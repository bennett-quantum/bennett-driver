mod support;

#[test]
fn materialised_memory_checks_use_published_adapter() {
    support::fixture("native_memory.py");
}
