//! Strict native comparison. No standard libraries or startup files are added.
use super::*;
fn number(o: &Options, key: &str, default: u64) -> Result<u64> {
    match o.get(key) {
        None => Ok(default),
        Some(s) => if let Some(hex) = s.strip_prefix("0x") {
            u64::from_str_radix(hex, 16)
        } else {
            s.parse()
        }
        .map_err(|e| format!("BD-E-INPUT: {key}: {e}")),
    }
}
pub fn compare(o: &Options, b: &mut Build) -> Result<()> {
    let m = o.major()?;
    let ws = Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap();
    let device = absolute(
        o.get("bennett-materialised")
            .map(PathBuf::from)
            .unwrap_or(b.out.join("device.bc")),
    )?;
    let runtime = absolute(
        o.get("bennett-runtimes")
            .map(PathBuf::from)
            .unwrap_or(ws.join(format!("bennett-runtimes/dist/llvm{m}/bennett-runtimes.bc"))),
    )?;
    let arith = absolute(
        o.get("bennett-arith")
            .map(PathBuf::from)
            .unwrap_or(ws.join(format!("bennett-arith/dist/llvm{m}/bennett-arith.bc"))),
    )?;
    let record_path = absolute(
        o.get("bennett-comparison-record")
            .map(PathBuf::from)
            .unwrap_or(b.out.join("native-comparison.json")),
    )?;
    let exe = absolute(
        o.get("bennett-comparison-output")
            .map(PathBuf::from)
            .unwrap_or(b.out.join("native-O2")),
    )?;
    let device_sha = sha(&device)?;
    for (key, p) in [("runtimes", &runtime), ("arith", &arith)] {
        b.record
            .set(key, artifact(p, o.get(&format!("bennett-{key}-sha256")))?);
    }
    b.run(
        "comparison-verify",
        vec![
            tool(m, "opt"),
            "-passes=verify".into(),
            "-disable-output".into(),
            device.display().to_string(),
        ],
        None,
    )?;
    let data = number(o, "bennett-layout-data-base", 4096)?;
    if data < 4096 || data % 4096 != 0 {
        return Err("BD-E-INPUT: comparison data base must be page aligned and leave the 4096-byte null region".into());
    }
    // This is a native layout map, not a claim that the plugin's device layout
    // already agrees. That cross-boundary obligation is tracked in cyg.3.
    let text = number(o, "bennett-layout-text-base", 0x400000)?;
    if text <= data || text % 0x200000 != 0 {
        return Err("BD-E-INPUT: text base must follow data on a 2MiB boundary".into());
    }
    let script = b.out.join("comparison.ld");
    write(
        &script,
        format!(
            "SECTIONS {{\n . = {data}; .rodata : {{ *(.rodata .rodata.*) }}\n .data : {{ *(.data .data.*) *(.init_array*) *(.fini_array*) }}\n .bss : {{ *(.bss .bss.*) *(COMMON) }}\n ASSERT(. < {text}, \"comparison data overlaps text\")\n . = {text}; .text : {{ *(.text .text.*) }}\n /DISCARD/ : {{ *(.eh_frame*) *(.comment) *(.note*) }}\n}}\n"
        ),
    )?;
    let mut extras = vec![];
    // Explicit comparison-only support, never linked into the production module.
    for key in ["bennett-native-input", "bennett-native-backend"] {
        if let Some(p) = o.get(key) {
            let p = absolute(p)?;
            b.record.set(key, artifact(&p, None)?);
            let output = b.out.join(format!("{key}.o"));
            b.run(
                "native-support",
                vec![
                    tool(m, "clang"),
                    "-O2".into(),
                    "-ffreestanding".into(),
                    "-fno-builtin".into(),
                    "-fno-pie".into(),
                    "-c".into(),
                    p.display().to_string(),
                    "-o".into(),
                    output.display().to_string(),
                ],
                None,
            )?;
            extras.push(output.display().to_string());
        }
    }
    let mut results = vec![];
    let mut first_error = None;
    for level in ["O2", "O0"] {
        let output = if level == "O2" {
            exe.clone()
        } else {
            exe.with_file_name("native-O0")
        };
        let mut argv = vec![
            tool(m, "clang"),
            format!("-{level}"),
            "-nostdlib".into(),
            "-nostdinc".into(),
            "-static".into(),
            "-no-pie".into(),
            "-fno-merge-all-constants".into(),
            device.display().to_string(),
            runtime.display().to_string(),
            arith.display().to_string(),
        ];
        argv.extend(extras.clone());
        if let Some(root) = o.get("bennett-sysroot") {
            argv.push(format!("--sysroot={}", absolute(root)?.display()));
        }
        if level == "O0" {
            argv.extend([
                "-fsanitize=address,undefined".into(),
                "-fno-sanitize-link-runtime".into(),
                "-fno-omit-frame-pointer".into(),
            ]);
        }
        argv.extend([
            format!("-Wl,-T,{}", script.display()),
            "-Wl,-e,_start".into(),
            "-Wl,--fatal-warnings".into(),
            "-Wl,--no-undefined".into(),
            format!(
                "-Wl,-Map,{}",
                b.out.join(format!("native-{level}.map")).display()
            ),
            "-o".into(),
            output.display().to_string(),
        ]);
        let mut record = obj([
            ("schema", "bennett-driver-native-comparison-1".into()),
            ("llvm_major", m.into()),
            ("materialised_sha256", device_sha.clone().into()),
            ("link_argv", strings(&argv)),
            ("status", "planned".into()),
        ]);
        if level == "O2" {
            write(&record_path, record.encode() + "\n")?;
        }
        let r = b.run(&format!("native-{level}"), argv, None);
        record.set(
            "status",
            if r.is_ok() {
                "linked".into()
            } else {
                "failed".into()
            },
        );
        if let Err(e) = r {
            record.set("error", e.clone().into());
            if first_error.is_none() {
                first_error = Some(e);
            }
        } else {
            let audit = b.run(
                "native-undefined",
                vec![
                    tool(m, "llvm-nm"),
                    "--undefined-only".into(),
                    output.display().to_string(),
                ],
                None,
            )?;
            if !audit.trim().is_empty() {
                return Err(format!("comparison unresolved imports: {audit}"));
            }
            record.set("sha256", sha(&output)?.into());
        }
        if level == "O2" {
            write(&record_path, record.encode() + "\n")?;
        }
        results.push(record);
    }
    write(
        b.out.join("native-comparisons.json"),
        Json::Array(results).encode() + "\n",
    )?;
    if let Some(e) = first_error {
        return Err(format!(
            "BD-E-NATIVE-LINK: §17.7/§19.5 strict comparison cannot link; no host libc/libm fallback. Supply the published native primitive/entry/sanitizer closure. {e}"
        ));
    }
    b.save("complete")
}
