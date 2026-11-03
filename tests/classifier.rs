mod support;

#[test]
fn original_input_ubsan_is_separate_from_materialised_comparison() {
    support::fixture("classifier.py");
}
