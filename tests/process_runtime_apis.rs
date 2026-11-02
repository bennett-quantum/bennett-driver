use std::{path::PathBuf, process::Command};

#[test]
fn process_locale_and_page_apis_are_published() {
    let result = Command::new("python3")
        .arg(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/process_runtime_apis.py"))
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
