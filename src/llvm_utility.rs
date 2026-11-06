//! Driver-owned bitcode synthesis utilities, compiled as external LLVM tools.
use super::*;

pub fn compile(b: &mut Build, major: u32, name: &str, code: &str) -> Result<PathBuf> {
    let cache = task_tmpdir()?.join("bennett-driver-tools");
    let source = b.out.join(format!("{name}.cpp"));
    write(&source, code)?;
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn compilation_requires_task_tmpdir() {
        // A child process isolates environment removal from parallel unit tests.
        if env::var_os("BENNETT_DRIVER_TEST_MISSING_TMPDIR").is_some() {
            let mut build = Build {
                out: PathBuf::new(),
                record: obj([] as [(&str, Json); 0]),
                commands: vec![],
            };
            let error = compile(&mut build, 23, "unused", "unused").unwrap_err();
            assert!(error.starts_with("BD-E-CONFIG: missing TMPDIR"), "{error}");
        } else {
            let result = Command::new(env::current_exe().unwrap())
                .args([
                    "--exact",
                    "llvm_utility::tests::compilation_requires_task_tmpdir",
                ])
                .env_remove("TMPDIR")
                .env("BENNETT_DRIVER_TEST_MISSING_TMPDIR", "1")
                .output()
                .unwrap();
            assert!(
                result.status.success(),
                "{}",
                String::from_utf8_lossy(&result.stderr)
            );
        }
    }
}
