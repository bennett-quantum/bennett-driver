use std::{fs, path::PathBuf, process::Command};
fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}
#[test]
fn hashtable_pipeline_matches_recorded_objects() {
    let result = Command::new("python3")
        .arg(root().join("tests/integration.py"))
        .arg(env!("CARGO_BIN_EXE_bennett-driver"))
        .arg("pipeline")
        .output()
        .unwrap();
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
