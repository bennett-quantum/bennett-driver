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
