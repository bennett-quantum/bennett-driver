//! Integration fixtures; select an individual Python case by its Rust test name.
mod support;

mod arith_conversions {
    use super::support;

    #[test]
    #[ignore = "slow offline arithmetic generator; run --test fixtures -- --ignored"]
    fn concrete_conversions_use_every_published_format_and_carrier() {
        support::fixture("arith_conversions.py");
    }
}

mod arith_instances {
    use super::support;

    #[test]
    #[ignore = "slow offline arithmetic generator; run --test fixtures -- --ignored"]
    fn concrete_arithmetic_uses_verified_offline_instances() {
        support::fixture("arith_instances.py");
    }
}

mod arith_production {
    use super::support;

    #[test]
    fn intrinsic_instances_enter_the_production_pipeline() {
        support::fixture("arith_production.py");
    }
}

mod classifier {
    use super::support;

    #[test]
    fn original_input_ubsan_is_separate_from_materialised_comparison() {
        support::fixture("classifier.py");
    }
}

mod closed_unit {
    use super::support;

    #[test]
    fn function_pointer_entry_falls_back_to_whole_program() {
        support::fixture("closed_unit.py");
    }
}

mod comparison {
    use super::support;

    #[test]
    fn native_support_diagnostics_execute_without_host_libc() {
        support::fixture("comparison.py");
    }
}

mod dialect_profile {
    use super::support;

    #[test]
    fn modern_contract_is_explicit_and_preserves_host_ownership() {
        support::fixture("dialect_profile.py");
    }
}

mod environment {
    use super::support;

    #[test]
    fn external_children_keep_the_task_environment() {
        support::fixture("environment.py");
    }
}

mod hook {
    use super::support;
    #[test]
    fn gate_configuration_and_stub_are_ready() {
        support::fixture("hook.py");
    }
}

mod input_headers {
    use super::support;

    #[test]
    fn all_production_inputs_require_explicit_targets() {
        support::fixture("input_headers.py");
    }
}

mod inputs {
    use super::support;

    #[test]
    fn textual_and_mixed_major_bitcode_inputs_produce_same_launch() {
        support::fixture("inputs.py");
    }
}

mod modes {
    use super::support;

    #[test]
    fn published_controls_reach_the_backend_without_false_success() {
        support::fixture("modes.py");
    }
}

mod native_byval {
    use super::support;

    #[test]
    fn valid_byval_objects_remain_live_in_native_comparison() {
        support::fixture("native_byval.py");
    }
}

mod native_faults {
    use super::support;

    #[test]
    fn materialised_faults_are_detected_at_o0_and_o2() {
        support::fixture("native_faults.py");
    }
}

mod native_host {
    use super::support;

    #[test]
    fn unmarked_programs_build_and_run_as_native_hosts() {
        support::fixture("native_host.py");
    }
}

mod native_materialisation {
    use super::support;

    #[test]
    fn actual_materialisation_uses_the_published_native_adapter() {
        support::fixture("native_materialisation.py");
    }
}

mod native_memory {
    use super::support;

    #[test]
    fn materialised_memory_checks_use_published_adapter() {
        support::fixture("native_memory.py");
    }
}

mod native_symbols {
    use super::support;

    #[test]
    fn native_elf_symbols_match_resolved_device_ranges() {
        support::fixture("native_symbols.py");
    }
}

mod output_paths {
    use super::support;

    #[test]
    fn comparison_outputs_preserve_inputs_and_evidence() {
        support::fixture("output_paths.py");
    }
}

mod pin_discipline {
    use super::support;

    #[test]
    fn sibling_reads_use_verified_pins_and_missing_configuration_is_loud() {
        support::fixture("pin_discipline.py");
    }
}

mod pipeline_metadata {
    use super::support;

    #[test]
    fn certificate_pipeline_matches_execution_for_each_option_spelling() {
        support::fixture("pipeline_metadata.py");
    }
}

mod preparation {
    use super::support;
    #[test]
    fn source_preparation_precedes_postlink_optimisation() {
        support::fixture("preparation.py");
    }
}

mod process {
    use super::support;

    #[test]
    fn process_preparation_is_rooted_before_materialisation() {
        support::fixture("process.py");
    }
}

mod process_runtime_apis {
    use super::support;

    #[test]
    fn process_locale_and_page_apis_are_published() {
        support::fixture("process_runtime_apis.py");
    }
}

mod reports {
    use super::support;

    #[test]
    fn structured_reports_cover_input_version_plugin_and_native_failures() {
        support::fixture("reports.py");
    }
}

mod reversible {
    use super::support;

    #[test]
    fn rung3_mode_reaches_plugin_or_reports_real_blocker() {
        support::fixture("reversible.py");
    }
}

#[test]
fn merged_module_executes_like_independent_native_sources() {
    support::fixture("merged_module.py");
}

#[test]
fn quality_baseline_rejects_independent_regression_classes() {
    support::fixture("quality.py");
}
