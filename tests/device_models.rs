mod support;

#[test]
#[ignore = "promised capability: bennett-driver-7y4; run --test device_models -- --ignored"]
fn selected_oracle_initialises_the_published_device_models() {
    support::fixture("device_models.py");
}
