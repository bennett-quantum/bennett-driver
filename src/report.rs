use super::*;
/// Driver implementation refusals are distinct from the four normative ISA
/// blockers. Keep the original diagnostics; never relabel a missing mode as ISA7.
pub fn failure(out: Option<&Path>, error: &str, stage: &str, args: &[String]) -> Result<()> {
    let code = error
        .split(|c: char| !(c.is_ascii_alphanumeric() || c == '-'))
        .find(|s| s.starts_with("BD-E-") || s.starts_with("BD-B-"))
        .unwrap_or(
            if stage.starts_with("native") || error.contains("comparison") {
                "DRIVER-NATIVE-LINK"
            } else if error.contains("plugin") {
                "DRIVER-PLUGIN-REFUSAL"
            } else {
                "DRIVER-INPUT"
            },
        );
    let (constraint, change) = if code == "BD-B-ISA7" || error.contains("BLK-5") {
        (
            "ISA 0.8 R generic trap cannot report typed faults while retaining reversible prefix history; BLK-5 (ISA-7)",
            "R fault C and implicit trap-to-code table, as specified by ISA 0.9 K5; keep the accepted ISA target 0.8 until a contract upgrade",
        )
    } else if error.contains("bennett-tier") && error.contains("Unknown command line") {
        (
            "Plugin does not register §19.2 tier/entry options; this is an implementation dependency, not a musl or typed-fault verdict",
            "Plugin must implement whole-program R entry, CC bennett.argv argc/argv/envp launch and §25.1 reports; bp-xkg",
        )
    } else if code == "BD-E-NATIVE-MARKERS" {
        (
            "§17.7 actual plugin-materialised device retains host-side quantum/effect marker calls",
            "bp-xyn: publish marker-free materialised comparison variants; never define fake markers or substitute the source module",
        )
    } else if code == "BD-E-NATIVE-LAYOUT" || error.contains("BD-E-NATIVE-LAYOUT") {
        (
            "§19.5 native and device data/global/function/heap/arena/interface addresses must agree",
            "bennett-driver-cyg.3 / bp-xyn: supply the resolved shared comparison layout and LLVM symbol map; never infer it from __bennett_rt_blk.<f>",
        )
    } else if code == "BD-E-VERSION" {
        (
            "§19.8/19.9: same target data layout/triple, readable envelope major, exact dialect/ISA/plugin identity and requested hashes",
            "Supply matching tools, inputs and pinned libraries; never silently upgrade ISA or substitute library bytes",
        )
    } else if error.contains("native") || error.contains("comparison") {
        (
            "§17.7/19.5: comparison must resolve the materialised module with runtimes/arith and no host libc/libm",
            "Inspect the exact native imports/link diagnostics and resolved device layout; bp-xyn / bennett-driver-cyg.3. Full ASan/general-memory detection remains brt-nuu.2; UBSan source diagnostics are separate",
        )
    } else {
        (
            "§19 inputs/options and §25 fail-loud implementation obligations",
            "Provide the required input or implement the named capability; its North-Star scope remains required",
        )
    };
    let row = |code: &str, reason: &str, constraint: &str, change: &str| {
        obj([
            ("code", code.into()),
            ("reason", reason.into()),
            ("stage", stage.into()),
            ("function", "<whole-program>".into()),
            ("value_or_call", "<see diagnostic>".into()),
            ("constraint", constraint.into()),
            ("required_change", change.into()),
            ("diagnostic", error.into()),
        ])
    };
    let mut rows = vec![row(code, error, constraint, change)];
    let mut text =
        format!("{code} <whole-program> <see diagnostic>: {error}; {constraint}; {change}\n");
    if args.iter().any(|s| s.ends_with("bennett-tier=reversible")) && code != "BD-B-ISA7" {
        let reason = "§25.1: every §19.2 R entry has mandatory §17.6 budget checks; successful R paths are not waived";
        let constraint =
            "ISA 0.8 has only generic R trap; BLK-5 (ISA-7) typed R fault reporting is unavailable";
        let change = "R fault C with reversible prefix history and implicit cause-to-code table (ISA 0.9 K5); no silent ISA upgrade";
        rows.push(row("BD-B-ISA7", reason, constraint, change));
        text.push_str(&format!(
            "BD-B-ISA7 <R-entry> <budget-check>: {reason}; {constraint}; BLK-5 (ISA-7) {change}\n"
        ));
    }
    let json = Json::Array(rows).encode() + "\n";
    if let Some(out) = out {
        fs::create_dir_all(out).map_err(|e| format!("report directory {}: {e}", out.display()))?;
        write(out.join("blockers.json"), &json)?;
        write(out.join("blockers.txt"), text)?;
    }
    eprintln!("{json}");
    Ok(())
}
