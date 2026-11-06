# Driver quality measurements

Round 1 preserves the pin-discipline branch and its plugin-native-comparison pin
`5a092cded3ba3351ba8cc2977a7eaf3b40f46526`.

The promised capability tests stay visible under named switches:
`cargo test --offline -j3 --test classes --test device_models --test pipeline --no-fail-fast -- --ignored --nocapture --test-threads=4`.
The quality job reproduced three failures: configured classes at dialect §3.4
(bennett-driver-9zg), scalar descriptor dispatch at §8.4 (bennett-driver-7y4),
and the missing tracked conformance `driver-regression/report.json`
(bennett-driver-ppz). Gate reports retain these expected failures. The exact
producer publication requests remain in their beads; these are capability
obligations, not accepted refusals or removed tests.

Default test timing before the split: `timeout 180 cargo test --offline -j3 -- --test-threads=4` timed out (exit 124). After consolidating 26 fixture wrappers and moving the two offline arithmetic generators to the gate's slow check, the same command passed in 154.19 s (7 unit tests, 24 active fixture tests, 2 pipeline checks; 5 named ignored tests). Test-profile debug information is line tables only. Job-local target/TMPDIR, headless environment and verified gate-pin checkouts were used. No consumer or full push gate was run.

Coverage before the stage refactor: **91.85% lines** (2,199/2,394), measured with
`timeout 240 cargo llvm-cov --offline -j3 --summary-only -- --test-threads=4`.
The run passed against the gate pins, including Python-spawned driver processes.
`environment` explicitly checks that `LLVM_PROFILE_FILE` survives external commands.
No coverage threshold is imposed.

Five least-covered Rust modules in that run:

| Module | Line coverage | Treatment |
|---|---:|---|
| llvm_utility | 86.14% | New red-first cache placement/execution and missing TMPDIR tests; remaining allocator/OS publication failures are platform error paths. |
| native_adapter | 88.66% | Real pinned prepare/check/finalise tests cover the published API; complete producer acceptance still depends on the open producer publications. |
| main | 89.91% | Option and stage boundary unit tests are part of the next refactor, alongside the existing target/alias/metadata matrices. |
| report | 90.32% | Structured error/code/exit integration tests execute the principal report classes; secondary report-write failure requires filesystem fault injection. |
| output_paths | 90.62% | Direct/canonical/symlink/hardlink/prior-artifact alias matrices execute real filesystem protection; uncommon metadata/read failures remain platform paths. |
