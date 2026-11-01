//! Offline arithmetic instantiation through the published JSON/bitcode ABI.
use super::*;

pub fn prepare(
    o: &Options,
    b: &mut Build,
    major: u32,
    base: &Path,
    ir: &[PathBuf],
) -> Result<PathBuf> {
    let effective = b.out.join("arith-effective.bc");
    if effective.is_file() {
        // Continuing production into comparison reuses the verified closure.
        // Admission required this Build's output directory to be empty.
        return Ok(effective);
    }
    let mut collect = vec![
        "python3".into(),
        "-c".into(),
        include_str!("../scripts/arith-instances.py").into(),
        "collect".into(),
        b.out.display().to_string(),
        major.to_string(),
    ];
    collect.extend(ir.iter().map(|p| p.display().to_string()));
    let needed = b.run("arith-collect", collect, None)?;
    if needed.trim() == "none" {
        return Ok(base.into());
    }
    if needed.trim() != "required" {
        return Err("BD-E-ARITH-INSTANCES: collector returned no verdict".into());
    }
    let generator = absolute(
        o.get("bennett-arith-generator")
            .map(PathBuf::from)
            .unwrap_or(
                Path::new(env!("CARGO_MANIFEST_DIR"))
                    .parent()
                    .unwrap()
                    .join("bennett-arith/softfloat/instantiate.py"),
            ),
    )?;
    b.record.set(
        "arith_generator",
        artifact(&generator, o.get("bennett-arith-generator-sha256"))?,
    );
    let request = b.out.join("arith-request.json");
    b.record.set("arith_request", artifact(&request, None)?);
    let directory = b.out.join("arith-instances");
    b.run("arith-generate",vec!["python3".into(),"-I".into(),generator.display().to_string(),request.display().to_string(),directory.display().to_string()],None)
        .map_err(|e| format!("BD-E-ARITH-INSTANCES: offline generation failed; every requested format/width remains required. {e}"))?;
    b.run(
        "arith-verify",
        vec![
            "python3".into(),
            "-c".into(),
            include_str!("../scripts/arith-instances.py").into(),
            "verify".into(),
            b.out.display().to_string(),
            major.to_string(),
        ],
        None,
    )?;
    let instances = directory.join("bennett-arith.bc");
    b.record.set("arith_instances", artifact(&instances, None)?);
    b.record.set(
        "arith_instances_manifest",
        artifact(&directory.join("manifest.json"), None)?,
    );
    b.record.set(
        "arith_verification",
        artifact(&b.out.join("arith-verification.json"), None)?,
    );
    // A generated instance replaces a prebuilt cache entry at this exact type.
    // This happens before materialisation, never over a materialised body.
    b.run(
        "arith-library-link",
        vec![
            tool(major, "llvm-link"),
            base.display().to_string(),
            format!("--override={}", instances.display()),
            "-o".into(),
            effective.display().to_string(),
        ],
        None,
    )?;
    b.record.set("effective_arith", artifact(&effective, None)?);
    Ok(effective)
}
