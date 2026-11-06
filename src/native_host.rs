//! Ordinary native output for source modules without a selected device entry.
use super::*;

pub fn build(
    o: &Options,
    b: &mut Build,
    major: u32,
    modules: &[String],
    pipeline: &str,
) -> Result<()> {
    let linked = b.out.join("linked.bc");
    let host = b.out.join("host.bc");
    let mut link = vec![tool(major, "llvm-link")];
    link.extend_from_slice(modules);
    link.extend(["-o".into(), linked.display().to_string()]);
    b.run("native-host-link-inputs", link, None)?;
    b.run(
        "postlink",
        vec![
            tool(major, "opt"),
            format!("-passes={pipeline}"),
            linked.display().to_string(),
            "-o".into(),
            host.display().to_string(),
        ],
        None,
    )?;
    let symbols = b.run(
        "native-host-symbols",
        vec![
            tool(major, "llvm-nm"),
            "--defined-only".into(),
            "--format=posix".into(),
            host.display().to_string(),
        ],
        None,
    )?;
    let main = symbols.lines().any(|line| {
        let mut fields = line.split_whitespace();
        fields.next() == Some("main") && matches!(fields.next(), Some("T" | "t" | "W" | "w"))
    });
    let output = b
        .out
        .join(if main { "native-host" } else { "native-host.o" });
    let mut codegen = vec![
        tool(major, "clang"),
        host.display().to_string(),
        "-o".into(),
        output.display().to_string(),
    ];
    if main {
        codegen.push("-lm".into());
    } else {
        codegen.push("-c".into());
    }
    if let Some(sysroot) = &o.sysroot {
        codegen.push(sysroot.link_flag());
    }
    b.run("native-host-codegen", codegen, None)?;
    write(b.out.join("launches.json"), "[]\n")?;
    b.record.set("completion", "native-only".into());
    b.record.set(
        "device_selection",
        "no reserved Bennett symbols in source modules and no explicit reversible entry".into(),
    );
    b.record.set(
        "outputs",
        obj([
            ("linked", artifact(&linked, None)?),
            ("host", artifact(&host, None)?),
            ("native_host", artifact(&output, None)?),
        ]),
    );
    b.save("complete")
}
