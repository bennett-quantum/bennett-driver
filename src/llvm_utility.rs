//! Driver-owned bitcode synthesis utilities, compiled as external LLVM tools.
use super::*;

pub fn compile(b: &mut Build, major: u32, name: &str, code: &str) -> Result<PathBuf> {
    let source = b.out.join(format!("{name}.cpp"));
    write(&source, code)?;
    let cache = env::var_os("TMPDIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| Path::new(env!("CARGO_MANIFEST_DIR")).join(".tmp"))
        .join("bennett-driver-tools");
    fs::create_dir_all(&cache).map_err(|e| format!("LLVM utility cache: {e}"))?;
    let executable = cache.join(format!("{name}-{major}-{}", sha(&source)?));
    if !executable.is_file() {
        let flags = b.run(
            &format!("{name}-tool-flags"),
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
        let temporary = b.out.join(format!("{name}-tool"));
        let mut args = vec![
            tool(major, "clang++"),
            "-O1".into(),
            source.display().to_string(),
        ];
        args.extend(flags.split_whitespace().map(String::from));
        args.extend(["-o".into(), temporary.display().to_string()]);
        b.run(&format!("{name}-tool-build"), args, None)?;
        fs::rename(&temporary, &executable).map_err(|e| format!("LLVM utility publish: {e}"))?;
    }
    Ok(executable)
}
