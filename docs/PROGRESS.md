# Native comparison integration — 2026-11-01 (in progress, no push)

Published native-support merge, required resolved-layout table and plain O0/O2
strict links pass both-major adapter diagnostics, including allocator execution,
no undefined symbols and no ELF interpreter. ASan/UBSan row explicitly blocked
on brt-nuu.1. Corpus/plugin acceptance remains under test; diagnostic inputs are
not acceptance. Missing layout and mismatched native data end fail loudly.

# M1 — 2026-11-01 (incomplete, no push)

- §19.1/19.9 full-LTO pipeline: green on LLVM18/23. All four rung-2 launch
  byte hashes agree with latest evidence `20261101T130556.518962Z`. Real plugin
  ABI identity, optional pins, module flags, canonical build/certificate records.
- §19.2: mode/entry forwarding; live plugin now emits R argv/console launches on
  both majors with **BD-B-ISA7 / BLK-5**. Driver verifies blocked outputs, finalises
  metadata and emits empty argv/envp header replies (or checks supplied replies).
  No ISA upgrade. Nonempty argument packing/storage and full R acceptance remain
  outstanding; **bp-xkg** has the upstream history, and cyg.2 stays blocked.
- §17.7/19.5: strict actual-materialised comparison adapter and O0+ASan/UBSan/O2
  link attempts; **no driver-produced native result yet**. Runtime/musl/startup/
  primitive/sanitizer closure **brt-nuu**, materialisation/layout **bp-xyn**,
  conformance adapter **bennett-conformance-7n6**. Recorded hosted native O0/O2
  baselines agree; they are not reused as driver output.
- §25: structured JSON and line reports preserve exact errors and distinguish
  implementation refusals from normative ISA dependencies. Unsupported options,
  bad SHA/identity/module flag, mixed targets, unreadable newer IR and defined
  markers are tested. No host libc/libm fallback and no plugin skipping.
- Detached pre-push gate tests committed pushed SHA, headless, offline, including
  real two-major integration (exact evidence-pinned plugin/library bytes). Dirty checkout isolation and cleanup are tested.

Red receipts: original stub accepted wrong version and emitted no module;
mode flags rejected before plugin; comparison adapter absent; errors lacked
reports; old hook tested dirty checkout. All corresponding regressions now pass.

Slices: cyg.1 closed; cyg.2 and cyg.3 blocked, not force-closed; cyg.4 covers
reports/gate. Umbrella cyg remains open. §19.3/4/6/7 and remaining full §19.8/9
mechanics are deferred implementation obligations, not waived capabilities.
Both live and frozen LLVM23 plugin hit §5.2 analysis guards under loaded builds,
filed as **bp-xv0**. Source inspection identifies a 30000ms compiler wall-clock
allowance. Integration now explicitly records 300000ms via the driver option;
execution budgets, corpus and exact expected object hashes are unchanged.
Default 30000ms acceptance under load is not claimed.
Arith dirty publications differ from plugin pins: tests extract exact matching
local Git blobs into driver .tmp and never change sibling code or pins.
