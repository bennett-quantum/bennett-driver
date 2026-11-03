mod support;

#[test]
fn modern_contract_is_explicit_and_preserves_host_ownership() {
    support::fixture("dialect_profile.py");
}
