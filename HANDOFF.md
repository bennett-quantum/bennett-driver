# Handoff — 2026-11-01T13:56:57Z

Real `date -u`; no push. Accepted dialect **0.2.10 @
023f5a771a814270634db3be9cfde88ded69f975**, ISA **0.8**. **M1 remains incomplete**.

§19.1/19.9: external full-LTO pipeline for C/IR/bitcode, LLVM18/23, major-matched
libraries, optional SHA pins, real plugin ABI identity and module flag checks.
Manifest includes tool/process/input/hash receipts; canonical driver build/hash,
certificate association and refreshed artifact inventories preserve object bytes.
§19.2: real R main argv/console launch now emitted by updated plugin on both
majors. Plugin exits3 with **BD-B-ISA7 / BLK-5**; driver verifies and retains outputs,
finalises metadata with status blocked, exits1 and emits exact structured reports.
Per-entry argv reply uses empty argc/argv/envp header, or checked caller-supplied
public reply JSON. Nonempty argument storage packing is still required work.
§17.7/19.5: strict actual-materialised native adapter, two-stage --only-needed
merge, O2/O0+ASan/UBSan argv and linker scripts/maps; no host libc/libm or fake
marker definitions. **No driver native execution result yet**; missing native
closure and shared device/native layout remain blocked.
§19.8: newest-major default23, basic mixed18/23 input reading/linking and target
checks. §25: loud JSON/line reports preserve input/version/plugin/native failures.

Verification: **11 Rust test cases**, clippy with -D warnings and formatting.
All four unchanged hashtable launch SHA256s agree with latest rung-2 evidence
**20261101T130556.518962Z**, using its exact frozen plugin157d4bd1 and runtime/arith
hashes. Recorded hosted O0/sanitizer and O2 baselines agree; they are not reused
as driver output. Integration asserts the actual strict native-link blocker.

Loaded builds exhausted the plugin's default **30000ms compiler wall-clock**
analysis guard (bp-xv0), including a frozen-plugin detached run. Integration now
explicitly records **--bennett-analysis-budget-ms=300000**; execution budgets,
corpus and expected hashes are unchanged. Earlier failed receipt:
`.tmp/pre-push-13ffb3f-analysis-timeout.log`. Concurrent .so rewrites also produced
real file-too-short refusals; final tests use explicit captured artifacts through
`BENNETT_DRIVER_TEST_ARTIFACTS=/home/tobias/Projects/bennett-workspace/bennett-driver/.tmp/plugin-snapshot-20261101T135147Z` (manifest records all SHAs, CLI pins verified).
No default-under-active-rebuild acceptance is claimed.

Latest persistent rung-3 argv/manifests/blocked builds/replies/reports:
`/home/tobias/Projects/bennett-workspace/bennett-driver/.tmp/final-rung3-20261101T135513Z`. Explicit18/23 and no-major(default23) all exit1 with BD-B-ISA7 after
emitting the real R launch. The final clean detached gate receipt is
`.tmp/final-pre-push.log`; it tests committed SHA, not dirty checkout, then cleans up.

Driver cyg.1/4 closed; cyg.2/3 and umbrella **bennett-driver-cyg remain blocked**.
Consumer beads filed: **bp-xkg** (R/argv history, updated mode now delivered),
**bp-xyn** (native materialisation/layout), **bp-xv0** (compiler allowance),
**brt-nuu** (native startup/musl/primitives/sanitizers),
**bennett-conformance-7n6** (two-stage native record/explicit-major adapter).
Sibling commits touched exported `.beads/issues.jsonl` only; no sibling code edited.

Still required: §19.3 oracle synthesis, §19.4 placement, complete §19.5 shared
layout/native closure, §19.6 snapshots, §19.7 closed-unit fallback, remaining
§19.8 language extraction/envelope and §19.9 semantic budget/layout metadata,
general argument storage and full unmodified musl execution. No capability waived;
passing blocker tests is not full R/native acceptance. No push.
