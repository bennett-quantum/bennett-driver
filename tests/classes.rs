mod support;
#[test]
#[ignore = "promised capability: bennett-driver-9zg; run --test classes -- --ignored"]
fn configured_classes_reach_production_lowering() {
    support::fixture("classes.py");
}
