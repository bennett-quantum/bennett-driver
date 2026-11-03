mod support;

#[test]
fn structured_reports_cover_input_version_plugin_and_native_failures() {
    support::fixture("reports.py");
}
