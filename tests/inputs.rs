mod support;

#[test]
fn textual_and_mixed_major_bitcode_inputs_produce_same_launch() {
    support::fixture("inputs.py");
}
