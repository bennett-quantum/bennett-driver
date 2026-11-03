use std::{path::PathBuf, process::Command};
#[test]
fn certificate_pipeline_matches_execution_for_each_option_spelling() {
    let result = Command::new("python3")
        .arg(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/pipeline_metadata.py"))
        .arg(env!("CARGO_BIN_EXE_bennett-driver"))
        .output()
        .unwrap();
    assert!(
        result.status.success(),
        "{}\n{}",
        String::from_utf8_lossy(&result.stdout),
        String::from_utf8_lossy(&result.stderr)
    );
}
