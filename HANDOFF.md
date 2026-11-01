# Handoff — 2026-11-01T13:33:03Z

Stamped with real `date -u`. No push. Contract: dialect **0.2.10 @
023f5a771a814270634db3be9cfde88ded69f975**, ISA **0.8**. **M1 remains incomplete**;
no North-Star capability waived and no host libc/libm or marker fallback.

## Delivered

§19.1: C/IR/bitcode full-LTO external-tool pipeline, major18/23 library selection,
optional artifact SHA pins, post-link pipeline then real plugin. Rust links no LLVM.
§19.2: reversible/entry forwarding; plugin refuses, so no R/argv launch is claimed.
§19.5/17.7: two-stage strict native comparison adapter, actual materialised module,
runtime/arith hashes, O0+ASan/UBSan/O2 argv, scripts/maps, unresolved-symbol refusal.
§19.8: newest-major default23, basic mixed18/23 input read/link and target checks.
§19.9: ABI identity/module flag, complete tool/process/input receipts, canonical driver
build record/hash and certificate association, refreshed artifact inventories.
§25: JSON/line reports on argument, version, pin, plugin and native-link failures;
R implementation gap and normative BD-B-ISA7 dependency remain distinct.

## Verification and exact limits

`cargo test --offline`: **10 Rust test cases**, including real LLVM18/23 corpus
integration and detached-gate isolation. `cargo clippy --offline --all-targets --
-D warnings` and formatting pass. Integration compares SHA256 of all four unchanged
hashtable launch files with latest rung-2 evidence **20261101T130556.518962Z**.
Native O0/sanitizer and O2 baseline outputs agree; **driver native results remain
blocked**, not substituted with baseline binaries. Comparison links attempt the real
device module plus unmodified main_golden.c and refuse missing closure/markers.

Evidence comparison snapshots the exact recorded plugin **157d4bd1** (.so SHA
verified from report.json) and published runtime/arith bytes (local Git recovery of
pins if dirty dist differs). Live LLVM23 plugin changed during this session and now
hits **§5.2 PT2 budget exhausted** on unchanged hashtable: **bp-xv0**. Current default
plugin acceptance is not claimed. No corpus, budgets or contract were reduced.

Rung-3 exact no-major probe selects23; explicit18/23 probes each exit1 with real
unknown tier/entry option diagnostics, plus separate **BD-B-ISA7 / BLK-5** requirement.
Persistent argv, manifest, JSON/line reports and stderr: `/home/tobias/Projects/bennett-workspace/bennett-driver/.tmp/final-rung3-20261101T132818Z`.
The final detached gate receipt is `.tmp/final-pre-push.log`; the gate runs unit and
integration tests on committed pushed SHA, not the dirty checkout, and cleans up.

## Beads and remaining work

Driver **cyg.1 closed**; **cyg.2/3 blocked**. cyg.4 reports/gate is verified; umbrella
**bennett-driver-cyg remains open/blocked**. Upstream consumer beads:
**bp-xkg** (R/argv), **bp-xyn** (native materialisation/layout), **bp-xv0** (live PT2
regression), **brt-nuu** (native startup/musl/primitives/sanitizers),
**bennett-conformance-7n6** (two-stage comparison audit and explicit major probe).
Only exported `.beads/issues.jsonl` was committed in sibling repos; no sibling code.

§19.3 oracle synthesis, §19.4 placement, full shared comparison layout (§19.5),
snapshots (§19.6), closed-unit fallback (§19.7), remaining language extraction/mixed
front-end envelope (§19.8), and complete semantic budget/layout metadata (§19.9)
remain implementation obligations. Fix upstream R/native interfaces and then finish
those mechanics; passing refusal tests does not close cyg or establish rung3.
