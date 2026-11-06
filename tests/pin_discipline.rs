mod support;

#[test]
fn sibling_reads_use_verified_pins_and_missing_configuration_is_loud() {
    support::fixture("pin_discipline.py");
}
