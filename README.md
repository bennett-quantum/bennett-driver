# bennett-driver

Rust orchestration of external LLVM 18/23 tools; no LLVM linkage or Cargo
network dependencies. Contract: dialect **0.2.10 @ 023f5a7**, ISA **0.8**.
M1 is **incomplete**: the full-LTO launch path works for the rung-2 corpus;
production R and corpus native comparison still have explicit upstream blockers.
Plain O0/O2 native-support adapter diagnostics execute on both majors.

```sh
unset DISPLAY WAYLAND_DISPLAY DBUS_SESSION_BUS_ADDRESS BROWSER
export TMPDIR=/home/tobias/Projects/bennett-workspace/bennett-driver/.tmp
cargo build --offline
./target/debug/bennett-driver --bennett-llvm-major=18 \
  -bennett-dialect=0.2.10 -bennett-isa=0.8 -bennett-out=.tmp/example \
  -bennett-budget-default=10000000,1048576,65536,256,65536 \
  ../bennett-conformance/ladder/rung-2/fixtures/hashtable_marked.c
```

Inputs: `.c`, `.bc`, `.ll`. C uses clang `-O2 -flto -emit-llvm`; all inputs and
major-matched runtimes/arith are merged with `llvm-link --only-needed`, followed
by `lto<O3>` and the `bennett` plugin. Default major: **23**, the newest envelope
major. Specify 18 explicitly for LLVM18 receipts. Mixed input targets fail loudly.
Plugin ABI identity and optional input module flags are checked, never bypassed.

Override artifacts with `--bennett-plugin=FILE`, `--bennett-runtimes=FILE`,
`--bennett-arith=FILE`; defaults are sibling `build/libbennett-plugin-M.so` and
`dist/llvmM/<repo>.bc`. Each accepts a `--bennett-<name>-sha256=HEX` pin.
`--bennett-pipeline=PIPELINE` overrides post-link LTO; LLVM view passes are forbidden.
`--bennett-sysroot=DIR` supplies the C header sysroot. Budget options pass through;
table and disk files are hashed. `--bennett-analysis-budget-ms=N` explicitly
controls the plugin's compiler wall-clock allowance (default plugin value: 30000ms).
Integration records 300000ms for loaded local builds; execution budgets are unchanged. `--help` lists the primary options.

Output must be new or empty. It contains `linked.bc`, `postlink.bc`, plugin launch
artifacts, `manifest.json` (versions, options, hashes and full process receipts),
canonical `build.json`, `build.sha256`, and per-entry certificates associated with
the driver build hash. ISA object bytes stay unchanged; certificate inventory
hashes are refreshed. Failures produce `blockers.json` and `blockers.txt`; an
unusable output directory receives a structured stderr report without overwriting
an earlier build. Tools required: LLVM tools, Python3 stdlib, `sha256sum` and an
ELF linker invoked by clang. Plugin identity is queried in an isolated helper.

`--bennett-tier=reversible --bennett-entry=main` reaches the real plugin. Current
plugins emit the R argv/console launch and report ISA-0.8 `BD-B-ISA7`/BLK-5.
The driver verifies and retains these artifacts/build records with status `blocked`
and a nonzero exit. Per-entry `argv-replies.json` defaults to the empty argc/argv/envp
header; `--bennett-argv-replies=FILE` supplies a checked public-executor reply array.
Nonempty argument storage must already be laid out by the caller; automatic packing
remains required work. Older plugins' missing-mode refusals are recorded distinctly.

For strict native links add `--bennett-comparison=true`, or use the consumer
adapter on the plugin's actual output:

```sh
./target/debug/bennett-driver --bennett-llvm-major=18 \
  --bennett-materialised=DIR/device.bc \
  --bennett-native-input=../bennett-conformance/ladder/rung-2/fixtures/main_golden.c
```

The adapter defaults to `DIR/native-work`, never re-runs or skips the plugin,
and accepts `--bennett-comparison-record=FILE`, `--bennett-comparison-output=FILE`,
`--bennett-native-input=FILE` (comparison harness), `--bennett-native-backend=FILE`
(explicit comparison support), and `--bennett-sysroot=DIR`. Harness/support inputs
are compiled to bitcode with published musl headers; marker definitions fail.
`--bennett-native-support=FILE` selects matching-major `native-support.bc`
(default sibling `dist/llvmM/musl-sysroot/lib/native-support.bc`), with optional
`--bennett-native-support-sha256=HEX` pin. The full `bennett-runtimes-native.bc`
is for original-input baselines and is **never** used to overwrite materialised
functions here. Production still links `bennett-runtimes.bc`.

