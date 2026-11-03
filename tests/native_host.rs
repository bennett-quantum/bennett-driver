mod support;

#[test]
fn unmarked_programs_build_and_run_as_native_hosts() {
    support::fixture("native_host.py");
}
