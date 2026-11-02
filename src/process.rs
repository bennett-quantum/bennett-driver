//! Synthesize the ordinary process-entry prelude before whole-program analysis.
use super::*;

pub fn prepare(
    o: &Options,
    b: &mut Build,
    major: u32,
    module: &Path,
    runtime: &Path,
    arith: &Path,
) -> Result<()> {
    if o.get("bennett-tier") != Some("reversible") {
        return Ok(());
    }
    let entry = o
        .get("bennett-entry")
        .ok_or("BD-E-PROCESS: missing entry")?;
    let source = b.out.join("process-entry.cpp");
    write(&source, include_str!("process-entry.cpp"))?;
    let cache = env::var_os("TMPDIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| Path::new(env!("CARGO_MANIFEST_DIR")).join(".tmp"))
        .join("bennett-driver-process");
    fs::create_dir_all(&cache).map_err(|e| format!("process tool cache: {e}"))?;
    let executable = cache.join(format!("prepare-{major}-{}", sha(&source)?));
    if !executable.is_file() {
        let flags = b.run(
            "process-tool-flags",
            vec![
                tool(major, "llvm-config"),
                "--cxxflags".into(),
                "--ldflags".into(),
                "--libs".into(),
                "core".into(),
                "irreader".into(),
                "bitwriter".into(),
            ],
            None,
        )?;
        let temporary = b.out.join("process-entry-tool");
        let mut args = vec![
            tool(major, "clang++"),
            "-O1".into(),
            source.display().to_string(),
        ];
        args.extend(flags.split_whitespace().map(String::from));
        args.extend(["-o".into(), temporary.display().to_string()]);
        b.run("process-tool-build", args, None)?;
        fs::rename(&temporary, &executable).map_err(|e| format!("process tool publish: {e}"))?;
    }
    let output = b.out.join("process-entry.bc");
    let report = b.out.join("process-entry.json");
    b.run(
        "process-entry",
        vec![
            executable.display().to_string(),
            module.display().to_string(),
            output.display().to_string(),
            entry.into(),
            report.display().to_string(),
        ],
        None,
    )?;
    b.run(
        "process-runtime-link",
        vec![
            tool(major, "llvm-link"),
            output.display().to_string(),
            runtime.display().to_string(),
            arith.display().to_string(),
            "--only-needed".into(),
            "-o".into(),
            module.display().to_string(),
        ],
        None,
    )?;
    close_libraries(
        b,
        major,
        "process-library-closure",
        module,
        &[runtime, arith],
    )?;
    let definitions = b.run(
        "process-root-audit",
        vec![
            tool(major, "llvm-nm"),
            "--defined-only".into(),
            module.display().to_string(),
        ],
        None,
    )?;
    for name in ["__bennett_rt_prepare_process", "exit"] {
        if !definitions
            .lines()
            .any(|line| line.split_whitespace().last() == Some(name))
        {
            return Err(format!(
                "BD-E-PROCESS: published runtimes lacks required definition {name}; preparation must enter materialisation"
            ));
        }
    }
    let prepared = b.out.join("process-prepared.bc");
    fs::copy(module, &prepared).map_err(|e| format!("process prepared module: {e}"))?;
    b.record.set(
        "process_preparation",
        obj([
            ("schema", "bennett-driver-process-preparation-1".into()),
            ("entry", entry.into()),
            ("module", artifact(&prepared, None)?),
            ("wrapper", artifact(&output, None)?),
            ("report", artifact(&report, None)?),
            ("tool", artifact(&executable, None)?),
            ("runtimes", artifact(runtime, None)?),
            (
                "native_inputs",
                "startup registers comparison inputs before checked preparation".into(),
            ),
            (
                "execution_claim",
                "preparation component; full R/executor acceptance is separate".into(),
            ),
        ]),
    );
    b.save("running")
}
