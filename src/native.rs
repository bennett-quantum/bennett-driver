//! Strict native comparison. No standard libraries or startup files are added.
use super::*;
fn marker(name: &str) -> bool {
    matches!(
        name,
        "__bennett_qalloc"
            | "__bennett_qborrow"
            | "__bennett_qfree"
            | "__bennett_gate"
            | "__bennett_gate2"
            | "__bennett_gate3"
            | "__bennett_rot"
            | "__bennett_measure"
            | "__bennett_qload"
            | "__bennett_qstore"
            | "__bennett_qprep"
            | "__bennett_observe"
            | "__bennett_ctrl"
            | "__bennett_adj"
            | "__bennett_compute"
            | "__bennett_reversible"
            | "__bennett_oracle"
            | "__bennett_inplace"
            | "__bennett_effect_console_write"
            | "__bennett_effect_clock_read"
            | "__bennett_effect_entropy_read"
            | "__bennett_effect_block_read"
            | "__bennett_effect_block_write"
    )
}
fn audit_markers(b: &mut Build, m: u32, p: &Path) -> Result<()> {
    let symbols = b.run(
        "native-marker-audit",
        vec![
            tool(m, "llvm-nm"),
            "--defined-only".into(),
            p.display().to_string(),
        ],
        None,
    )?;
    for name in symbols.lines().filter_map(|l| l.split_whitespace().last()) {
        if marker(name) {
            return Err(format!(
                "BD-E-MARKER-DEFINED: §19.9 comparison input {} supplies marker definition {name}",
                p.display()
            ));
        }
    }
    Ok(())
}
pub fn compare(o: &Options, b: &mut Build) -> Result<()> {
    let m = o.major()?;
    let device = absolute(
        o.get("bennett-materialised")
            .map(PathBuf::from)
            .unwrap_or(b.out.join("device.bc")),
    )?;
    let runtime = configured_path(o, "bennett-runtimes")?;
    let arith = configured_path(o, "bennett-arith")?;
    let adapter = configured_path(o, "bennett-native-check")?;
    let support = configured_path(o, "bennett-native-support")?;
    let sysroot = o.required_sysroot()?;
    let record_path = absolute(
        o.get("bennett-comparison-record")
            .map(PathBuf::from)
            .unwrap_or(b.out.join("native-comparison.json")),
    )?;
    let exe = absolute(
        o.get("bennett-comparison-output")
            .map(PathBuf::from)
            .unwrap_or(b.out.join("native-O2")),
    )?;
    let materialisation = native_adapter::Adapter::select(o, m, &device)?;
    let mut protected = vec![device.clone(), runtime.clone(), arith.clone()];
    output_paths::recorded_artifacts(&b.record, &mut protected);
    if let Some(adapter) = &materialisation {
        protected.extend([adapter.plugin.clone(), adapter.receipt.clone()]);
    }
    protected.extend(o.inputs.iter().map(absolute).collect::<Result<Vec<_>>>()?);
    protected.extend(o.paths.values().cloned());
    for key in [
        "bennett-native-input",
        "bennett-native-backend",
        "bennett-classifier-input",
        "bennett-comparison-layout",
        "bennett-budgets",
        "bennett-argv-replies",
        "bennett-disk",
    ] {
        if let Some(path) = o.get(key) {
            protected.push(absolute(path)?);
        }
    }
    protected.push(sysroot.root.clone());
    let mut destinations = vec![
        ("comparison record", record_path.clone()),
        ("O2 executable", exe.clone()),
        ("O0 executable", exe.with_file_name("native-O0")),
    ];
    for name in [
        "manifest.json",
        "native-comparisons.json",
        "native-detection.json",
        "native-classifiers.json",
        "resolved-layout.json",
        "native-layout.ll",
        "native-layout.bc",
        "comparison.ld",
        "comparison.bc",
        "comparison-linked.bc",
        "comparison-check-input.bc",
        "comparison-checked.bc",
        "comparison-adapted.bc",
        "arith-input.ll",
        "native-memory.bc",
        "bennett-native-input.bc",
        "bennett-native-backend.bc",
        "native-prepared.bc",
        "native-finalised.bc",
        "native-host.bc",
        "native-preparation.json",
        "native-materialisation.json",
        "native-O2.o",
        "native-O0.o",
    ] {
        destinations.push((name, b.out.join(name)));
    }
    output_paths::admit(&protected, &destinations)?;
    let device_sha = sha(&device)?;
    for (key, p) in [("runtimes", &runtime), ("arith", &arith)] {
        b.record
            .set(key, artifact(p, o.get(&format!("bennett-{key}-sha256")))?);
    }
    b.run(
        "comparison-verify",
        vec![
            tool(m, "opt"),
            "-passes=verify".into(),
            "-disable-output".into(),
            device.display().to_string(),
        ],
        None,
    )?;
    let source = if let Some(adapter) = &materialisation {
        adapter.run(b, m, native_adapter::Phase::Prepare, &device)?
    } else {
        device.clone()
    };
    let input_ir = b.out.join("arith-input.ll");
    b.run(
        "comparison-arith-input",
        vec![
            tool(m, "opt"),
            "-passes=verify".into(),
            "-S".into(),
            source.display().to_string(),
            "-o".into(),
            input_ir.display().to_string(),
        ],
        None,
    )?;
    let base_arith_sha = sha(&arith)?;
    let arith = arith::prepare(o, b, m, &arith, &[input_ir])?;
    let mut extras = vec![];
    // Explicit comparison-only support, never linked into the production module.
    for key in ["bennett-native-input", "bennett-native-backend"] {
        if let Some(p) = o.get(key) {
            let p = absolute(p)?;
            b.record.set(key, artifact(&p, None)?);
            let output = b.out.join(format!("{key}.bc"));
            let mut support = vec![
                tool(m, "clang"),
                "-O2".into(),
                "-ffreestanding".into(),
                "-fno-builtin".into(),
                "-fno-pie".into(),
                "-emit-llvm".into(),
                "-c".into(),
                p.display().to_string(),
                "-o".into(),
                output.display().to_string(),
            ];
            support.extend(sysroot.frontend_flags());
            b.run("native-support", support, None)?;
            audit_markers(b, m, &output)?;
            extras.push(output.display().to_string());
        }
    }
    let linked = b.out.join("comparison-linked.bc");
    let bitcode_link = vec![
        tool(m, "llvm-link"),
        source.display().to_string(),
        runtime.display().to_string(),
        arith.display().to_string(),
        "--only-needed".into(),
        "-o".into(),
        linked.display().to_string(),
    ];
    b.run("comparison-bitcode-link", bitcode_link.clone(), None)?;
    close_libraries(
        b,
        m,
        "comparison-materialised-closure",
        &linked,
        &[&runtime, &arith],
    )?;
    audit_markers(b, m, &linked)?;
    let checked = b.out.join("comparison-checked.bc");
    b.record.set(
        "native_check_adapter",
        artifact(&adapter, o.get("bennett-native-check-sha256"))?,
    );
    // Include harness roots before the adapter emits its global-object table.
    // Materialised callees may read data supplied by this comparison harness.
    let check_input = b.out.join("comparison-check-input.bc");
    let mut check_link = vec![tool(m, "llvm-link"), linked.display().to_string()];
    check_link.extend(extras);
    check_link.extend(["-o".into(), check_input.display().to_string()]);
    b.run("comparison-check-inputs", check_link, None)?;
    let linked_sha = sha(&linked)?;
    b.run(
        "comparison-checks",
        vec![
            adapter.display().to_string(),
            m.to_string(),
            check_input.display().to_string(),
            checked.display().to_string(),
        ],
        None,
    )?;
    if sha(&device)? != device_sha || sha(&linked)? != linked_sha {
        return Err("BD-E-NATIVE-CHECKS: adapter modified original materialised input".into());
    }
    b.run(
        "comparison-check-verify",
        vec![
            tool(m, "opt"),
            "-passes=verify".into(),
            "-disable-output".into(),
            checked.display().to_string(),
        ],
        None,
    )?;
    b.record
        .set("checked_materialised", artifact(&checked, None)?);
    let coverage = obj([
        ("subject", "materialised".into()),
        (
            "provenance",
            if materialisation.is_some() {
                "selected-entry launch record verified".into()
            } else {
                "explicit module; producer receipt not verified".into()
            },
        ),
        ("status", "instrumented".into()),
        ("general_memory", true.into()),
        ("use_after_free", true.into()),
        ("out_of_live_allocation", true.into()),
        ("memory_function_ranges", true.into()),
        ("invalid_free", true.into()),
        ("double_free", true.into()),
        ("division_by_zero", true.into()),
        ("signed_division_overflow", true.into()),
        ("explicit_fault", true.into()),
        ("unreachable", true.into()),
        ("source_ub_erased_by_optimisation", false.into()),
        ("infrastructure_exit_status", 125u32.into()),
        ("adapter", artifact(&adapter, None)?),
        ("materialised_sha256", device_sha.clone().into()),
        ("checked_sha256", sha(&checked)?.into()),
    ]);
    write(
        b.out.join("native-detection.json"),
        coverage.encode() + "\n",
    )?;
    b.record.set(
        "native_detection",
        artifact(&b.out.join("native-detection.json"), None)?,
    );
    b.record.set(
        "native_support",
        artifact(&support, o.get("bennett-native-support-sha256"))?,
    );
    if let Some(p) = o.get("bennett-comparison-layout") {
        b.record
            .set("comparison_layout", artifact(&absolute(p)?, None)?);
    }
    b.run(
        "native-layout",
        vec![
            "python3".into(),
            "-c".into(),
            include_str!("../scripts/native-layout.py").into(),
            b.out.display().to_string(),
            device.display().to_string(),
            o.get("bennett-comparison-layout").unwrap_or("").into(),
            o.get("bennett-layout-data-base").unwrap_or("4096").into(),
            o.get("bennett-layout-text-base").unwrap_or("").into(),
        ],
        None,
    )?;
    let config = b.out.join("native-layout.bc");
    b.run(
        "native-layout-assemble",
        vec![
            tool(m, "llvm-as"),
            b.out.join("native-layout.ll").display().to_string(),
            "-o".into(),
            config.display().to_string(),
        ],
        None,
    )?;
    b.record.set(
        "resolved_layout",
        artifact(&b.out.join("resolved-layout.json"), None)?,
    );
    let native_source = if let Some(adapter) = &materialisation {
        adapter.run(b, m, native_adapter::Phase::Finalise, &checked)?
    } else {
        checked.clone()
    };
    let adapted = b.out.join("comparison-adapted.bc");
    let mut support_link = vec![tool(m, "llvm-link"), native_source.display().to_string()];
    // Startup support stays outside checked producer/harness bodies.
    support_link.extend([
        config.display().to_string(),
        format!("--override={}", support.display()),
        "-o".into(),
        adapted.display().to_string(),
    ]);
    b.run("comparison-support-link", support_link, None)?;
    let closed = b.out.join("comparison.bc");
    b.run(
        "comparison-closure-link",
        vec![
            tool(m, "llvm-link"),
            adapted.display().to_string(),
            runtime.display().to_string(),
            arith.display().to_string(),
            "--only-needed".into(),
            "-o".into(),
            closed.display().to_string(),
        ],
        None,
    )?;
    // LLVM codegen (especially O0) may introduce ABI memory libcalls after
    // --only-needed. Retain the published definitions that are not present.
    let definitions = b.run(
        "native-memory-audit",
        vec![
            tool(m, "llvm-nm"),
            "--defined-only".into(),
            closed.display().to_string(),
        ],
        None,
    )?;
    let defined: Vec<&str> = definitions
        .lines()
        .filter_map(|l| l.split_whitespace().last())
        .collect();
    let missing: Vec<&str> = ["memcpy", "memmove", "memset"]
        .into_iter()
        .filter(|n| !defined.contains(n))
        .collect();
    if !missing.is_empty() {
        let memory = b.out.join("native-memory.bc");
        let mut extract = vec![tool(m, "llvm-extract"), runtime.display().to_string()];
        extract.extend(missing.iter().map(|n| format!("--func={n}")));
        extract.extend(["-o".into(), memory.display().to_string()]);
        b.run("native-memory-extract", extract, None)?;
        b.run(
            "native-memory-link",
            vec![
                tool(m, "llvm-link"),
                closed.display().to_string(),
                memory.display().to_string(),
                "-o".into(),
                closed.display().to_string(),
            ],
            None,
        )?;
    }
    b.run(
        "native-memory-closure",
        vec![
            tool(m, "llvm-link"),
            closed.display().to_string(),
            runtime.display().to_string(),
            arith.display().to_string(),
            "--only-needed".into(),
            "-o".into(),
            closed.display().to_string(),
        ],
        None,
    )?;
    b.run(
        "comparison-cleanup",
        vec![
            tool(m, "opt"),
            "-passes=strip-dead-prototypes,verify".into(),
            closed.display().to_string(),
            "-o".into(),
            closed.display().to_string(),
        ],
        None,
    )?;
    if let Some(adapter) = &materialisation {
        let host = adapter.run(b, m, native_adapter::Phase::HostImports, &closed)?;
        fs::copy(host, &closed).map_err(|error| format!("native host imports: {error}"))?;
    }
    audit_markers(b, m, &closed)?;
    let imports = b.run(
        "native-import-audit",
        vec![
            tool(m, "llvm-nm"),
            "--undefined-only".into(),
            closed.display().to_string(),
        ],
        None,
    )?;
    let residual: Vec<String> = imports
        .lines()
        .filter_map(|l| l.split_whitespace().last())
        .filter(|n| marker(n))
        .map(String::from)
        .collect();
    let script = b.out.join("comparison.ld");
    let mut results = vec![];
    let mut first_error = None;
    for level in ["O2", "O0"] {
        let output = if level == "O2" {
            exe.clone()
        } else {
            exe.with_file_name("native-O0")
        };
        // Keep checked source IR fixed. Only machine-code optimisation differs
        // between the comparison and diagnostic variants.
        let code_input = b.out.join(format!("native-{level}.o"));
        b.run(
            &format!("native-codegen-{level}"),
            vec![
                tool(m, "llc"),
                format!("-{level}"),
                "-filetype=obj".into(),
                "-data-sections".into(),
                // A density above 100% selects branch lowering instead of
                // private jump tables whose readonly data differs by O-level.
                "-jump-table-density=101".into(),
                "-optsize-jump-table-density=101".into(),
                closed.display().to_string(),
                "-o".into(),
                code_input.display().to_string(),
            ],
            None,
        )?;
        let mut argv = vec![
            tool(m, "clang"),
            format!("-{level}"),
            "-nostdlib".into(),
            "-nostdinc".into(),
            "-static".into(),
            "-no-pie".into(),
            "-fno-merge-all-constants".into(),
            code_input.display().to_string(),
        ];
        argv.push(sysroot.link_flag());
        argv.extend([
            format!("-Wl,-T,{}", script.display()),
            "-Wl,-e,_start".into(),
            "-Wl,--fatal-warnings".into(),
            "-Wl,--no-undefined".into(),
            format!(
                "-Wl,-Map,{}",
                b.out.join(format!("native-{level}.map")).display()
            ),
            "-o".into(),
            output.display().to_string(),
        ]);
        let mut record = obj([
            ("schema", "bennett-driver-native-comparison-1".into()),
            ("variant", level.into()),
            ("llvm_major", m.into()),
            ("native_support_sha256", sha(&support)?.into()),
            (
                "resolved_layout_sha256",
                sha(&b.out.join("resolved-layout.json"))?.into(),
            ),
            ("residual_markers", strings(&residual)),
            ("materialised_sha256", device_sha.clone().into()),
            (
                "provenance",
                if materialisation.is_some() {
                    "selected-entry launch record verified".into()
                } else {
                    "explicit module; producer receipt not verified".into()
                },
            ),
            ("link_argv", strings(&argv)),
            ("bitcode_link_argv", strings(&bitcode_link)),
            ("linked_sha256", sha(&closed)?.into()),
            ("codegen_object", artifact(&code_input, None)?),
            ("runtimes_sha256", sha(&runtime)?.into()),
            ("arith_sha256", sha(&arith)?.into()),
            ("base_arith_sha256", base_arith_sha.clone().into()),
            ("status", "planned".into()),
        ]);
        if level == "O2" {
            write(&record_path, record.encode() + "\n")?;
        }
        let r = b.run(&format!("native-{level}"), argv, None);
        record.set(
            "status",
            if r.is_ok() {
                "linked".into()
            } else {
                "failed".into()
            },
        );
        if let Err(e) = r {
            record.set("error", e.clone().into());
            if first_error.is_none() {
                first_error = Some(e);
            }
        } else {
            let audit = b.run(
                "native-undefined",
                vec![
                    tool(m, "llvm-nm"),
                    "--undefined-only".into(),
                    output.display().to_string(),
                ],
                None,
            )?;
            if !audit.trim().is_empty() {
                return Err(format!("comparison unresolved imports: {audit}"));
            }
            b.run(
                "native-layout-audit",
                vec![
                    "python3".into(),
                    "-c".into(),
                    include_str!("../scripts/native-layout.py").into(),
                    "--audit".into(),
                    m.to_string(),
                    output.display().to_string(),
                    b.out.join("resolved-layout.json").display().to_string(),
                ],
                None,
            )?;
            record.set("sha256", sha(&output)?.into());
        }
        if level == "O2" {
            write(&record_path, record.encode() + "\n")?;
        }
        results.push(record);
    }
    results.push(obj([("variant", "O0-ASan".into()), ("status", "blocked".into()),
        ("code","BD-E-NATIVE-SANITIZER".into()),("stage","native-sanitizer".into()),
        ("function","<whole-program>".into()),("value_or_call","<instrumentation>".into()),
        ("constraint","§17.7 diagnostic instrumentation must not import hosted sanitizer/libc/libm".into()),
        ("required_change","Publish a real freestanding ASan closure or specified checked memory adapter".into()),
        ("blocked_on",strings(&["brt-nuu.2".into()])),
        ("reason","Published UBSan-minimal source classifier is separate; general memory detection remains required".into())]));
    b.record
        .set("native_comparisons", Json::Array(results.clone()));
    write(
        b.out.join("native-comparisons.json"),
        Json::Array(results).encode() + "\n",
    )?;
    if !residual.is_empty() {
        return Err(format!(
            "BD-E-NATIVE-MARKERS: §17.7 actual materialised device still calls {}; select the launch-record-verified marker-free comparison adapter; no fake definitions. {}",
            residual.join(", "),
            first_error.unwrap_or_default()
        ));
    }
    if let Some(e) = first_error {
        return Err(format!(
            "BD-E-NATIVE-LINK: §17.7/§19.5 strict comparison cannot link; no host libc/libm fallback. See native link diagnostics and the separate sanitizer receipt. {e}"
        ));
    }
    classifier::build(o, b, m, &arith)?;
    if sha(&device)? != device_sha {
        return Err("BD-E-OUTPUT-PATH: comparison changed the original materialised input".into());
    }
    b.save("linked")
}
