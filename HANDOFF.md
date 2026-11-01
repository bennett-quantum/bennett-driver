# Handoff — native comparison integration

Updated UTC: **2026-11-01T14:41:16Z** (`date -u`). No push/network. Accepted dialect
**0.2.10 @023f5a771a814270634db3be9cfde88ded69f975**, ISA **0.8**.
**M1 remains incomplete. cyg.2/3 and cyg remain blocked.**

## Implemented and verified

Implementation commits **5309ab5**, **ac342d769df1e41abdf9fa738ef2edcc5e785f56**.
The strict native adapter consumes actual plugin `device.bc`, matching-major
production runtimes and arith, then driver layout + explicit harness bitcode +
published `musl-sysroot/lib/native-support.bc` via --override, then production
runtime/arith --only-needed again. The full native runtime is never used to
replace materialised functions. Harness main is a retained root, not a library
that --only-needed can drop before startup is introduced. No fake markers,
host CRT/libc/libm, hosted sanitizer fallback or plugin skipping.

O0 codegen introduced a memcpy libcall after bitcode dependency closure.
Retain missing published memcpy/memmove/memset bodies and close their imports
again. Extracting recursively duplicated an already materialised memcpy in
LLVM23 hello; extraction now preserves existing bodies and follows dependencies
through a separate --only-needed closure. strip-dead-prototypes,verify removes
dead marker prototypes after transport override. Every process/library hash,
linker script/map, native import audit and variant result is recorded.

Driver emits `__bennett_rt_native_layout` as an 8-byte-aligned LP64 constant
`{1, heap_base, heap_limit_max}`, from the common resolved launch-object layout.
Adapter consumers may pass `--bennett-comparison-layout=FILE`; absent layout
fails, never defaults. `__bennett_rt_blk.<f>` remains §14.9 block identity.
The byte limit drives runtime allocation history capacity. Linker asserts the
first page after native data equals the resolved heap base. Default text uses
the first 2MiB boundary above occupied device ranges (at least0x400000), not
2^H when H only bounds them. Unmapped globals/arena/interfaces remain explicit
implementation blockers; full global/function address replication is unfinished.

Both-major marker-free **adapter diagnostics**, including explicit harness
roots, run plain O0/O2 binaries: required exact allocation base, zero fill,
store/free, no undefined imports or ELF interpreter. These are not corpus
acceptance. Four persistent successful binaries are under
`.tmp/native-probes-20261101T142910Z/{18,23}/primitive-diagnostic/out/native-O{0,2}`.
ASan/UBSan has its own structured **blocked** row on **brt-nuu.1**; plain O0
is a separate diagnostic, never relabelled a sanitizer pass. §17.7 baseline is O2.

## Actual corpus: still red

Fresh plugin code **e1f797e**, immutable .so/library snapshot manifest and all
actual driver commands/outputs:
`/home/tobias/Projects/bennett-workspace/bennett-driver/.tmp/native-probes-20261101T142910Z`.
`native-summary.json` distinguishes successful diagnostics from blocked corpus.

- **LLVM18/23 hashtable:** driver full-LTO/plugin emits both entry launches.
  The actual materialised module retains **__bennett_qalloc, __bennett_qfree**.
  Both strict plain O2/O0 native links remain red, with **BD-E-NATIVE-MARKERS**
  and exact symbols (**bp-xyn**). No driver-native ten-case results exist yet.
  Layout heap_base4096 also cannot follow startup/musl/harness/table data.
- **LLVM18 real unmodified musl hello.c:** production stops at §12 N21/N27
  vector intrinsic lane materialisation, **llvm.fshl.v4i32** (**bp-ozp**),
  before device.bc. No permissible native comparison input.
- **LLVM23 real hello.c:** real R output, argv/console launch, **BD-B-ISA7**
  (**bp-is0**). Adapter of its actual device.bc finds inlined
  **__bennett_effect_console_write** in __stdio_write (**bp-xyn**); native
  transport override cannot rematerialise it. Strict native links stay red.
  Device globals use ISA names without an LLVM symbol/address correspondence.
- R tier/entry options are accepted; historical missing-mode refusal is not the
  current blocker. General nonempty argv storage/packing and full R/reset/replay
  remain required. No silent ISA0.9 upgrade. Minimal argv/console probes still
  produce and preserve real blocked R artifacts on both majors.

For exact final native attempts see each corpus directory's `native-verified/`
manifest, native-comparisons.json, blockers.json/txt and stdout/stderr.
Runtime native publication consumed from **5c045f9**, production SHAs unchanged;
consumer-note-only runtime commit **d8f7591** changes no tested artifact bytes.

## Verification and tracking

**11 Rust tests PASS**, offline; formatting and clippy --all-targets -D warnings.
Clean detached **scripts/pre-push PASS at ac342d7**, receipt
`.tmp/native-clean-pre-push.log`; script remains unchanged and cleans its worktree.
The final handoff/bead commit changes no tested code. Gate used explicit
`BENNETT_DRIVER_TEST_ARTIFACTS=.tmp/native-probes-20261101T142910Z` (absolute in
actual invocation) to avoid racing the plugin rebuild. CLI SHA pins all checked.
Compiler analysis allowance explicitly300000ms; **bp-xv0** retains default30s
under-load issue. No execution budget, corpus, expected hash or pin relaxed.

All four frozen-evidence launch hashes remain equal to rung-2 receipt
**20261101T130556.518962Z**, using its exact separate frozen plugin/library bytes.
Ten native golden bytes agree with archived VM/reference forwards on both
majors; hosted evidence binaries rerun at O0/O2 agree. Those outputs are not
substituted for driver-native output. Corpus blockers and positive diagnostics
are tested separately. Native layout missing/mismatch/global-map/overflow/text
overlap and exact first-2MiB-above-large-heap rules are also checked.

No beads closed or newly filed: existing dependencies already cover the gaps.
Driver cyg/cyg.2/cyg.3 updated; plugin **bp-xyn, bp-xkg, bp-ozp** updated
(export-only commit **dccc18c**, bp-ozp now includes driver/comparison labels);
runtime **brt-nuu** updated (export-only **d8f7591**). **brt-nuu.1** remains open.
Sibling source code untouched; ongoing sibling sanitizer work left intact.

Still required beyond these blockers: complete shared §19.5 layout and native/
executor outcomes, §19.3 synthesis, §19.4 placement, §19.6 snapshots, §19.7
closed-unit fallback, remaining §19.8 frontend extraction/envelope and §19.9
semantic metadata. No North-Star capability waived. No push.
