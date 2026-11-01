use std::{path::PathBuf, process::Command};
#[test]
fn comparison_links_actual_materialised_module_without_libc() {
    let r = Command::new("python3")
        .arg(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/comparison.py"))
        .arg(env!("CARGO_BIN_EXE_bennett-driver"))
        .output()
        .unwrap();
    assert!(
        r.status.success(),
        "{}\n{}",
        String::from_utf8_lossy(&r.stdout),
        String::from_utf8_lossy(&r.stderr)
    );
}
