//! Original-input definedness diagnostics; never used as materialised results.
use super::*;

pub fn build(o: &Options, b: &mut Build, major: u32, arith: &Path) -> Result<()> {
    let runtime = configured_path(o, "bennett-runtimes")?;
    let publication = runtime
        .parent()
        .ok_or("BD-E-CONFIG: runtime has no publication directory")?;
    let sysroot = o.required_sysroot()?;
    let mut sources = match o.get("bennett-classifier-input") {
        Some(p) => vec![absolute(p)?],
        None => vec![],
    };
    if !sources.is_empty()
        && let Some(p) = o.get("bennett-native-input")
    {
        sources.push(absolute(p)?);
    }
    let mut row = obj([
        ("variant", "O0-UBSan-minimal-original-input".into()),
        ("subject", "original-input".into()),
        ("layout_scope", "independent source diagnostic; never native/device address agreement".into()),
        ("llvm_major", major.into()),
        ("status", "blocked".into()),
        ("coverage", obj([
            ("instrumentation", "clang -fsanitize=undefined -fsanitize-minimal-runtime".into()),
            ("array_bounds", true.into()),
            ("general_memory", false.into()),
            ("use_after_free", false.into()),
            ("runtime_internals", false.into()),
            ("source_ub_erased_by_optimisation", false.into()),
        ])),
        ("outcome_policy", "classifier-flagged inputs are undefined/excluded; record execution diagnostics per input".into()),
    ]);
    let result = (|| -> Result<()> {
        if sources.is_empty() {
            return Err("original C input is required; materialised bitcode cannot classify erased source UB".into());
        }
        let mut modules = vec![];
        let mut inputs = vec![];
        for (i, source) in sources.iter().enumerate() {
            inputs.push(artifact(source, None)?);
            if source.extension().and_then(|s| s.to_str()) != Some("c") {
                return Err(format!(
                    "BD-E-NATIVE-CLASSIFIER: original-input instrumentation for {} remains required; supply original C using --bennett-classifier-input",
                    source.display()
                ));
            }
            let module = b.out.join(format!("classifier-input-{i}.bc"));
            let mut args = vec![
                tool(major, "clang"),
                "--target=x86_64-unknown-linux-musl".into(),
                "-O0".into(),
                "-ffreestanding".into(),
                "-fno-builtin".into(),
                "-fno-pie".into(),
                "-fsanitize=undefined".into(),
                "-fsanitize-minimal-runtime".into(),
                "-fno-sanitize-recover=all".into(),
                "-emit-llvm".into(),
                "-c".into(),
                source.display().to_string(),
                "-o".into(),
                module.display().to_string(),
            ];
            args.extend(sysroot.frontend_flags());
            b.run("classifier-frontend", args, None)?;
            modules.push(module.display().to_string());
        }
        row.set("inputs", Json::Array(inputs));
        // Instrumentation adds globals. Resolve this source classifier's own
        // layout rather than moving the materialised comparison's heap.
        let layout_ir = b.out.join("classifier-layout.ll");
        let layout_bc = b.out.join("classifier-layout.bc");
        let script = b.out.join("classifier.ld");
        // The layout script already validated these exact source option values.
        let limit = b.run(
            "classifier-heap-budget",
            vec![
                "python3".into(),
                "-c".into(),
                "import json,sys; print(json.load(open(sys.argv[1]))['heap_limit_max'])".into(),
                b.out.join("resolved-layout.json").display().to_string(),
            ],
            None,
        )?;
        let limit = limit
            .trim()
            .parse::<u64>()
            .map_err(|e| format!("classifier heap budget: {e}"))?;
        let data = o.get("bennett-layout-data-base").unwrap_or("4096");
        write(
            &layout_ir,
            format!(
                "target triple = \"x86_64-unknown-linux-musl\"\n@__bennett_classifier_heap = external global i8\n@__bennett_rt_native_layout = constant {{ i64, i64, i64 }} {{ i64 1, i64 ptrtoint (ptr @__bennett_classifier_heap to i64), i64 {limit} }}, align 8\n"
            ),
        )?;
        write(
            &script,
            format!(
                "SECTIONS {{\n . = {data}; .rodata : {{ *(.rodata .rodata.*) }}\n .data : {{ *(.data .data.*) *(.init_array*) *(.fini_array*) }}\n .bss : {{ *(.bss .bss.*) *(COMMON) }}\n __bennett_classifier_heap = ALIGN(.,4096);\n . = ALIGN(MAX(0x400000, __bennett_classifier_heap + {limit}), 0x200000);\n .text : {{ *(.text .text.*) }}\n /DISCARD/ : {{ *(.eh_frame*) *(.comment) *(.note*) }}\n}}\n"
            ),
        )?;
        b.run(
            "classifier-layout-assemble",
            vec![
                tool(major, "llvm-as"),
                layout_ir.display().to_string(),
                "-o".into(),
                layout_bc.display().to_string(),
            ],
            None,
        )?;
        row.set("layout", artifact(&layout_ir, None)?);
        row.set("linker_script", artifact(&script, None)?);
        let runtime = publication.join("bennett-runtimes-native.bc");
        let support = publication.join("sanitizer-support.bc");
        let archive = publication.join("libclang_rt.ubsan_minimal-x86_64.a");
        for (name, p) in [
            ("runtime", &runtime),
            ("support", &support),
            ("compiler_rt", &archive),
        ] {
            row.set(name, artifact(p, None)?);
        }
        let linked = b.out.join("classifier-native.bc");
        let closed = b.out.join("classifier-closed.bc");
        let mut args = vec![tool(major, "llvm-link")];
        args.extend(modules);
        args.extend([
            layout_bc.display().to_string(),
            format!("--override={}", runtime.display()),
            "-o".into(),
            linked.display().to_string(),
        ]);
        b.run("classifier-native-link", args, None)?;
        b.run(
            "classifier-closure-link",
            vec![
                tool(major, "llvm-link"),
                linked.display().to_string(),
                arith.display().to_string(),
                "--only-needed".into(),
                "-o".into(),
                closed.display().to_string(),
            ],
            None,
        )?;
        let binary = b.out.join("classifier-ubsan-minimal");
        let args = vec![
            tool(major, "clang"),
            "--target=x86_64-unknown-linux-musl".into(),
            "-O0".into(),
            "-nostdlib".into(),
            "-nostdinc".into(),
            "-static".into(),
            "-no-pie".into(),
            "-ffreestanding".into(),
            "-fno-builtin".into(),
            "-fno-sanitize-link-runtime".into(),
            "-Wl,-e,_start".into(),
            "-Wl,--no-undefined".into(),
            format!("-Wl,-T,{}", script.display()),
            format!("-Wl,-Map,{}", b.out.join("classifier.map").display()),
            closed.display().to_string(),
            support.display().to_string(),
            archive.display().to_string(),
            "-o".into(),
            binary.display().to_string(),
        ];
        row.set("link_argv", strings(&args));
        b.run("classifier-codegen", args, None)?;
        let imports = b.run(
            "classifier-import-audit",
            vec![
                tool(major, "llvm-nm"),
                "--undefined-only".into(),
                binary.display().to_string(),
            ],
            None,
        )?;
        if !imports.trim().is_empty() {
            return Err(format!(
                "BD-E-NATIVE-CLASSIFIER: unresolved imports {imports}"
            ));
        }
        row.set("binary", artifact(&binary, None)?);
        row.set("link_map", artifact(&b.out.join("classifier.map"), None)?);
        row.set("status", "linked".into());
        Ok(())
    })();
    if let Err(ref e) = result {
        row.set("reason", e.clone().into());
    }
    let rows = Json::Array(vec![row, obj([
        ("variant", "O0-ASan-original-input".into()),
        ("subject", "original-input".into()),
        ("status", "blocked".into()),
        ("blocked_on", strings(&["brt-nuu.2".into()])),
        ("reason", "Full freestanding ASan is not published; UBSan does not detect general memory faults or use after free".into()),
    ])]);
    write(b.out.join("native-classifiers.json"), rows.encode() + "\n")?;
    b.record.set("source_classifiers", rows);
    // An adapter without original inputs is still useful as link evidence.
    // An explicitly requested classifier must fail loudly if it cannot build.
    if o.get("bennett-classifier-input").is_some() {
        result.map_err(|e| format!("BD-E-NATIVE-CLASSIFIER: {e}"))?;
    }
    Ok(())
}
