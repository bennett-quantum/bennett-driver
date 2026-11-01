# bennett-driver

Rust orchestration of external LLVM 18/23 tools; no LLVM linkage or Cargo
network dependencies. Contract: dialect **0.2.10 @ 023f5a7**, ISA **0.8**.
M1 is **incomplete**: the full-LTO launch path works for the rung-2 corpus;
production R and native comparison still have explicit upstream blockers.

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
table and disk files are hashed. `--help` lists the primary options.

Output must be new or empty. It contains `linked.bc`, `postlink.bc`, plugin launch
artifacts, `manifest.json` (versions, options, hashes and full process receipts),
canonical `build.json`, `build.sha256`, and per-entry certificates associated with
the driver build hash. ISA object bytes stay unchanged; certificate inventory
hashes are refreshed. Failures produce `blockers.json` and `blockers.txt`; an
unusable output directory receives a structured stderr report without overwriting
an earlier build. Tools required: LLVM tools, Python3 stdlib, `sha256sum` and an
ELF linker invoked by clang. Plugin identity is queried in an isolated helper.

`--bennett-tier=reversible --bennett-entry=main` reaches the real plugin. Current
plugins refuse these options; reports distinguish that implementation gap from
ISA-0.8 `BD-B-ISA7`/BLK-5 typed R faults. No R launch or argv reply is fabricated.

For strict native links add `--bennett-comparison=true`, or use the consumer
adapter `--bennett-materialised=DIR/device.bc --bennett-llvm-major=M`.
The adapter defaults to `DIR/native-work`, does not re-run the materialiser, and
requires already materialised input. It accepts `--bennett-comparison-record=FILE`,
`--bennett-comparison-output=FILE`, `--bennett-sysroot=DIR`, and explicit
`--bennett-native-input=FILE` (host harness) / `--bennett-native-backend=FILE`
(comparison primitives). No marker definitions are supplied. Native records contain
both the `--only-needed` bitcode merge and final clang link argv, library hashes,
linker script and maps. O2 and O0+ASan/UBSan links use `-nostdlib -static -no-pie`;
auto-linking hosted sanitizer libraries is disabled. Data/text base options are
accepted. Full shared device/native layout, startup, musl and sanitizer closure
remain blocked; a link receipt alone is not a checked execution claim.

`cargo test --offline` runs unit tests and both-major integration against the
latest rung-2 evidence (`BENNETT_RUNG2_EVIDENCE` overrides it explicitly). Tests pin the exact plugin SHA from the selected evidence and
recover exact plugin-pinned library bytes from local Git history if dirty sibling
publications differ. They compare all four launch hashes and recorded native
baselines, then assert the driver's actual native-link refusal. Refusal tests
are not native acceptance. `scripts/pre-push` runs this suite in a clean detached
worktree of each pushed SHA. No CI and no push is performed here.

Oracle synthesis (§19.3), placement (§19.4), complete comparison layout (§19.5),
snapshots (§19.6), closed-unit fallback (§19.7), rlib extraction and the full
mixed-front-end envelope (§19.8), and complete §19.9 semantic budget/layout
metadata remain obligations under `bennett-driver-cyg`; unsupported options fail
with structured reports. See HANDOFF.md and docs/PROGRESS.md for exact blockers.
