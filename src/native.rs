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
    let ws = Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap();
    let device = absolute(
        o.get("bennett-materialised")
            .map(PathBuf::from)
            .unwrap_or(b.out.join("device.bc")),
    )?;
    let runtime = absolute(
        o.get("bennett-runtimes")
            .map(PathBuf::from)
            .unwrap_or(ws.join(format!("bennett-runtimes/dist/llvm{m}/bennett-runtimes.bc"))),
    )?;
    let arith = absolute(
        o.get("bennett-arith")
            .map(PathBuf::from)
            .unwrap_or(ws.join(format!("bennett-arith/dist/llvm{m}/bennett-arith.bc"))),
    )?;
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
            support.extend([
                "-nostdinc".into(),
                "-isystem".into(),
                ws.join(format!(
                    "bennett-runtimes/dist/llvm{m}/musl-sysroot/include"
                ))
                .display()
                .to_string(),
            ]);
            support.extend(sysroot_flags(o)?);
            b.run("native-support", support, None)?;
            audit_markers(b, m, &output)?;
            extras.push(output.display().to_string());
        }
    }
    let linked = b.out.join("comparison-linked.bc");
    let bitcode_link = vec![
        tool(m, "llvm-link"),
        device.display().to_string(),
        runtime.display().to_string(),
        arith.display().to_string(),
        "--only-needed".into(),
        "-o".into(),
        linked.display().to_string(),
    ];
    b.run("comparison-bitcode-link", bitcode_link.clone(), None)?;
    audit_markers(b, m, &linked)?;
    let support = absolute(
        o.get("bennett-native-support")
            .map(PathBuf::from)
            .unwrap_or(ws.join(format!(
                "bennett-runtimes/dist/llvm{m}/musl-sysroot/lib/native-support.bc"
            ))),
    )?;
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
    let adapted = b.out.join("comparison-adapted.bc");
    let mut support_link = vec![tool(m, "llvm-link"), linked.display().to_string()];
    // A harness main is a root, not a --only-needed library: startup is added
    // here, after the initial production closure.
    support_link.extend(extras);
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
        let mut argv = vec![
            tool(m, "clang"),
            format!("-{level}"),
            "-nostdlib".into(),
            "-nostdinc".into(),
            "-static".into(),
            "-no-pie".into(),
            "-fno-merge-all-constants".into(),
            closed.display().to_string(),
        ];
        if let Some(root) = o.get("bennett-sysroot") {
            argv.push(format!("--sysroot={}", absolute(root)?.display()));
        }
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
            ("link_argv", strings(&argv)),
            ("bitcode_link_argv", strings(&bitcode_link)),
            ("linked_sha256", sha(&closed)?.into()),
            ("runtimes_sha256", sha(&runtime)?.into()),
            ("arith_sha256", sha(&arith)?.into()),
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
            record.set("sha256", sha(&output)?.into());
        }
        if level == "O2" {
            write(&record_path, record.encode() + "\n")?;
        }
        results.push(record);
    }
    results.push(obj([("variant", "O0-ASan-UBSan".into()), ("status", "blocked".into()),
        ("code","BD-E-NATIVE-SANITIZER".into()),("stage","native-sanitizer".into()),
        ("function","<whole-program>".into()),("value_or_call","<instrumentation>".into()),
        ("constraint","§17.7 diagnostic instrumentation must not import hosted sanitizer/libc/libm".into()),
        ("required_change","brt-nuu.1: publish a real freestanding ASan/UBSan closure or specified adapter".into()),
        ("blocked_on",strings(&["brt-nuu.1".into()])),
        ("reason","Published native closure has no freestanding ASan/UBSan runtime; no hosted sanitizer fallback".into())]));
    b.record
        .set("native_comparisons", Json::Array(results.clone()));
    write(
        b.out.join("native-comparisons.json"),
        Json::Array(results).encode() + "\n",
    )?;
    if !residual.is_empty() {
        return Err(format!(
            "BD-E-NATIVE-MARKERS: §17.7 actual materialised device still calls {}; bp-xyn must lower host-side markers; no fake definitions. {}",
            residual.join(", "),
            first_error.unwrap_or_default()
        ));
    }
    if let Some(e) = first_error {
        return Err(format!(
            "BD-E-NATIVE-LINK: §17.7/§19.5 strict comparison cannot link; no host libc/libm fallback. See native link diagnostics; sanitizer row separately blocked on brt-nuu.1. {e}"
        ));
    }
    b.save("complete")
}
