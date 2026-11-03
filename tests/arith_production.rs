mod support;

#[test]
fn intrinsic_instances_enter_the_production_pipeline() {
    support::fixture("arith_production.py");
}