The exact native bitcode order is:

1. `device.bc runtimes.bc arith.bc --only-needed` → `comparison-linked.bc`.
2. That module, explicit harness/support and `native-layout.bc`, with
   `--override=native-support.bc` → `comparison-adapted.bc`. Harness main is
   retained as a root before startup's closure is resolved.
3. Adapted module, production runtimes then arith, `--only-needed` → `comparison.bc`.
4. Retain missing published `memcpy/memmove/memset` bodies with `llvm-extract`,
   without recursively duplicating existing bodies; close their runtime imports
   again. `opt -passes=strip-dead-prototypes,verify` removes dead prototypes.
5. Same-major clang, plain `-O2` comparison / `-O0` diagnostic, `-nostdlib
   -nostdinc -static -no-pie -fno-merge-all-constants`, fixed linker script,
   `_start`, `--no-undefined`; audit final imports. No host CRT/libc/libm.

`native-layout.ll/bc` defines the required 8-byte-aligned LP64 constant
`__bennett_rt_native_layout = {1, heap_base, heap_limit_max}`. Values come from
one common resolved `layout` section across adjacent `launches.json` objects.
`--bennett-comparison-layout=FILE` supplies that resolved layout JSON explicitly
for an already materialised consumer input; the file/hash is recorded. There is
no heap default and `__bennett_rt_blk.<f>` remains block identity (§14.9).
Native allocation history capacity is derived by runtimes from the byte limit.
`--bennett-layout-data-base` defaults to 4096; text defaults to 0x400000 or the next
2MiB boundary above the resolved device ranges. Explicit text/data options are
checked. The linker asserts that the first page boundary after native data equals
the device heap base; it never silently relocates the heap. Shared global/function
and arena/interface symbol mapping remains required; unmapped resolved data/regions
fail loudly instead of claiming common addresses.

`native-comparison.json` is the O2 receipt; `native-comparisons.json` records
plain O2, plain O0 and an explicitly **blocked** ASan/UBSan row (`brt-nuu.1`).
The manifest retains every merge/codegen/audit command, library/layout hashes,
linker scripts and maps. A linked receipt is not executor/native agreement.
Residual marker symbols are listed under `residual_markers` and reported as
`BD-E-NATIVE-MARKERS` / `bp-xyn`, separately from native-layout failures.

Current actual corpus verdicts: both majors' hashtable device modules retain
`__bennett_qalloc/qfree`; the ten driver-native results remain blocked on
`bp-xyn` and shared layout (`cyg.3`). LLVM18 real musl hello stops before device
emission at vector `llvm.fshl.v4i32` materialisation (`bp-ozp`). LLVM23 emits R
artifacts with `BD-B-ISA7` (`bp-is0`), but its device module retains an inlined
`__bennett_effect_console_write` (`bp-xyn`). No driver-native hello claim.

`cargo test --offline` runs unit tests and both-major integration against the
latest rung-2 evidence (`BENNETT_RUNG2_EVIDENCE` overrides it). Tests pin its plugin
and recover exact plugin-pinned library bytes from local Git history if sibling
publications differ. All four launch hashes and the ten recorded native/VM/reference
results must agree. Actual driver native links must preserve their precise marker
blockers. Separate marker-free adapter diagnostics run strict O0/O2 allocation
binaries and check required layout, harness retention, layout mismatch/overlap and
no undefined imports/ELF interpreter. These diagnostics are not corpus acceptance.
Real unmodified hello's production/native frontiers are also checked.
`scripts/pre-push` tests each pushed SHA in a clean detached worktree.
`BENNETT_DRIVER_TEST_ARTIFACTS=DIR` selects an explicit immutable local artifact
manifest during sibling rebuilds; all CLI pins are verified. No push is performed.

Oracle synthesis (§19.3), placement (§19.4), complete comparison layout (§19.5),
snapshots (§19.6), closed-unit fallback (§19.7), rlib extraction and the full
mixed-front-end envelope (§19.8), and complete §19.9 semantic budget/layout
metadata remain obligations under `bennett-driver-cyg`; unsupported options fail
with structured reports. See HANDOFF.md and docs/PROGRESS.md for exact blockers.
