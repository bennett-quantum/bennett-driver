# Native comparison — 2026-11-01 (M1 incomplete; no push)

- §17.7/19.5 published support integration: both-major plain O0/O2 adapter
  diagnostics link and execute strict static binaries with no undefined imports
  or ELF interpreter. Harness main is retained before final runtime closure;
  codegen ABI memory definitions come from published runtimes, preserving any
  already materialised definitions. No host libc/libm or full-native overwrite.
- Emit `__bennett_rt_native_layout = {1, heap_base, heap_limit_max}`, align8,
  from the actual resolved launch layout (or explicit consumer layout JSON).
  Never reinterpret `__bennett_rt_blk.<f>`. Native data-end/heap equality and
  disjoint text range are checked; missing mapping is an explicit blocker.
- **Actual hashtable LLVM18/23: native ten cases blocked**, exact residual
  `__bennett_qalloc`, `__bennett_qfree` (**bp-xyn**). All four launch hashes
  still agree with rung-2 evidence `20261101T130556.518962Z`; its ten hosted
  native/VM/reference results agree. No driver-native results substituted.
- **Actual hello LLVM18:** N21/N27 `llvm.fshl.v4i32` (**bp-ozp**) before
  device emission. **LLVM23:** real R output + **BD-B-ISA7** (**bp-is0**);
  actual device retains `__bennett_effect_console_write` (**bp-xyn**).
- Shared comparison layout remains **cyg.3 / bp-xyn**: rung-2 heap4096 cannot
  follow native startup/musl/harness/table data; hello lacks LLVM ↔ ISA global
  symbol map. Global/function/arena/interface layout replication remains required.
- ASan/UBSan diagnostic row explicitly **blocked on brt-nuu.1**. Plain O0 is
  distinct from the optimised §17.7 comparison. No sanitizer instrumentation
  silently disabled and called a sanitizer pass.
- §25 structured reports list exact residual symbols and separate implementation
  and ISA blockers. **cyg.2/3 and cyg stay blocked**, no capability waived.
- Verification: 11 Rust tests, both-major native adapter and real-corpus blocker
  regressions, clippy -D warnings, formatting; detached clean pre-push gate.
  Persistent fresh-plugin receipts: `.tmp/native-probes-20261101T142910Z`
  (plugin code e1f797e). Frozen evidence plugin remains separate.

# Earlier M1 handoff — superseded by the native comparison block above

- §19.1/19.9 full-LTO pipeline: green on LLVM18/23. All four rung-2 launch
  byte hashes agree with latest evidence `20261101T130556.518962Z`. Real plugin
  ABI identity, optional pins, module flags, canonical build/certificate records.
- §19.2: mode/entry forwarding; live plugin now emits R argv/console launches on
  both majors with **BD-B-ISA7 / BLK-5**. Driver verifies blocked outputs, finalises
  metadata and emits empty argv/envp header replies (or checks supplied replies).
  No ISA upgrade. Nonempty argument packing/storage and full R acceptance remain
  outstanding; **bp-xkg** has the upstream history, and cyg.2 stays blocked.
- §17.7/19.5: strict actual-materialised comparison adapter (historical missing-closure state) and O0+ASan/UBSan/O2
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
