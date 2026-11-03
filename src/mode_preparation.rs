use super::*;

pub fn prepare(o: &Options, b: &mut Build, major: u32, modules: &[String]) -> Result<Vec<String>> {
    let classes = o
        .plugin_args
        .iter()
        .filter_map(|arg| arg.strip_prefix("-bennett-class="))
        .map(str::to_string)
        .collect::<Vec<_>>();
    if classes.is_empty()
        && o.get("bennett-snapshot").is_none()
        && o.get("bennett-vscale").is_none()
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
    for key in ["snapshot", "vscale"] {
        if let Some(value) = o.get(&format!("bennett-{key}")) {
            request.set(key, value.into());
        }
    }
    let config = b.out.join("mode-request.json");
    write(&config, request.encode())?;
    let input = b.out.join("mode-input.bc");
    let output = b.out.join("mode-prepared.bc");
    let report = b.out.join("mode-preparation.json");
    let mut link = vec![super::tool(major, "llvm-link")];
    link.extend_from_slice(modules);
    link.extend(["-o".into(), input.display().to_string()]);
    b.run("mode-input-link", link, None)?;
    b.run(
        "mode-preparation",
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
        "mode_preparation",
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
