# M1 — 2026-11-01 (incomplete, no push)

- §19.1/19.9 full-LTO pipeline: green on LLVM18/23. All four rung-2 launch
  byte hashes agree with latest evidence `20261101T130556.518962Z`. Real plugin
  ABI identity, optional pins, module flags, canonical build/certificate records.
- §19.2: exact mode/entry forwarding and refusal tests green; production R/argv
  launches blocked by **bp-xkg**. Report separately names **BD-B-ISA7 / BLK-5**
  on accepted ISA0.8; no ISA upgrade, fabricated launch or argv reply.
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
Current mutable LLVM23 plugin regressed during the final run: §5.2 PT2 budget
exhaustion on unchanged hashtable, filed as **bp-xv0**. Frozen evidence plugin
157d4bd1 still reproduces all four hashes; current default acceptance is not claimed.
Arith dirty publications differ from plugin pins: tests extract exact matching
local Git blobs into driver .tmp and never change sibling code or pins.
