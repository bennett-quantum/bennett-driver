use super::*;

pub enum Phase {
    Source,
    Linked,
}

pub fn prepare(
    o: &Options,
    b: &mut Build,
    major: u32,
    modules: &[String],
    phase: Phase,
) -> Result<Vec<String>> {
    let include_vscale = matches!(phase, Phase::Linked);
    let classes = o
        .plugin_args
        .iter()
        .filter(|arg| arg.key == OptionKey::Class)
        .map(|arg| arg.value.clone())
        .collect::<Vec<_>>();
    if classes.is_empty()
        && o.get(OptionKey::Snapshot).is_none()
        && (!include_vscale || o.get(OptionKey::Vscale).is_none())
    {
        return Ok(modules.to_vec());
    }
    let tool = llvm_utility::compile(
        b,
        major,
        "mode-preparation",
        include_str!("mode-preparation.cpp"),
    )?;
    let mut request = obj([("classes", strings(&classes))]);
    for (name, key) in [
        ("snapshot", OptionKey::Snapshot),
        ("vscale", OptionKey::Vscale),
    ] {
        if key == OptionKey::Vscale && !include_vscale {
            continue;
        }
        if let Some(value) = o.get(key) {
            request.set(name, value.into());
        }
    }
    let prefix = if include_vscale {
        "mode"
    } else {
        "source-mode"
    };
    let config = b.out.join(format!("{prefix}-request.json"));
    write(&config, request.encode())?;
    let input = b.out.join(format!("{prefix}-input.bc"));
    let output = b.out.join(format!("{prefix}-prepared.bc"));
    let report = b.out.join(format!("{prefix}-preparation.json"));
    let mut link = vec![super::tool(major, "llvm-link")];
    link.extend_from_slice(modules);
    link.extend(["-o".into(), input.display().to_string()]);
    b.run(&format!("{prefix}-input-link"), link, None)?;
    b.run(
        &format!("{prefix}-preparation"),
        vec![
            tool.display().to_string(),
            input.display().to_string(),
            output.display().to_string(),
            config.display().to_string(),
            report.display().to_string(),
        ],
        None,
    )?;
    b.record.set(
        if include_vscale {
            "mode_preparation"
        } else {
            "source_mode_preparation"
        },
        obj([
            ("request", artifact(&config, None)?),
            ("tool", artifact(&tool, None)?),
            ("input", artifact(&input, None)?),
            ("module", artifact(&output, None)?),
            ("report", artifact(&report, None)?),
        ]),
    );
    Ok(vec![output.display().to_string()])
}
