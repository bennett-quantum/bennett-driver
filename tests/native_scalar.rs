mod support;

#[test]
fn scalar_printf_process_preparation_uses_the_real_static_native_closure() {
    support::fixture("native_scalar.py");
}
