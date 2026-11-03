mod support;

#[test]
fn process_locale_and_page_apis_are_published() {
    support::fixture("process_runtime_apis.py");
}
