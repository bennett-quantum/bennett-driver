use std::{path::PathBuf, process::Command};
#[test]
fn actual_materialisation_uses_the_published_native_adapter() {
    let result = Command::new("python3")
        .arg(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/native_materialisation.py"))
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
