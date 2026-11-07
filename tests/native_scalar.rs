mod support;

#[test]
fn actual_scalar_r_requires_real_program_binding_before_startup() {
    support::fixture("native_scalar_binding.py");
}

#[test]
#[ignore = "§17.7: musl pop_arg faults on native va_list storage; expected red until the varargs checker storage fix (bennett-driver-972)"]
fn scalar_printf_process_preparation_uses_the_real_static_native_closure() {
    support::fixture("native_scalar.py");
}
