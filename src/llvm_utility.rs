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
        // Compile beside the destination: rename remains atomic even when the
        // build output and TMPDIR live on different filesystems.
        static NEXT_BUILD: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
        let temporary = loop {
            let serial = NEXT_BUILD.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
            let path =
                executable.with_extension(format!("partial-{}-{serial}", std::process::id()));
            match fs::OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(&path)
            {
                Ok(_) => break path,
                Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => continue,
                Err(error) => return Err(format!("LLVM utility temporary: {error}")),
            }
        };
        let mut args = vec![
            tool(major, "clang++"),
            "-O1".into(),
            source.display().to_string(),
        ];
        args.extend(flags.split_whitespace().map(String::from));
        args.extend(["-o".into(), temporary.display().to_string()]);
        if let Err(error) = b.run(&format!("{name}-tool-build"), args, None) {
            fs::remove_file(&temporary)
                .map_err(|cleanup| format!("{error}; cleanup: {cleanup}"))?;
            return Err(error);
        }
        fs::rename(&temporary, &executable).map_err(|e| format!("LLVM utility publish: {e}"))?;
    }
    Ok(executable)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tool_publication_stays_on_cache_filesystem_6bl() {
        let out = task_tmpdir()
            .unwrap()
            .join(format!("utility-test-{}", std::process::id()));
        fs::create_dir_all(&out).unwrap();
        let mut build = Build {
            out: out.clone(),
            record: obj([] as [(&str, Json); 0]),
            commands: vec![],
        };
        let name = format!("cache-probe-{}", std::process::id());
        let executable = compile(&mut build, 23, &name, "int main() { return 17; }\n").unwrap();
        let command = build
            .commands
            .iter()
            .find(|command| command.encode().contains("-tool-build"))
            .unwrap();
        let Json::Object(fields) = command else {
            panic!("command must be an object")
        };
        let Json::Array(argv) = &fields["argv"] else {
            panic!("argv must be an array")
        };
        let Json::Str(destination) = argv.last().unwrap() else {
            panic!("output must be a path")
        };
        assert_eq!(
            Path::new(destination).parent(),
            executable.parent(),
            "publish must use a same-filesystem rename"
        );
        assert_eq!(Command::new(&executable).status().unwrap().code(), Some(17));
        fs::remove_file(executable).unwrap();
        fs::remove_dir_all(out).unwrap();
    }

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
