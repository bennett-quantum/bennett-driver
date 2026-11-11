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
    if o.tier != Some(Tier::Reversible) {
        return Ok(());
    }
    let entry = o
        .get(OptionKey::Entry)
        .ok_or("BD-E-PROCESS: missing entry")?;
    let executable =
        llvm_utility::compile(b, major, "process-entry", include_str!("process-entry.cpp"))?;
    let output = b.out.join("process-entry.bc");
    let report = b.out.join("process-entry.json");
    let mut synthesis = vec![
        executable.display().to_string(),
        module.display().to_string(),
        output.display().to_string(),
        entry.into(),
        report.display().to_string(),
    ];
    if o.contract == Contract::ClassicalR {
        synthesis.push(".bennett.driver.run.init".into());
    }
    b.run("process-entry", synthesis, None)?;
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
    if o.contract == Contract::ClassicalR && o.emission == Emission::ProcessBitcode {
        bind_initialisation(b, major, module)?;
    }
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
    b.run(
        "process-definition-audit",
        vec![
            executable.display().to_string(),
            "--verify".into(),
            module.display().to_string(),
            entry.into(),
        ],
        None,
    )?;
    let prepared = b.out.join("process-prepared.bc");
    fs::copy(module, &prepared).map_err(|e| format!("process prepared module: {e}"))?;
    b.record.set(
        "process_preparation",
        obj([
            ("schema", "bennett-driver-process-preparation-1".into()),
            ("entry", entry.into()),
            ("helper_type", "void (i32, ptr, ptr)".into()),
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

// Bind the selected link inventory after LTO, before device materialisation.
pub fn bind_initialisation(b: &mut Build, major: u32, module: &Path) -> Result<()> {
    let tool = llvm_utility::compile(
        b,
        major,
        "process-init-fini",
        include_str!("process-init-fini.cpp"),
    )?;
    let bound = b.out.join("process-init-fini.bc");
    let facts = b.out.join("process-init-fini.json");
    b.run(
        "process-init-fini",
        vec![
            tool.display().to_string(),
            module.display().to_string(),
            bound.display().to_string(),
            facts.display().to_string(),
        ],
        None,
    )?;
    fs::copy(&bound, module).map_err(|error| format!("BD-E-PROCESS-LINK: {error}"))?;
    b.record.set(
        "process_initialisation",
        obj([
            ("module", artifact(&bound, None)?),
            ("report", artifact(&facts, None)?),
        ]),
    );
    Ok(())
}
