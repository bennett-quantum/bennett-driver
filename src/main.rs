mod arith;
mod classifier;
mod json;
mod native;
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
const DIALECT: &str = "0.2.10";
const ISA: &str = "0.8";
const IDENTITY: &str = "dialect-0.2.10;isa-0.8";
const HELP: &str = "bennett-driver: external whole-program LLVM driver\nRequired: -bennett-dialect=0.2.10 -bennett-out=DIR INPUT.{c,bc,ll}...\nOptions: --bennett-llvm-major=18|23 (default 23), -bennett-isa=0.8,\n --bennett-plugin=FILE --bennett-runtimes=FILE --bennett-arith=FILE\n --bennett-{plugin,runtimes,arith}-sha256=HEX --bennett-pipeline=lto<O3>\n --bennett-tier=reversible --bennett-entry=SYMBOL\n -bennett-budget-default=s,h,st,d,ss -bennett-budgets=FILE\n --bennett-comparison=true or --bennett-materialised=DIR/device.bc\n --bennett-comparison-layout=FILE (resolved layout; defaults to adjacent launches)\n --bennett-native-support=FILE --bennett-native-support-sha256=HEX\n --bennett-native-input=FILE --bennett-comparison-record=FILE\n --bennett-classifier-input=FILE (original C, UBSan-minimal diagnostic)\n Plain O2 comparison and O0 diagnostic; full ASan blocked on brt-nuu.2\n";
#[derive(Debug)]
struct Options {
    values: BTreeMap<String, String>,
    inputs: Vec<PathBuf>,
    plugin_args: Vec<String>,
}
impl Options {
    fn parse(args: &[String]) -> Result<Self> {
        let mut o = Self {
            values: BTreeMap::new(),
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
                let (key, value) = clean
                    .split_once('=')
                    .ok_or_else(|| format!("BD-E-INPUT: option requires =value: {arg}"))?;
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
                        | "bennett-materialised"
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
                );
                if !driver && !pass {
                    return Err(format!(
                        "BD-E-INPUT: unimplemented driver option {arg}; capability remains required by dialect §19"
                    ));
                }
                if value.is_empty() {
                    return Err(format!("BD-E-INPUT: empty option {key}"));
                }
                if o.values.insert(key.into(), value.into()).is_some() {
                    return Err(format!("BD-E-INPUT: empty or duplicate option {key}"));
                }
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
        if o.get("bennett-dialect") != Some(DIALECT) || o.get("bennett-isa").unwrap_or(ISA) != ISA {
            return Err("BD-E-VERSION: required dialect 0.2.10 and ISA 0.8".into());
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
fn headless(cmd: &mut Command) {
    for key in [
        "DISPLAY",
        "WAYLAND_DISPLAY",
        "DBUS_SESSION_BUS_ADDRESS",
        "BROWSER",
    ] {
        cmd.env_remove(key);
    }
    cmd.env(
        "TMPDIR",
        Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap()
            .join("bennett-driver/.tmp"),
    );
}
fn sha(path: &Path) -> Result<String> {
    let mut c = Command::new("sha256sum");
    c.arg("--").arg(path);
    headless(&mut c);
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
        headless(&mut c);
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
fn sysroot_flags(o: &Options) -> Result<Vec<String>> {
    match o.get("bennett-sysroot") {
        None => Ok(vec![]),
        Some(p) => {
            let p = absolute(p)?;
            Ok(vec![
                format!("--sysroot={}", p.display()),
                "-nostdinc".into(),
                "-isystem".into(),
                p.join("include").display().to_string(),
            ])
        }
    }
}
fn tool(major: u32, name: &str) -> String {
    format!("/usr/lib/llvm-{major}/bin/{name}")
}
fn identity(b: &mut Build, plugin: &Path, major: u32) -> Result<()> {
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
    if id.trim() != IDENTITY {
        return Err(format!(
            "BD-E-VERSION: plugin identity {:?}, expected {IDENTITY}",
            id.trim()
        ));
    }
    Ok(())
}
fn execute(o: &Options, b: &mut Build) -> Result<()> {
    let m = o.major()?;
    let ws = Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap();
    let library =
        |key: &str, default: PathBuf| absolute(o.get(key).map(PathBuf::from).unwrap_or(default));
    let runtime = library(
        "bennett-runtimes",
        ws.join(format!("bennett-runtimes/dist/llvm{m}/bennett-runtimes.bc")),
    )?;
    let arith = library(
        "bennett-arith",
        ws.join(format!("bennett-arith/dist/llvm{m}/bennett-arith.bc")),
    )?;
    let plugin = library(
        "bennett-plugin",
        ws.join(format!("bennett-plugin/build/libbennett-plugin-{m}.so")),
    )?;
    for (key, p) in [
        ("runtimes", &runtime),
        ("arith", &arith),
        ("plugin", &plugin),
    ] {
        b.record
            .set(key, artifact(p, o.get(&format!("bennett-{key}-sha256")))?);
    }
    identity(b, &plugin, m)?;
    // Identity was obtained from the exported ABI, not a string search in the .so.
    let mut p = artifact(&plugin, None)?;
    p.set("identity", IDENTITY.into());
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
                frontend.extend(sysroot_flags(o)?);
                b.run("frontend", frontend, None)?;
                out
            }
            "bc" | "ll" => p,
            _ => {
                return Err(format!(
                    "BD-E-INPUT: unsupported input {}: expected C or LLVM bitcode/IR; extraction of rlib/Julia sources remains a §19.1 obligation",
                    p.display()
                ));
            }
        };
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
        input_ir.push(ir);
        for (key, previous) in [
            ("target datalayout", &mut layout),
            ("target triple", &mut triple),
        ] {
            if let Some(line) = text.lines().find(|l| l.starts_with(key)) {
                if previous.as_ref().is_some_and(|s| s != line) {
                    return Err(format!(
                        "BD-E-VERSION: mismatched {key} in {}: {line}",
                        module.display()
                    ));
                }
                *previous = Some(line.to_string());
            }
        }
        modules.push(module.display().to_string());
    }
    b.record.set("inputs", Json::Array(inputs));
    let arith = arith::prepare(o, b, m, &arith, &input_ir)?;
    let linked = b.out.join("linked.bc");
    let post = b.out.join("postlink.bc");
    let mut link = vec![tool(m, "llvm-link")];
    link.extend(modules);
    link.extend([
        runtime.display().to_string(),
        arith.display().to_string(),
        "--only-needed".into(),
        "-o".into(),
        linked.display().to_string(),
    ]);
    b.run("runtime-link", link, None)?;
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
    close_libraries(
        b,
        m,
        "production-library-closure",
        &linked,
        &[&runtime, &arith],
    )?;
    process::prepare(o, b, m, &linked, &runtime, &arith)?;
    let pipeline = o.get("bennett-pipeline").unwrap_or("lto<O3>");
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
        format!("-bennett-dialect={DIALECT}"),
        format!("-bennett-isa={ISA}"),
        format!("-bennett-out={}", b.out.display()),
    ];
    pass.extend(o.plugin_args.clone());
    pass.extend(["-disable-output".into(), post.display().to_string()]);
    let blocked = match b.run("plugin", pass, Some(&arith)) {
        Ok(_) => None,
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
    let mut c = Command::new("python3");
    c.arg("-c")
        .arg(include_str!("../scripts/finalise-build.py"))
        .arg(&b.out);
    headless(&mut c);
    let result = c.output().map_err(|e| format!("build-record: {e}"))?;
    if !result.status.success() {
        return Err(format!(
            "build-record: {}",
            String::from_utf8_lossy(&result.stderr)
        ));
    }
    if let Some(e) = blocked {
        return Err(e);
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
        fs::create_dir_all(Path::new(env!("CARGO_MANIFEST_DIR")).join(".tmp"))
            .map_err(|e| e.to_string())?;
        let o = Options::parse(&args)?;
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
                ("dialect", DIALECT.into()),
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
}
