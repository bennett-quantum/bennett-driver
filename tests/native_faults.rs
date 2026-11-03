mod support;

#[test]
fn materialised_faults_are_detected_at_o0_and_o2() {
    support::fixture("native_faults.py");
}
