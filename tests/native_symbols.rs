mod support;

#[test]
fn native_elf_symbols_match_resolved_device_ranges() {
    support::fixture("native_symbols.py");
}
