mod arith;
mod classifier;
mod json;
mod llvm_utility;
mod mode_preparation;
mod native;
mod native_adapter;
mod native_host;
mod output_paths;
mod process;
mod report;
use json::{Json, obj, strings};
use std::{
    collections::BTreeMap,
    env, fs,
    path::{Path, PathBuf},
    process::{Command, Stdio},
};
type Result<T> = std::result::Result<T, String>;
const DIALECT: &str = "0.2.13";
const ISA: &str = "0.8";
const HELP: &str = "bennett-driver: external whole-program LLVM driver\nRequired: -bennett-dialect=0.2.13 (historical 0.2.10 accepted explicitly) -bennett-out=DIR INPUT.{c,bc,ll}...\nOptions: --bennett-llvm-major=18|23 (default 23), -bennett-isa=0.8,\n --bennett-plugin=FILE --bennett-runtimes=FILE --bennett-arith=FILE\n --bennett-arith-generator=FILE --bennett-native-check=FILE --bennett-sysroot=DIR\n --bennett-{plugin,runtimes,arith}-sha256=HEX --bennett-pipeline=lto<O3>\n --bennett-tier=reversible --bennett-entry=SYMBOL\n --bennett-snapshot=FILE --bennett-class=NAME --bennett-vscale=V\n -bennett-closed-unit --bennett-oracle=SYMBOL (requires callable wrapper handoff)\n --bennett-emit=process-bitcode (preparation stage; manifest status prepared)\n -bennett-budget-default=s,h,st,d,ss -bennett-budgets=FILE\n --bennett-comparison=true or --bennett-materialised=DIR/device.bc\n --bennett-comparison-layout=FILE (resolved layout; defaults to adjacent launches)\n --bennett-comparison-entry=SYMBOL --bennett-comparison-launch-record=FILE\n --bennett-native-support=FILE --bennett-native-support-sha256=HEX\n --bennett-native-input=FILE --bennett-comparison-record=FILE\n --bennett-classifier-input=FILE (original C, UBSan-minimal diagnostic)\n Plain O2 comparison and O0 diagnostic; full ASan requires its freestanding runtime publication\n Environment: TMPDIR is required. External paths also accept BENNETT_DRIVER_ followed by\n PLUGIN, RUNTIMES, ARITH, ARITH_GENERATOR, NATIVE_CHECK, NATIVE_SUPPORT or SYSROOT.\n";
#[derive(Debug)]
struct Options {
    values: BTreeMap<String, String>,
    paths: BTreeMap<&'static str, PathBuf>,
    sysroot: Option<Sysroot>,
    inputs: Vec<PathBuf>,
    plugin_args: Vec<String>,
}
impl Options {
    fn parse(args: &[String]) -> Result<Self> {
        let mut o = Self {
            values: BTreeMap::new(),
            paths: BTreeMap::new(),
            sysroot: None,
            inputs: vec![],
            plugin_args: vec![],
        };
        let mut positional = false;
        for arg in args {
            if arg == "--" {
                positional = true;
                continue;
            }
            if !positional && arg.starts_with('-') {
                let clean = arg.trim_start_matches('-');
                let (key, value) = match clean.split_once('=') {
                    Some(pair) => pair,
                    None if matches!(clean, "bennett-closed-unit" | "bennett-warn-qstore") => {
                        (clean, "true")
                    }
                    None => return Err(format!("BD-E-INPUT: option requires =value: {arg}")),
                };
                let driver = matches!(
                    key,
                    "bennett-dialect"
                        | "bennett-isa"
                        | "bennett-out"
                        | "bennett-llvm-major"
                        | "bennett-plugin"
                        | "bennett-runtimes"
                        | "bennett-arith"
                        | "bennett-plugin-sha256"
                        | "bennett-runtimes-sha256"
                        | "bennett-arith-sha256"
                        | "bennett-arith-generator"
                        | "bennett-arith-generator-sha256"
                        | "bennett-pipeline"
                        | "bennett-emit"
                        | "bennett-materialised"
                        | "bennett-comparison-entry"
                        | "bennett-comparison-launch-record"
                        | "bennett-comparison-record"
                        | "bennett-comparison-output"
                        | "bennett-sysroot"
                        | "bennett-native-input"
                        | "bennett-native-backend"
                        | "bennett-native-support"
                        | "bennett-native-support-sha256"
                        | "bennett-native-check"
                        | "bennett-native-check-sha256"
                        | "bennett-classifier-input"
                        | "bennett-comparison-layout"
                        | "bennett-layout-data-base"
                        | "bennett-layout-text-base"
                        | "bennett-comparison"
                        | "bennett-argv-replies"
                );
                let pass = matches!(
                    key,
                    "bennett-budget-default"
                        | "bennett-analysis-budget-ms"
                        | "bennett-budgets"
                        | "bennett-tier"
                        | "bennett-entry"
                        | "bennett-disk"
                        | "bennett-oracle"
                        | "bennett-bind"
                        | "bennett-dev"
                        | "bennett-payload"
                        | "bennett-snapshot"
                        | "bennett-closed-unit"
                        | "bennett-platform"
                        | "bennett-platform-ram"
                        | "bennett-class"
                        | "bennett-vscale"
                        | "bennett-cpu"
                        | "bennett-qreg-instances"
                        | "bennett-inplace-exhaustive-bits"
                        | "bennett-warn-qstore"
                        | "bennett-arena-heap"
                );
                if !driver && !pass {
                    return Err(format!(
                        "BD-E-INPUT: unimplemented driver option {arg}; capability remains required by dialect §19"
                    ));
                }
                if value.is_empty() {
                    return Err(format!("BD-E-INPUT: empty option {key}"));
                }
                if matches!(key, "bennett-closed-unit" | "bennett-warn-qstore")
                    && !matches!(value, "true" | "false")
                {
                    return Err(format!("BD-E-INPUT: {key} requires true|false"));
                }
                let repeatable = matches!(key, "bennett-bind" | "bennett-dev" | "bennett-class");
                if o.values.contains_key(key) && !repeatable {
                    return Err(format!("BD-E-INPUT: empty or duplicate option {key}"));
                }
                o.values.entry(key.into()).or_insert_with(|| value.into());
                if pass {
                    o.plugin_args.push(format!(
                        "{}{}={value}",
                        if matches!(key, "bennett-tier" | "bennett-entry" | "bennett-disk") {
                            "--"
                        } else {
                            "-"
                        },
                        key
                    ));
                }
            } else {
                o.inputs.push(PathBuf::from(arg));
            }
        }
        let adapter = o.get("bennett-materialised").is_some();
        if let Some(emit) = o.get("bennett-emit")
            && (emit != "process-bitcode"
                || adapter
                || o.get("bennett-tier") != Some("reversible")
                || o.get("bennett-comparison") == Some("true"))
        {
            return Err("BD-E-INPUT: --bennett-emit=process-bitcode requires a reversible process entry and excludes materialised/comparison mode".into());
        }
        if adapter && o.get("bennett-dialect").is_none() {
            o.values.insert("bennett-dialect".into(), DIALECT.into());
        }
        if adapter && o.get("bennett-out").is_none() {
            let path = Path::new(o.get("bennett-materialised").unwrap())
                .parent()
                .unwrap_or(Path::new("."));
            let out = path.join("native-work").display().to_string();
            o.values.insert("bennett-out".into(), out);
        }
        if !matches!(o.get("bennett-dialect"), Some("0.2.10" | "0.2.13"))
            || o.get("bennett-isa").unwrap_or(ISA) != ISA
        {
            return Err(
                "BD-E-VERSION: required dialect 0.2.13 (or explicit historical 0.2.10) and ISA 0.8"
                    .into(),
            );
        }
        if o.get("bennett-out").is_none() || (o.inputs.is_empty() && !adapter) {
            return Err("BD-E-INPUT: -bennett-out and at least one input required".into());
        }
        o.major()?;
        if let Some(value) = o.get("bennett-comparison")
            && !matches!(value, "true" | "false")
        {
            return Err("BD-E-INPUT: --bennett-comparison=true|false required".into());
        }
        if o.get("bennett-pipeline")
            .is_some_and(|p| p.contains("view-"))
        {
            return Err("BD-E-INPUT: LLVM view-* is forbidden in headless mode".into());
        }
        if !adapter
            && o.get("bennett-comparison") != Some("true")
            && o.values.keys().any(|k| {
                matches!(
                    k.as_str(),
                    "bennett-native-input"
                        | "bennett-native-backend"
                        | "bennett-native-support"
                        | "bennett-native-support-sha256"
                        | "bennett-native-check"
                        | "bennett-native-check-sha256"
                        | "bennett-classifier-input"
                        | "bennett-comparison-layout"
                        | "bennett-comparison-entry"
                        | "bennett-comparison-launch-record"
                        | "bennett-comparison-record"
                        | "bennett-comparison-output"
                        | "bennett-layout-data-base"
                        | "bennett-layout-text-base"
                )
            })
        {
            return Err("BD-E-INPUT: comparison options require --bennett-comparison=true or --bennett-materialised".into());
        }
        if o.get("bennett-argv-replies").is_some() && o.get("bennett-tier") != Some("reversible") {
            return Err("BD-E-INPUT: argv replies require --bennett-tier=reversible".into());
        }
        if let Some(tier) = o.get("bennett-tier") {
            if tier != "reversible" || o.get("bennett-entry").is_none() {
                return Err("BD-E-INPUT: §19.2 requires --bennett-tier=reversible and --bennett-entry=SYMBOL".into());
            }
        } else if o.get("bennett-entry").is_some() {
            return Err("BD-E-INPUT: --bennett-entry requires --bennett-tier=reversible".into());
        }
        for key in [
            "bennett-plugin",
            "bennett-runtimes",
            "bennett-arith",
            "bennett-arith-generator",
            "bennett-native-check",
            "bennett-native-support",
        ] {
            if let Some(path) = resolve_path(&o, key)? {
                o.paths.insert(key, path);
            }
        }
        o.sysroot = resolve_path(&o, "bennett-sysroot")?
            .map(Sysroot::new)
            .transpose()?;
        Ok(o)
    }
    fn get(&self, key: &str) -> Option<&str> {
        self.values.get(key).map(String::as_str)
    }
    fn major(&self) -> Result<u32> {
        match self.get("bennett-llvm-major").unwrap_or("23") {
            "18" => Ok(18),
            "23" => Ok(23),
            v => Err(format!(
                "BD-E-VERSION: unsupported envelope LLVM major {v}; expected 18 or 23"
            )),
        }
    }
    fn dialect(&self) -> &str {
        self.get("bennett-dialect").unwrap()
    }
    fn required_sysroot(&self) -> Result<&Sysroot> {
        self.sysroot.as_ref().ok_or_else(|| {
            "BD-E-CONFIG: missing --bennett-sysroot=PATH or BENNETT_DRIVER_SYSROOT".into()
        })
    }
}
#[derive(Debug)]
struct Sysroot {
    root: PathBuf,
}
impl Sysroot {
    fn new(root: PathBuf) -> Result<Self> {
        fs::read_dir(root.join("include")).map_err(|e| {
            format!(
                "BD-E-CONFIG: unusable sysroot {}: cannot read include directory: {e}",
                root.display()
            )
        })?;
        Ok(Self { root })
    }
    fn link_flag(&self) -> String {
        format!("--sysroot={}", self.root.display())
    }
    fn frontend_flags(&self) -> Vec<String> {
        vec![
            self.link_flag(),
            "-nostdinc".into(),
            "-isystem".into(),
            self.root.join("include").display().to_string(),
        ]
    }
}
fn absolute(p: impl AsRef<Path>) -> Result<PathBuf> {
    let p = p.as_ref();
    if p.is_absolute() {
        Ok(p.into())
    } else {
        Ok(env::current_dir().map_err(|e| e.to_string())?.join(p))
    }
}
fn write(path: impl AsRef<Path>, content: impl AsRef<[u8]>) -> Result<()> {
    fs::write(path.as_ref(), content).map_err(|e| format!("write {}: {e}", path.as_ref().display()))
}
fn read(path: impl AsRef<Path>) -> Result<String> {
    fs::read_to_string(path.as_ref()).map_err(|e| format!("read {}: {e}", path.as_ref().display()))
}
fn configured_path(o: &Options, key: &str) -> Result<PathBuf> {
    o.paths.get(key).cloned().ok_or_else(|| {
        format!(
            "BD-E-CONFIG: missing --{key}=PATH or BENNETT_DRIVER_{}",
            key.trim_start_matches("bennett-")
                .to_uppercase()
                .replace('-', "_")
        )
    })
}
fn resolve_path(o: &Options, key: &str) -> Result<Option<PathBuf>> {
    let variable = format!(
        "BENNETT_DRIVER_{}",
        key.trim_start_matches("bennett-")
            .to_uppercase()
            .replace('-', "_")
    );
    let path = o
        .get(key)
        .map(PathBuf::from)
        .or_else(|| env::var_os(&variable).map(PathBuf::from));
    path.map(|path| {
        if path.as_os_str().is_empty() {
            return Err(format!(
                "BD-E-CONFIG: empty {variable}; provide --{key}=PATH or unset it"
            ));
        }
        absolute(path)
    })
    .transpose()
}
fn task_tmpdir() -> Result<PathBuf> {
    env::var_os("TMPDIR")
        .filter(|path| !path.is_empty())
        .map(PathBuf::from)
        .ok_or_else(|| "BD-E-CONFIG: missing TMPDIR; set it to a writable task directory".into())
}
fn headless(cmd: &mut Command) -> Result<()> {
    for key in [
        "DISPLAY",
        "WAYLAND_DISPLAY",
        "DBUS_SESSION_BUS_ADDRESS",
        "BROWSER",
    ] {
        cmd.env_remove(key);
    }
    cmd.env("TMPDIR", task_tmpdir()?);
    Ok(())
}
fn sha(path: &Path) -> Result<String> {
    let mut c = Command::new("sha256sum");
    c.arg("--").arg(path);
    headless(&mut c)?;
    let o = c.output().map_err(|e| format!("sha256sum: {e}"))?;
    if !o.status.success() {
        return Err(format!(
            "BD-E-INPUT: hash {}: {}",
            path.display(),
            String::from_utf8_lossy(&o.stderr)
        ));
    }
    Ok(String::from_utf8_lossy(&o.stdout)
        .split_whitespace()
        .next()
        .ok_or("empty sha256sum")?
        .to_string())
}
fn artifact(path: &Path, pin: Option<&str>) -> Result<Json> {
    let digest = sha(path)?;
    if pin.is_some_and(|p| p != digest) {
        return Err(format!(
            "BD-E-VERSION: SHA-256 mismatch for {}: actual {digest}, expected {}",
            path.display(),
            pin.unwrap()
        ));
    }
    Ok(obj([
        ("path", path.display().to_string().into()),
        ("sha256", digest.into()),
    ]))
}
struct Build {
    out: PathBuf,
    record: Json,
    commands: Vec<Json>,
}
impl Build {
    fn save(&mut self, status: &str) -> Result<()> {
        self.record.set("status", status.into());
        self.record
            .set("commands", Json::Array(self.commands.clone()));
        write(self.out.join("manifest.json"), self.record.encode() + "\n")
    }
    fn run(&mut self, stage: &str, argv: Vec<String>, arith: Option<&Path>) -> Result<String> {
        let mut c = Command::new(&argv[0]);
        c.args(&argv[1..]).stdin(Stdio::null());
        headless(&mut c)?;
        // No caller environment may silently override the library recorded by the driver.
        c.env_remove("BENNETT_ARITH_BITCODE");
        if let Some(p) = arith {
            c.env("BENNETT_ARITH_BITCODE", p);
        }
        let result = c
            .output()
            .map_err(|e| format!("{stage}: cannot execute {}: {e}", argv[0]))?;
        let stdout = String::from_utf8_lossy(&result.stdout).to_string();
        let stderr = String::from_utf8_lossy(&result.stderr).to_string();
        let number = self.commands.len();
        write(
            self.out.join(format!("{number:03}-{stage}.stdout")),
            &result.stdout,
        )?;
        write(
            self.out.join(format!("{number:03}-{stage}.stderr")),
            &result.stderr,
        )?;
        self.commands.push(obj([
            ("stage", stage.into()),
            ("argv", strings(&argv)),
            ("success", result.status.success().into()),
            ("stdout", stdout.clone().into()),
            ("stderr", stderr.clone().into()),
        ]));
        self.save("running")?;
        if !result.status.success() {
            return Err(format!(
                "{stage}: command exited {}: {}",
                result.status, stderr
            ));
        }
        Ok(stdout)
    }
}
/// Resolve imports introduced by later libraries before instrumenting globals
/// or normalising callers. A single ordered --only-needed pass is insufficient
/// when arithmetic introduces a runtime state dependency such as fenv.
fn close_libraries(
    b: &mut Build,
    major: u32,
    stage: &str,
    module: &Path,
    libraries: &[&Path],
) -> Result<()> {
    let mut previous = None;
    loop {
        let imports = b.run(
            &format!("{stage}-imports"),
            vec![
                tool(major, "llvm-nm"),
                "--undefined-only".into(),
                module.display().to_string(),
            ],
            None,
        )?;
        if previous.as_ref() == Some(&imports) {
            return Ok(());
        }
        previous = Some(imports);
        let mut args = vec![tool(major, "llvm-link"), module.display().to_string()];
        args.extend(libraries.iter().map(|p| p.display().to_string()));
        args.extend([
            "--only-needed".into(),
            "-o".into(),
            module.display().to_string(),
        ]);
        b.run(stage, args, None)?;
    }
}
fn tool(major: u32, name: &str) -> String {
    format!("/usr/lib/llvm-{major}/bin/{name}")
}
fn identity(b: &mut Build, plugin: &Path, major: u32, dialect: &str) -> Result<()> {
    let id = b.run(
        "plugin-identity",
        vec![
            "python3".into(),
            "-c".into(),
            include_str!("../scripts/plugin-identity.py").into(),
            plugin.display().to_string(),
            format!("/usr/lib/llvm-{major}/lib/libLLVM.so"),
        ],
        None,
    )?;
    let expected = format!("dialect-{dialect};isa-{ISA}");
    if id.trim() != expected {
        return Err(format!(
            "BD-E-VERSION: plugin identity {:?}, expected {expected}",
            id.trim()
        ));
    }
    Ok(())
}
fn admit_dialect_flag(ir: &str, expected: &str) -> Result<()> {
    // This is opt's verified, canonical IR. Only tuples referenced by the
    // module-flags list are authoritative, not arbitrary debug metadata.
    if let Some(flags) = ir
        .lines()
        .find_map(|line| line.strip_prefix("!llvm.module.flags = !{"))
    {
        for id in flags
            .trim_end_matches('}')
            .split(", ")
            .filter(|id| !id.is_empty())
        {
            let prefix = format!("{id} = ");
            let tuple = ir
                .lines()
                .find_map(|line| line.strip_prefix(&prefix))
                .ok_or("BD-E-VERSION: missing verified module-flag tuple")?;
            if let Some((_, value)) = tuple.split_once(", !\"bennett.dialect\", ")
                && value.trim_end_matches('}').trim() != format!("!\"{expected}\"")
            {
                return Err(format!(
                    "BD-E-VERSION: bennett.dialect module flag {value} differs from {expected}"
                ));
            }
        }
    }
    Ok(())
}
fn execute(o: &Options, b: &mut Build) -> Result<()> {
    let m = o.major()?;
    let runtime = configured_path(o, "bennett-runtimes")?;
    let arith = configured_path(o, "bennett-arith")?;
    let plugin = configured_path(o, "bennett-plugin")?;
    for (key, p) in [
        ("runtimes", &runtime),
        ("arith", &arith),
        ("plugin", &plugin),
    ] {
        b.record
            .set(key, artifact(p, o.get(&format!("bennett-{key}-sha256")))?);
    }
    identity(b, &plugin, m, o.dialect())?;
    // Identity was obtained from the exported ABI, not a string search in the .so.
    let mut p = artifact(&plugin, None)?;
    p.set(
        "identity",
        format!("dialect-{};isa-{ISA}", o.dialect()).into(),
    );
    b.record.set("plugin", p);
    let mut versions = vec![];
    for name in ["clang", "llvm-link", "opt"] {
        let v = b.run(
            &format!("version-{name}"),
            vec![tool(m, name), "--version".into()],
            None,
        )?;
        if !v.contains(&format!("version {m}.")) && !v.contains(&format!("LLD {m}.")) {
            return Err(format!("BD-E-VERSION: {name} is not LLVM {m}: {v}"));
        }
        versions.push((name, v.into()));
    }
    b.record.set("tools", obj(versions));
    if let Some(file) = o.get("bennett-budgets") {
        b.record
            .set("budget_input", artifact(&absolute(file)?, None)?);
    }
    if let Some(file) = o.get("bennett-argv-replies") {
        b.record
            .set("argv_replies", artifact(&absolute(file)?, None)?);
    }
    if let Some(file) = o.get("bennett-disk") {
        b.record.set("disk", artifact(&absolute(file)?, None)?);
    }
    if let Some(file) = o.get("bennett-snapshot") {
        b.record.set("snapshot", artifact(&absolute(file)?, None)?);
    }
    let mut inputs = vec![];
    let mut modules = vec![];
    let mut input_ir = vec![];
    let mut layout = None;
    let mut triple = None;
    for (i, p) in o.inputs.iter().enumerate() {
        let p = absolute(p)?;
        inputs.push(artifact(&p, None)?);
        let ext = p.extension().and_then(|v| v.to_str()).unwrap_or("");
        let module = match ext {
            "c" => {
                let out = b.out.join(format!("input-{i}.bc"));
                let mut frontend = vec![
                    tool(m, "clang"),
                    "-O2".into(),
                    "-flto".into(),
                    "-emit-llvm".into(),
                    "-c".into(),
                    p.display().to_string(),
                    "-o".into(),
                    out.display().to_string(),
                ];
                if let Some(sysroot) = &o.sysroot {
                    frontend.extend(sysroot.frontend_flags());
                }
                b.run("frontend", frontend, None)?;
                out
            }
            "bc" | "ll" => p,
            "o" | "a" => {
                return Err(format!(
                    "BD-B-NATIVE-INPUT: {} requires the mixed native/VM host link, deferred under bennett-4ht and bennett-driver-116; no partial output was linked",
                    p.display()
                ));
            }
            _ => {
                return Err(format!(
                    "BD-E-INPUT: unsupported input {}: expected C or LLVM bitcode/IR; extraction of rlib/Julia sources remains a §19.1 obligation",
                    p.display()
                ));
            }
        };
        // opt may infer a missing DataLayout from a triple. Inspect the input
        // before any optimisation/target-machine defaults can fill it in.
        let declared = if module.extension().and_then(|e| e.to_str()) == Some("ll") {
            read(&module)?
        } else {
            b.run(
                "input-target",
                vec![
                    tool(m, "llvm-dis"),
                    module.display().to_string(),
                    "-o".into(),
                    "-".into(),
                ],
                None,
            )
            .map_err(|error| {
                format!(
                    "BD-E-VERSION: cannot read target metadata in {}: {error}",
                    module.display()
                )
            })?
        };
        for field in ["target triple", "target datalayout"] {
            let present = declared.lines().map(str::trim_start).any(|line| {
                line.starts_with(field)
                    && line.split_once('=').is_some_and(|(_, value)| {
                        value
                            .trim_start()
                            .strip_prefix('"')
                            .and_then(|value| value.split_once('"'))
                            .is_some_and(|(target, _)| !target.is_empty())
                    })
            });
            if !present {
                return Err(format!(
                    "BD-E-VERSION: missing {field} in {}; every input must declare its target before linking",
                    module.display()
                ));
            }
        }
        let ir = b.out.join(format!("input-{i}.ll"));
        b.run(
            "input-verify",
            vec![
                tool(m, "opt"),
                "-passes=verify".into(),
                "-S".into(),
                module.display().to_string(),
                "-o".into(),
                ir.display().to_string(),
            ],
            None,
        )
        .map_err(|e| {
            format!(
                "BD-E-VERSION: LLVM {m} cannot read/verify {}: {e}",
                module.display()
            )
        })?;
        let text = read(&ir)?;
        admit_dialect_flag(&text, o.get("bennett-dialect").unwrap())?;
        input_ir.push(ir.clone());
        for (key, previous) in [
            ("target datalayout", &mut layout),
            ("target triple", &mut triple),
        ] {
            let line = text.lines().find(|line| line.starts_with(key)).ok_or_else(|| {
                format!("BD-E-VERSION: missing {key} in {}; every input must declare its target before linking", module.display())
            })?;
            if previous.as_ref().is_some_and(|s| s != line) {
                return Err(format!(
                    "BD-E-VERSION: mismatched {key} in {}: {line}",
                    module.display()
                ));
            }
            *previous = Some(line.to_string());
        }
        let verified = b.out.join(format!("input-{i}-verified.bc"));
        b.run(
            "input-bitcode",
            vec![
                tool(m, "llvm-as"),
                ir.display().to_string(),
                "-o".into(),
                verified.display().to_string(),
            ],
            None,
        )?;
        modules.push(verified.display().to_string());
    }
    b.record.set("inputs", Json::Array(inputs));
    let pipeline = o.get("bennett-pipeline").unwrap_or("lto<O3>");
    b.record.set("pipeline", pipeline.into());
    let process_entry = o.get("bennett-tier") == Some("reversible");
    // Marker calls and reserved runtime names are the dialect's entry to the
    // device pipeline. Inspect source modules before adding device libraries;
    // ordinary host libc must never become a selected device closure.
    let mut reserved_symbols = false;
    for module in &modules {
        let symbols = b.run(
            "input-symbols",
            vec![tool(m, "llvm-nm"), "--format=posix".into(), module.clone()],
            None,
        )?;
        reserved_symbols |= symbols.lines().any(|line| {
            line.split_whitespace()
                .next()
                .is_some_and(|name| name.starts_with("__bennett_"))
        });
    }
    let modules = mode_preparation::prepare(o, b, m, &modules, mode_preparation::Phase::Source)?;
    let device_mode = process_entry
        || ["bennett-oracle", "bennett-platform"]
            .iter()
            .any(|key| o.get(key).is_some());
    if !device_mode && !reserved_symbols {
        native_host::build(o, b, m, &modules, pipeline)?;
        return finalise_build(b);
    }
    // Oracle synthesis must preserve an internal program root before LTO and
    // establish the callable register ownership; a late flag cannot restore it.
    let preparation = ["bennett-oracle"]
        .into_iter()
        .filter(|key| o.get(key).is_some())
        .collect::<Vec<_>>();
    if !preparation.is_empty() {
        return Err(format!(
            "BD-B-MODE-BACKEND: {} requires a published descriptor/root, initializer or vscale preparation handoff before post-link optimisation; requested options and input hashes are retained, no unchanged build is certified",
            preparation.join(", ")
        ));
    }
    let arith = arith::prepare(o, b, m, &arith, &input_ir)?;
    let linked = b.out.join("linked.bc");
    let post = b.out.join("postlink.bc");
    let mut link = vec![tool(m, "llvm-link")];
    link.extend(modules);
    if !process_entry {
        link.extend([
            runtime.display().to_string(),
            arith.display().to_string(),
            "--only-needed".into(),
        ]);
    }
    link.extend(["-o".into(), linked.display().to_string()]);
    b.run(
        if process_entry {
            "process-input-link"
        } else {
            "runtime-link"
        },
        link,
        None,
    )?;
    let instances = b.out.join("arith-instances/bennett-arith.bc");
    if instances.is_file() {
        b.run(
            "arith-instance-roots",
            vec![
                tool(m, "llvm-link"),
                linked.display().to_string(),
                format!("--override={}", instances.display()),
                "-o".into(),
                linked.display().to_string(),
            ],
            None,
        )?;
    }
    if process_entry {
        process::prepare(o, b, m, &linked, &runtime, &arith)?;
    } else {
        close_libraries(
            b,
            m,
            "production-library-closure",
            &linked,
            &[&runtime, &arith],
        )?;
    }
    let mut prepared_path = b.out.join("process-prepared.bc");
    if o.get("bennett-vscale").is_some() {
        let modules = mode_preparation::prepare(
            o,
            b,
            m,
            &[linked.display().to_string()],
            mode_preparation::Phase::Linked,
        )?;
        prepared_path = PathBuf::from(&modules[0]);
        fs::copy(&prepared_path, &linked).map_err(|e| format!("mode prepared module: {e}"))?;
    }
    if o.get("bennett-emit") == Some("process-bitcode") {
        b.record
            .set("completion", "process-bitcode preparation stage".into());
        b.record.set(
            "outputs",
            obj([("process_prepared", artifact(&prepared_path, None)?)]),
        );
        return b.save("prepared");
    }
    b.run(
        "postlink",
        vec![
            tool(m, "opt"),
            format!("-passes={pipeline}"),
            linked.display().to_string(),
            "-o".into(),
            post.display().to_string(),
        ],
        None,
    )?;
    let mut pass = vec![
        tool(m, "opt"),
        format!("-load-pass-plugin={}", plugin.display()),
        "-passes=bennett".into(),
        format!("-bennett-dialect={}", o.dialect()),
        format!("-bennett-isa={ISA}"),
        format!("-bennett-out={}", b.out.display()),
    ];
    pass.extend(o.plugin_args.clone());
    pass.retain(|arg| {
        !["-bennett-class=", "-bennett-vscale=", "-bennett-snapshot="]
            .iter()
            .any(|prefix| arg.starts_with(prefix))
    });
    pass.extend(["-disable-output".into(), post.display().to_string()]);
    let blocked = match b.run("plugin", pass, Some(&arith)) {
        Ok(_) => None,
        Err(e) if e.contains("Unknown command line argument") => {
            return Err(format!(
                "BD-B-MODE-BACKEND: published dialect §19/20 control has no registered backend; selected plugin and complete argv are recorded, no unchanged build is certified. Required control implementation or published driver/backend handoff: {e}"
            ));
        }
        Err(e) if e.contains("BD-B-") => Some(e),
        Err(e) => return Err(e),
    };
    for name in ["device.bc", "host.bc", "launches.json"] {
        if !b.out.join(name).is_file() {
            return Err(format!(
                "plugin returned success without §19.9 output {name}"
            ));
        }
    }
    for name in ["device.bc", "host.bc"] {
        b.run(
            "output-verify",
            vec![
                tool(m, "opt"),
                "-passes=verify".into(),
                "-disable-output".into(),
                b.out.join(name).display().to_string(),
            ],
            None,
        )?;
    }
    b.record.set(
        "outputs",
        obj([
            ("linked", artifact(&linked, None)?),
            ("postlink", artifact(&post, None)?),
            ("device", artifact(&b.out.join("device.bc"), None)?),
            ("host", artifact(&b.out.join("host.bc"), None)?),
        ]),
    );
    if let Some(ref e) = blocked {
        b.record.set("error", e.clone().into());
    }
    b.save(if blocked.is_some() {
        "blocked"
    } else {
        "complete"
    })?;
    finalise_build(b)?;
    if let Some(e) = blocked {
        return Err(e);
    }
    Ok(())
}
fn finalise_build(b: &Build) -> Result<()> {
    let mut c = Command::new("python3");
    c.arg("-c")
        .arg(include_str!("../scripts/finalise-build.py"))
        .arg(&b.out);
    headless(&mut c)?;
    let result = c.output().map_err(|e| format!("build-record: {e}"))?;
    if !result.status.success() {
        return Err(format!(
            "build-record: {}",
            String::from_utf8_lossy(&result.stderr)
        ));
    }
    Ok(())
}
fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    if args == ["--help"] {
        print!("{HELP}");
        return;
    }
    if args == ["--version"] {
        println!("bennett-driver {}", env!("CARGO_PKG_VERSION"));
        return;
    }
    let mut report_written = false;
    let result = (|| -> Result<()> {
        let o = Options::parse(&args)?;
        fs::create_dir_all(task_tmpdir()?).map_err(|e| format!("BD-E-CONFIG: TMPDIR: {e}"))?;
        let out = absolute(o.get("bennett-out").unwrap())?;
        if out.exists()
            && fs::read_dir(&out)
                .map_err(|e| e.to_string())?
                .next()
                .is_some()
        {
            return Err(format!(
                "BD-E-INPUT: output directory {} must be empty to exclude stale artefacts",
                out.display()
            ));
        }
        fs::create_dir_all(&out).map_err(|e| e.to_string())?;
        let mut b = Build {
            out,
            commands: vec![],
            record: obj([
                ("schema", "bennett-driver-build-1".into()),
                ("driver_version", env!("CARGO_PKG_VERSION").into()),
                ("dialect", o.dialect().into()),
                ("isa", ISA.into()),
                ("llvm_major", o.major()?.into()),
                ("options", strings(&args)),
            ]),
        };
        let r = if o.get("bennett-materialised").is_some() {
            native::compare(&o, &mut b)
        } else {
            execute(&o, &mut b).and_then(|()| {
                if o.get("bennett-comparison") == Some("true") {
                    native::compare(&o, &mut b)
                } else {
                    Ok(())
                }
            })
        };
        if let Err(ref e) = r {
            b.record.set("error", e.clone().into());
            b.save(if e.contains("BD-B-") {
                "blocked"
            } else {
                "failed"
            })?;
            let stage = b
                .commands
                .last()
                .and_then(|v| {
                    if let Json::Object(m) = v {
                        if let Some(Json::Str(s)) = m.get("stage") {
                            Some(s.as_str())
                        } else {
                            None
                        }
                    } else {
                        None
                    }
                })
                .unwrap_or("input");
            report::failure(
                Some(&b.out),
                e,
                if e.starts_with("plugin:") {
                    "plugin"
                } else {
                    stage
                },
                &args,
            )?;
            report_written = true;
        }
        r
    })();
    if let Err(e) = result {
        if !report_written {
            // Never overwrite an earlier build's evidence for a stale directory.
            let hint = args
                .iter()
                .find_map(|a| a.trim_start_matches('-').strip_prefix("bennett-out="));
            let out = hint
                .and_then(|s| absolute(s).ok())
                .filter(|p| !p.exists() || fs::read_dir(p).is_ok_and(|mut d| d.next().is_none()));
            if let Err(r) = report::failure(out.as_deref(), &e, "arguments", &args) {
                eprintln!("report failure: {r}");
            }
        }
        eprintln!("bennett-driver: {e}");
        std::process::exit(1);
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    fn parse(a: &[&str]) -> Result<Options> {
        Options::parse(&a.iter().map(|s| s.to_string()).collect::<Vec<_>>())
    }
    #[test]
    fn unknown_and_duplicate_options_fail() {
        assert!(parse(&["--ignored=yes"]).is_err());
        assert!(
            parse(&[
                "-bennett-dialect=0.2.10",
                "-bennett-out=o",
                "--bennett-argv-replies=replies.json",
                "x.bc"
            ])
            .is_err()
        );
        assert!(parse(&["-bennett-dialect=0.2.10", "-bennett-dialect=0.2.10"]).is_err());
    }
    #[test]
    fn analysis_wall_clock_allowance_is_explicit_and_forwarded() {
        let o = parse(&[
            "-bennett-dialect=0.2.10",
            "-bennett-out=o",
            "--bennett-analysis-budget-ms=300000",
            "x.bc",
        ])
        .unwrap();
        assert!(
            o.plugin_args
                .contains(&"-bennett-analysis-budget-ms=300000".to_string())
        );
    }
    #[test]
    fn defaults_choose_newest_envelope() {
        assert_eq!(
            parse(&["-bennett-dialect=0.2.10", "-bennett-out=o", "x.bc"])
                .unwrap()
                .major()
                .unwrap(),
            23
        );
    }
    #[test]
    fn process_bitcode_stage_has_explicit_scope() {
        let base = [
            "-bennett-dialect=0.2.10",
            "-bennett-out=o",
            "--bennett-emit=process-bitcode",
            "x.bc",
        ];
        assert!(parse(&base).is_err());
        let mut args = base.to_vec();
        args.extend(["--bennett-tier=reversible", "--bennett-entry=main"]);
        assert_eq!(
            parse(&args).unwrap().get("bennett-emit"),
            Some("process-bitcode")
        );
        args.push("--bennett-comparison=true");
        assert!(parse(&args).is_err());
    }
}
