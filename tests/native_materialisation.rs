mod support;

#[test]
fn actual_materialisation_uses_the_published_native_adapter() {
    support::fixture("native_materialisation.py");
}
