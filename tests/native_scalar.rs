mod support;

#[test]
fn actual_scalar_r_requires_real_program_binding_before_startup() {
    support::fixture("native_scalar_binding.py");
}

#[test]
fn scalar_printf_process_preparation_uses_the_real_static_native_closure() {
    support::fixture("native_scalar.py");
}
