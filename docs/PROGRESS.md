## Resume

Native comparison links the actual materialised module with published runtimes and arithmetic, comparison-only native support and the resolved ABI-v1 layout table. Plain O2 comparison and O0 diagnostic links remain distinct from source definedness classifiers. Materialised input bytes and production region identity are unchanged.

The driver now checks scalar signed/unsigned division and remainder before native optimisation, preserving fault 5 for zero divisors and fault 6 for signed minimum/-1. Reached unreachable/trap paths call fault 4. Exact explicit runtime fault codes and double-free faults are tested. `native-detection.json` states that general load/store/range and use-after-free detection remain incomplete (`brt-2qs`); it never claims UBSan supplies these checks.

`--bennett-classifier-input=FILE` builds an original-C O0 UBSan-minimal diagnostic with the actual matching-major published compiler-rt archive, runtime and sanitizer support. Original C inputs in a combined production/comparison invocation are collected automatically; an adapter with no original input records its classifier as blocked. Classifiers have independent resolved diagnostic layouts, source hashes, commands and `native-classifiers.json` coverage. Their outputs are not native/device agreement. Actual array-overrun diagnostics execute on both majors. Full ASan remains blocked on `brt-nuu.2`.

Arithmetic instance integration uses the 0.2.12 §13.1 request schema without claiming a wholesale dialect/ISA compatibility upgrade: accepted plugin identity remains dialect0.2.10/ISA0.8. The driver collects sorted, deduplicated powi/conversion instances from verified LLVM IR, invokes the documented offline generator, verifies request/bitcode hashes, target fields and literal LLVM export types, and builds the effective arithmetic library before normalisation. Generator path/hash overrides are `--bennett-arith-generator` and `--bennett-arith-generator-sha256`.

**The arithmetic acceptance test is RED.** Real generated f32 i7/i193 plain/_rm definitions pass manifest/type validation, but strict native linking finds the required `__bennett_rt_fenv` missing from both current runtime publications. Producer `brt-zct.1` owns the `{i32,i32}`, align4, initial-zero state. Local blocker `bennett-driver-4wi` blocks `bennett-driver-q4d`. The arithmetic diagnostic fixture also reports an unresolved native data-end/heap mismatch. Do not add a fake state object, relax the linker assertion, remove the test or claim numerical acceptance. Per COMMON.md rule8, implementation stops at this external prerequisite.

Verification receipts:

- `BENNETT_DRIVER_TEST_ARTIFACTS=.tmp/native-probes-20261101T142910Z timeout 300 cargo test --offline -j4 --test native_faults --test classifier --test comparison -- --nocapture --test-threads=4`: PASS after all code changes (three tests), including 36 exact materialised fault outcomes and actual source UBSan failure diagnostics across LLVM18/23.
- `BENNETT_DRIVER_TEST_ARTIFACTS=.tmp/native-probes-20261101T142910Z timeout 420 cargo test --offline -j4 --test reports --test inputs --test reversible --test classifier --test comparison -- --nocapture --test-threads=4`: PASS, five tests; actual R/musl blockers retained.
- `BENNETT_DRIVER_TEST_PUBLICATIONS=.tmp/sol-driver-queue/publications timeout 420 cargo test --offline -j4 --test pipeline -- --nocapture --test-threads=4`: PASS, two tests, four frozen launch hashes equal; recorded ten-case native/VM/reference observations agree, actual driver-native residual qalloc/qfree blockers remain. Explicit immutable publications avoid invoking Git for recovery.
- `timeout 360 cargo test --offline -j4 --test arith_instances -- --nocapture --test-threads=4`: FAIL at real native linking (missing runtime fenv; diagnostic layout mismatch). No real instance execution or tamper-regression pass claimed.
- `timeout 120 cargo test --offline -j4 --bin bennett-driver -- --test-threads=4`: PASS, four unit tests.
- `timeout 120 cargo clippy --offline -j4 --all-targets -- -D warnings`: PASS after arithmetic integration.

Open: cyg.3 native corpus/shared layout (`bp-xyn`), materialised memory checks (`brt-2qs`), full ASan (`brt-nuu.2`); cyg.2 ISA0.8 typed R fault boundary and nonempty argv/process context; i0v complete memory coverage; q4d real production/native arithmetic acceptance (`4wi` / `brt-zct.1`). Existing LLVM18 hello vector materialisation (`bp-ozp`) and LLVM23 R ISA7/console marker evidence remain separate. No bead was closed prematurely.

Runner must commit the owned files and run the detached `scripts/pre-push` gate; that script invokes Git and was not run under this job protocol. The rung-3 consumer was read only, never edited or run. No Git command was run by this job.
