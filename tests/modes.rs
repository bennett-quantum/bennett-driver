mod support;

#[test]
fn published_controls_reach_the_backend_without_false_success() {
    support::fixture("modes.py");
}
