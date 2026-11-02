use std::{path::PathBuf, process::Command};

#[test]
fn process_preparation_is_rooted_before_materialisation() {
    let result = Command::new("python3")
        .arg(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/process.py"))
        .arg(env!("CARGO_BIN_EXE_bennett-driver"))
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
