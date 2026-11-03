mod support;

#[test]
fn concrete_conversions_use_every_published_format_and_carrier() {
    support::fixture("arith_conversions.py");
}
