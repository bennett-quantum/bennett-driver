mod support;

#[test]
fn concrete_arithmetic_uses_verified_offline_instances() {
    support::fixture("arith_instances.py");
}
