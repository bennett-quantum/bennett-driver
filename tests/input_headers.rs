mod support;

#[test]
fn all_production_inputs_require_explicit_targets() {
    support::fixture("input_headers.py");
}
