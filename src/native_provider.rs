//! Driver-owned isolated hosted provider and freestanding component startup.
use super::*;

pub fn enabled(o: &Options) -> bool {
    o.paths.contains_key(&OptionKey::NativeProvider)
}
pub fn component(o: &Options, output: &Path) -> PathBuf {
    if enabled(o) {
        PathBuf::from(format!("{}.component", output.display()))
    } else {
        output.to_path_buf()
    }
}
pub fn prepare(o: &Options, b: &mut Build, adapter: &native_adapter::Adapter) -> Result<PathBuf> {
    let provider = configured_path(o, OptionKey::NativeProvider)?;
    let target = configured_path(o, OptionKey::NativeTarget)?;
    b.record.set("native_provider", artifact(&provider, None)?);
    b.record.set("native_target", artifact(&target, None)?);
    write(
        b.out.join("native-provider-api.h"),
        include_str!("native_provider_api.h"),
    )?;
    write(
        b.out.join("native-component.c"),
        include_str!("native_component.c"),
    )?;
    write(
        b.out.join("native-bootstrap.c"),
        include_str!("native_bootstrap.c"),
    )?;
    write(
        b.out.join("native-provider-run.py"),
        include_str!("../scripts/native-provider-run.py"),
    )?;
    b.run(
        "native-provider-ir",
        vec![
            tool(o.major, "llvm-dis"),
            b.out.join("native-finalised.bc").display().to_string(),
            "-o".into(),
            b.out.join("native-finalised.ll").display().to_string(),
        ],
        None,
    )?;
    let mut calling_entry = adapter.entry.clone();
    for key in [OptionKey::NativeInput, OptionKey::NativeBackend] {
        if o.get(key).is_some() {
            let names = b.run(
                "native-provider-caller",
                vec![
                    tool(o.major, "llvm-nm"),
                    "--defined-only".into(),
                    b.out.join(format!("{key}.bc")).display().to_string(),
                ],
                None,
            )?;
            if names
                .lines()
                .any(|line| line.split_whitespace().last() == Some("main"))
            {
                calling_entry = "main".into();
            }
        }
    }
    b.run(
        "native-provider-plan",
        vec![
            "python3".into(),
            "-c".into(),
            include_str!("../scripts/native-provider-plan.py").into(),
            "prepare".into(),
            b.out.display().to_string(),
            adapter.entry.clone(),
            adapter.receipt.display().to_string(),
            provider.display().to_string(),
            target.display().to_string(),
            calling_entry,
        ],
        None,
    )?;
    let output = b.out.join("native-component.bc");
    let mut args = vec![
        tool(o.major, "clang"),
        "-O0".into(),
        "-ffreestanding".into(),
        "-fno-builtin".into(),
        "-fno-pie".into(),
        "-emit-llvm".into(),
        "-c".into(),
        b.out.join("native-component.c").display().to_string(),
        "-o".into(),
        output.display().to_string(),
    ];
    args.extend(o.required_sysroot()?.frontend_flags());
    b.run("native-provider-gateway", args, None)?;
    b.run(
        "native-provider-bootstrap",
        vec![
            "cc".into(),
            "-std=c11".into(),
            "-O2".into(),
            "-fPIE".into(),
            "-pie".into(),
            b.out.join("native-bootstrap.c").display().to_string(),
            "-ldl".into(),
            "-o".into(),
            b.out.join("native-bootstrap").display().to_string(),
        ],
        None,
    )?;
    b.record.set(
        "native_startup",
        obj([
            ("profile", "bennett-driver-isolated-provider-1".into()),
            (
                "status",
                "owned load/bind/entry/unload startup generated; execution receipt required".into(),
            ),
            (
                "plan",
                artifact(&b.out.join("native-provider-plan.json"), None)?,
            ),
        ]),
    );
    Ok(output)
}
pub fn wrap(b: &mut Build, output: &Path, component: &Path) -> Result<()> {
    b.run(
        "native-provider-package",
        vec![
            "python3".into(),
            "-c".into(),
            include_str!("../scripts/native-provider-plan.py").into(),
            "wrap".into(),
            b.out.display().to_string(),
            output.display().to_string(),
            component.display().to_string(),
            b.out.join("native-provider-run.py").display().to_string(),
        ],
        None,
    )?;
    Ok(())
}

pub fn sections(o: &Options, b: &mut Build, input: &Path) -> Result<PathBuf> {
    let tool = llvm_utility::compile(
        b,
        o.major,
        "native-component-adapt",
        include_str!("native_component_adapt.cpp"),
    )?;
    let output = b.out.join("comparison-sectioned.bc");
    b.run(
        "native-component-adapt",
        vec![
            tool.display().to_string(),
            input.display().to_string(),
            b.out.join("resolved-layout.json").display().to_string(),
            output.display().to_string(),
        ],
        None,
    )?;
    b.record.set("native_sectioned", artifact(&output, None)?);
    Ok(output)
}

pub fn destinations(o: &Options, b: &Build, exe: &Path) -> Vec<(&'static str, PathBuf)> {
    if !enabled(o) {
        return vec![];
    }
    let mut paths = vec![];
    for name in [
        "native-provider-api.h",
        "native-component.c",
        "native-component.bc",
        "native-bootstrap.c",
        "native-bootstrap",
        "native-provider-run.py",
        "native-selected.bennett",
        "native-target.json",
        "native-provider-plan.json",
        "native-finalised.ll",
        "comparison-sectioned.bc",
    ] {
        paths.push(("hosted startup artifact", b.out.join(name)));
    }
    for executable in [exe.to_path_buf(), exe.with_file_name("native-O0")] {
        for suffix in [".component", ".provider-config.json", ".runtime.json"] {
            paths.push((
                "hosted comparison output",
                PathBuf::from(format!("{}{suffix}", executable.display())),
            ));
        }
    }
    paths
}
