mod arith;
mod classifier;
mod json;
mod llvm_utility;
mod mode_preparation;
mod native;
mod native_adapter;
mod native_host;
mod options;
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
use options::{Emission, OptionKey, Options, Tier};
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
fn configured_path(o: &Options, key: OptionKey) -> Result<PathBuf> {
    o.paths.get(&key).cloned().ok_or_else(|| {
        format!(
            "BD-E-CONFIG: missing --{key}=PATH or BENNETT_DRIVER_{}",
            key.as_str()
                .trim_start_matches("bennett-")
                .to_uppercase()
                .replace('-', "_")
        )
    })
}
fn resolve_path(o: &Options, key: OptionKey) -> Result<Option<PathBuf>> {
    let variable = format!(
        "BENNETT_DRIVER_{}",
        key.as_str()
            .trim_start_matches("bennett-")
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
struct Environment {
    m: u32,
    runtime: PathBuf,
    arith: PathBuf,
    plugin: PathBuf,
}
struct AdmittedInputs {
    modules: Vec<String>,
    input_ir: Vec<PathBuf>,
}
struct LinkedProgram {
    arith: PathBuf,
    linked: PathBuf,
    prepared_path: PathBuf,
}
impl Environment {
    fn inspect(o: &Options, b: &mut Build) -> Result<Self> {
        let m = o.major;
        let runtime = configured_path(o, OptionKey::Runtimes)?;
        let arith = configured_path(o, OptionKey::Arith)?;
        let plugin = configured_path(o, OptionKey::Plugin)?;
        for (key, pin, p) in [
            ("runtimes", OptionKey::RuntimesSha256, &runtime),
            ("arith", OptionKey::ArithSha256, &arith),
            ("plugin", OptionKey::PluginSha256, &plugin),
        ] {
            b.record.set(key, artifact(p, o.get(pin))?);
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
        if let Some(file) = o.get(OptionKey::Budgets) {
            b.record
                .set("budget_input", artifact(&absolute(file)?, None)?);
        }
        if let Some(file) = o.get(OptionKey::ArgvReplies) {
            b.record
                .set("argv_replies", artifact(&absolute(file)?, None)?);
        }
        if let Some(file) = o.get(OptionKey::Disk) {
            b.record.set("disk", artifact(&absolute(file)?, None)?);
        }
        if let Some(file) = o.get(OptionKey::Snapshot) {
            b.record.set("snapshot", artifact(&absolute(file)?, None)?);
        }
        Ok(Self {
            m,
            runtime,
            arith,
            plugin,
        })
    }
    fn link(
        &self,
        o: &Options,
        b: &mut Build,
        inputs: AdmittedInputs,
        process_entry: bool,
    ) -> Result<LinkedProgram> {
        let Self {
            m, runtime, arith, ..
        } = self;
        let m = *m;
        let AdmittedInputs { modules, input_ir } = inputs;
        let arith = arith::prepare(o, b, m, arith, &input_ir)?;
        let linked = b.out.join("linked.bc");
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
            process::prepare(o, b, m, &linked, runtime, &arith)?;
        } else {
            close_libraries(
                b,
                m,
                "production-library-closure",
                &linked,
                &[runtime, &arith],
            )?;
        }
        let mut prepared_path = b.out.join("process-prepared.bc");
        if o.get(OptionKey::Vscale).is_some() {
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
        Ok(LinkedProgram {
            arith,
            linked,
            prepared_path,
        })
    }
    fn lower(&self, o: &Options, b: &mut Build, program: LinkedProgram) -> Result<()> {
        let m = self.m;
        let plugin = &self.plugin;
        let pipeline = &o.pipeline;
        let LinkedProgram { arith, linked, .. } = program;
        let post = b.out.join("postlink.bc");
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
        pass.extend(
            o.plugin_args
                .iter()
                .filter(|arg| {
                    !matches!(
                        arg.key,
                        OptionKey::Class | OptionKey::Vscale | OptionKey::Snapshot
                    )
                })
                .map(ToString::to_string),
        );
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
}
fn admit_inputs(o: &Options, b: &mut Build, m: u32) -> Result<AdmittedInputs> {
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
                    "BD-B-NATIVE-INPUT: {} requires the mixed native/VM host link, pending the published mixed-container and host-entry ABI; no partial output was linked",
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
        admit_dialect_flag(&text, o.get(OptionKey::Dialect).unwrap())?;
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
    Ok(AdmittedInputs { modules, input_ir })
}
fn execute(o: &Options, b: &mut Build) -> Result<()> {
    let environment = Environment::inspect(o, b)?;
    let m = environment.m;
    let AdmittedInputs { modules, input_ir } = admit_inputs(o, b, m)?;
    let pipeline = o.pipeline.as_str();
    b.record.set("pipeline", pipeline.into());
    let process_entry = o.tier == Some(Tier::Reversible);
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
        || [OptionKey::Oracle, OptionKey::Platform]
            .iter()
            .any(|key| o.get(*key).is_some());
    if !device_mode && !reserved_symbols {
        if o.comparison {
            return Err("BD-E-NATIVE-COMPARISON: no selected device entry; strict device comparison requires a materialised device module".into());
        }
        b.record.set(
            "unused_device_options",
            strings(
                &o.plugin_args
                    .iter()
                    .map(ToString::to_string)
                    .collect::<Vec<_>>(),
            ),
        );
        native_host::build(o, b, m, &modules, pipeline)?;
        return finalise_build(b);
    }
    // Oracle synthesis must preserve an internal program root before LTO and
    // establish the callable register ownership; a late flag cannot restore it.
    let preparation = [OptionKey::Oracle]
        .into_iter()
        .filter(|key| o.get(*key).is_some())
        .collect::<Vec<_>>();
    if !preparation.is_empty() {
        return Err(format!(
            "BD-B-MODE-BACKEND: {} requires a published descriptor/root, initializer or vscale preparation handoff before post-link optimisation; requested options and input hashes are retained, no unchanged build is certified",
            preparation
                .iter()
                .map(ToString::to_string)
                .collect::<Vec<_>>()
                .join(", ")
        ));
    }
    let program = environment.link(o, b, AdmittedInputs { modules, input_ir }, process_entry)?;
    let prepared_path = &program.prepared_path;
    if o.emission == Emission::ProcessBitcode {
        b.record
            .set("completion", "process-bitcode preparation stage".into());
        b.record.set(
            "outputs",
            obj([("process_prepared", artifact(prepared_path, None)?)]),
        );
        return b.save("prepared");
    }
    environment.lower(o, b, program)
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
        let out = absolute(o.get(OptionKey::Out).unwrap())?;
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
                ("llvm_major", o.major.into()),
                ("options", strings(&args)),
            ]),
        };
        let r = if o.get(OptionKey::Materialised).is_some() {
            native::compare(&o, &mut b)
        } else {
            execute(&o, &mut b).and_then(|()| {
                if o.comparison {
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
            // A production build may have completed before a later comparison
            // failed. Keep the hash-bound public receipt consistent with exit.
            if b.out.join("build.json").is_file() {
                finalise_build(&b)?;
            }
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
mod test_support {
    use super::*;

    pub struct Fixture {
        pub root: PathBuf,
        pub options: Options,
        pub build: Build,
    }
    impl Fixture {
        pub fn new(name: &str) -> Self {
            let root = task_tmpdir()
                .unwrap()
                .join(format!("stage-{name}-{}", std::process::id()));
            fs::create_dir(&root).unwrap();
            let out = root.join("out");
            fs::create_dir(&out).unwrap();
            fs::create_dir(root.join("include")).unwrap();
            let source = root.join("source.ll");
            let c_source = root.join("source.c");
            write(&c_source, "int main(void) { return 17; }\n").unwrap();
            let result = Command::new(tool(23, "clang"))
                .args(["-S", "-emit-llvm"])
                .arg(&c_source)
                .arg("-o")
                .arg(&source)
                .output()
                .unwrap();
            assert!(
                result.status.success(),
                "{}",
                String::from_utf8_lossy(&result.stderr)
            );
            let args = vec![
                "--bennett-dialect=0.2.13".into(),
                format!("--bennett-out={}", out.display()),
                source.display().to_string(),
            ];
            let mut options = Options::parse(&args).unwrap();
            for key in [
                OptionKey::Runtimes,
                OptionKey::Arith,
                OptionKey::Plugin,
                OptionKey::NativeCheck,
                OptionKey::NativeSupport,
            ] {
                let path = root.join(key.as_str());
                write(&path, "define void @unused() { ret void }\n").unwrap();
                options.paths.insert(key, path);
            }
            options.sysroot = Some(Sysroot::new(root.clone()).unwrap());
            let build = Build {
                out,
                record: obj([] as [(&str, Json); 0]),
                commands: vec![],
            };
            Self {
                root,
                options,
                build,
            }
        }
    }
    impl Drop for Fixture {
        fn drop(&mut self) {
            fs::remove_dir_all(&self.root).unwrap();
        }
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    fn parse(a: &[&str]) -> Result<Options> {
        Options::parse(&a.iter().map(|s| s.to_string()).collect::<Vec<_>>())
    }
    #[test]
    fn environment_stage_rejects_a_wrong_library_digest_before_tools() {
        let mut fixture = test_support::Fixture::new("environment");
        fixture
            .options
            .values
            .insert(OptionKey::RuntimesSha256, "0".repeat(64));
        let result = Environment::inspect(&fixture.options, &mut fixture.build);
        assert!(matches!(result, Err(error) if error.contains("BD-E-VERSION: SHA-256 mismatch")));
        assert!(fixture.build.commands.is_empty());
    }
    #[test]
    fn admission_stage_verifies_the_original_target_and_exports() {
        let mut fixture = test_support::Fixture::new("admission");
        let input = admit_inputs(&fixture.options, &mut fixture.build, 23).unwrap();
        assert_eq!(input.modules.len(), 1);
        let symbols = fixture
            .build
            .run(
                "test-symbols",
                vec![
                    tool(23, "llvm-nm"),
                    "--defined-only".into(),
                    input.modules[0].clone(),
                ],
                None,
            )
            .unwrap();
        assert!(symbols.split_whitespace().any(|symbol| symbol == "main"));
        let source = &fixture.options.inputs[0];
        write(source, "define i32 @main() { ret i32 17 }\n").unwrap();
        assert!(
            matches!(admit_inputs(&fixture.options, &mut fixture.build, 23), Err(error) if error.contains("missing target triple"))
        );
    }
    #[test]
    fn production_link_stage_preserves_the_admitted_program() {
        let mut fixture = test_support::Fixture::new("production-link");
        let input = admit_inputs(&fixture.options, &mut fixture.build, 23).unwrap();
        let environment = Environment {
            m: 23,
            runtime: configured_path(&fixture.options, OptionKey::Runtimes).unwrap(),
            arith: configured_path(&fixture.options, OptionKey::Arith).unwrap(),
            plugin: configured_path(&fixture.options, OptionKey::Plugin).unwrap(),
        };
        let linked = environment
            .link(&fixture.options, &mut fixture.build, input, false)
            .unwrap();
        let observed = Command::new(tool(23, "lli"))
            .arg(linked.linked)
            .output()
            .unwrap();
        assert_eq!(observed.status.code(), Some(17));
        assert!(observed.stderr.is_empty());
    }
    #[test]
    fn lowering_stage_fails_before_plugin_when_postlink_input_is_invalid() {
        let mut fixture = test_support::Fixture::new("lowering");
        let invalid = fixture.root.join("invalid.bc");
        write(&invalid, "not LLVM bitcode").unwrap();
        let environment = Environment {
            m: 23,
            runtime: PathBuf::new(),
            arith: PathBuf::new(),
            plugin: PathBuf::new(),
        };
        let program = LinkedProgram {
            arith: PathBuf::new(),
            linked: invalid,
            prepared_path: PathBuf::new(),
        };
        let result = environment.lower(&fixture.options, &mut fixture.build, program);
        assert!(matches!(result, Err(error) if error.starts_with("postlink:")));
        assert_eq!(fixture.build.commands.len(), 1);
        assert!(!fixture.build.out.join("build.json").exists());
    }
    #[test]
    fn repeated_backend_controls_keep_their_parsed_keys_and_order() {
        let options = parse(&[
            "--bennett-dialect=0.2.13",
            "--bennett-out=out",
            "--bennett-class=alpha",
            "--bennett-bind=x=y",
            "--bennett-class=beta",
            "input.ll",
        ])
        .unwrap();
        use OptionKey::{Bind, Class};
        let received = options
            .plugin_args
            .iter()
            .map(|arg| (arg.key, arg.value.as_str()))
            .collect::<Vec<_>>();
        assert_eq!(received, [(Class, "alpha"), (Bind, "x=y"), (Class, "beta")]);
    }
    #[test]
    fn typed_controls_have_one_default_owner() {
        let options =
            parse(&["--bennett-dialect=0.2.13", "--bennett-out=out", "input.ll"]).unwrap();
        assert_eq!(options.major, 23);
        assert!(!options.comparison);
        assert_eq!(options.tier, None);
        assert_eq!(options.emission, Emission::Artifact);
        assert_eq!(options.pipeline, "lto<O3>");
        assert_eq!(options.data_base, "4096");
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
        assert_eq!(o.plugin_args[0].key, OptionKey::AnalysisBudgetMs);
        assert_eq!(o.plugin_args[0].value, "300000");
        assert_eq!(
            o.plugin_args[0].to_string(),
            "-bennett-analysis-budget-ms=300000"
        );
    }
    #[test]
    fn defaults_choose_newest_envelope() {
        assert_eq!(
            parse(&["-bennett-dialect=0.2.10", "-bennett-out=o", "x.bc"])
                .unwrap()
                .major,
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
            parse(&args).unwrap().get(OptionKey::Emit),
            Some("process-bitcode")
        );
        args.push("--bennett-comparison=true");
        assert!(parse(&args).is_err());
    }
}
