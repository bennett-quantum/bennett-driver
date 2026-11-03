mod support;

#[test]
fn certificate_pipeline_matches_execution_for_each_option_spelling() {
    support::fixture("pipeline_metadata.py");
}
