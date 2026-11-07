use std::{fs, path::PathBuf, process::Command};
fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}
#[test]
#[ignore = "blocked publication: bennett-driver-ppz; run --test pipeline -- --ignored"]
fn hashtable_pipeline_matches_recorded_objects() {
    let result = Command::new("python3")
        .arg(root().join("tests/integration.py"))
        .arg(env!("CARGO_BIN_EXE_bennett-driver"))
        .arg("pipeline")
        .output()
        .unwrap();
    print!("{}", String::from_utf8_lossy(&result.stdout));
    assert!(
        result.status.success(),
        "{}\n{}",
        String::from_utf8_lossy(&result.stdout),
        String::from_utf8_lossy(&result.stderr)
    );
}
#[test]
fn version_mismatch_is_loud() {
    let out = root().join(".tmp/test-version");
    let result = Command::new(env!("CARGO_BIN_EXE_bennett-driver"))
        .args([
            "-bennett-dialect=0.1",
            &format!("-bennett-out={}", out.display()),
            "missing.bc",
        ])
        .output()
        .unwrap();
    assert!(!result.status.success());
    assert!(String::from_utf8_lossy(&result.stderr).contains("BD-E-VERSION"));
    let _ = fs::remove_dir_all(out);
}

#[test]
fn missing_published_fixture_names_its_dependency() {
    let missing = root().join(format!(".tmp/absent-rung2-fixture-{}", std::process::id()));
    assert!(!missing.exists());
    let result = Command::new("python3")
        .arg(root().join("tests/integration.py"))
        .arg(env!("CARGO_BIN_EXE_bennett-driver"))
        .arg("--check-inputs")
        .env("BENNETT_RUNG2_EVIDENCE", missing)
        .output()
        .unwrap();
    assert!(!result.status.success());
    let error = String::from_utf8_lossy(&result.stderr);
    assert!(error.contains("BD-E-TEST-FIXTURE"), "{error}");
    assert!(
        error.contains("conformance must publish the tracked driver-regression fixture"),
        "{error}"
    );
    assert!(error.contains("no live sibling .tmp fallback"), "{error}");
}
