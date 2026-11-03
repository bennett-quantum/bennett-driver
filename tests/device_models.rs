mod support;

#[test]
fn selected_oracle_initialises_the_published_device_models() {
    support::fixture("device_models.py");
}
