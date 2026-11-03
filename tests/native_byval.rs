mod support;

#[test]
fn valid_byval_objects_remain_live_in_native_comparison() {
    support::fixture("native_byval.py");
}
