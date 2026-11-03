mod support;

#[test]
fn native_support_diagnostics_execute_without_host_libc() {
    support::fixture("comparison.py");
}
