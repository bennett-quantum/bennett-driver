# bennett-driver

Rust orchestration of external LLVM 18/23 tools, with no LLVM linkage or Cargo
network dependencies. Accepted contracts: dialect **0.2.13** and explicit historical
**0.2.10**, ISA **0.8**. The requested plugin identity must match exactly.

The driver accepts `.c`, `.bc` and `.ll` inputs. C uses clang `-O2 -flto -emit-llvm`;
verified inputs must declare matching target triples and data layouts before
linking. LLVM 23 is the default envelope; select 18 explicitly when required.
Inputs with a selected device entry link the runtime/arithmetic closure, run the
post-link pipeline (default `lto<O3>`) and invoke the external Bennett plugin.
Unmarked inputs build an ordinary native executable or library object, retaining
host startup and libc. Device controls unused on that route appear explicitly in
`unused_device_options`; strict device comparison requires a materialised device
module. Mixed native machine-code/device linking remains a required capability
pending its published container and host-entry ABI.

External dependencies are explicit. Supply `--bennett-plugin=FILE`,
`--bennett-runtimes=FILE`, `--bennett-arith=FILE`, and optional matching SHA-256
pins, or the corresponding `BENNETT_DRIVER_PLUGIN`, `BENNETT_DRIVER_RUNTIMES` and
`BENNETT_DRIVER_ARITH` environment variables. Comparison additionally requires
`NATIVE_CHECK`, `NATIVE_SUPPORT` and `SYSROOT`; arithmetic instance generation
requires `ARITH_GENERATOR`. There are no live-sibling path defaults.
`--help` lists the CLI spellings. `TMPDIR` must name a writable task directory;
children retain it and lose desktop/browser environment settings.

```sh
unset DISPLAY WAYLAND_DISPLAY DBUS_SESSION_BUS_ADDRESS BROWSER
mkdir -p .tmp/task
export TMPDIR="$PWD/.tmp/task"
cargo build --offline -j3
# Set external paths above to the intended immutable publications.
./target/debug/bennett-driver -bennett-dialect=0.2.13 \
  -bennett-out=.tmp/example input.ll
```

Output directories must be new or empty. Production emits `linked.bc`,
`postlink.bc`, plugin artifacts, `manifest.json` with versions/options/hashes and
process receipts, and hash-bound `build.json`/certificates. Native-only builds
emit `host.bc`, `native-host` or `native-host.o`, and an empty device inventory.
Failures produce structured `blockers.json`/`blockers.txt`; a failed later
comparison also refreshes the existing public build receipt. Old evidence is
never overwritten when an output directory is already populated.

`--bennett-tier=reversible --bennett-entry=SYMBOL` selects process preparation;
`--bennett-emit=process-bitcode` stops at the explicitly labelled preparation
stage. The accepted ISA 0.8 producer can emit `BD-B-ISA7` for required typed
reversible fault handling. A blocked component run is not full acceptance.
Snapshots, class tables and fixed vscale have driver preparation stages; configured
classes, descriptor device models, oracle entry ownership and remaining backend
controls retain their full capability obligations. See [quality notes](docs/quality.md)
and dated reviews for exact evidence and open publication dependencies.

Strict native comparison uses `--bennett-comparison=true`, or
`--bennett-materialised=DIR/device.bc` for an existing module. The latter defaults
to `DIR/native-work`. It requires a resolved shared layout (adjacent launches or
`--bennett-comparison-layout=FILE`), checks aliases/input hashes, merges the
published check/support/runtime closure, and emits plain O2/O0 freestanding
executables. No host libc/libm fallback is used. Receipts retain exact commands,
hashes, symbol/layout audits and explicit sanitizer limitations.
`--bennett-classifier-input=FILE` requests a separate original-C UBSan diagnostic;
without original C its blocked diagnostic does not invalidate LLVM-input native
comparison. Full freestanding ASan remains a producer publication dependency.
Linked receipts alone do not claim native/VM agreement.

`cargo test --offline -j3 -- --test-threads=4` runs the default suite against
verified `gate.toml` pins. Materialise missing pins with the pinned gate tool's
`verify` command; tests fail with a single actionable pin error when absent.
The slow arithmetic generators run with
`cargo test --offline -j3 --test fixtures -- --ignored --test-threads=4` and are
required by the gate. Promised configured-class/device-model tests and the blocked
tracked rung-2 fixture have separate named `--ignored` reports in `gate.toml`;
those tests keep their full success assertions. Timing, coverage and the structural
quality baseline are recorded in [docs/quality.md](docs/quality.md).
`scripts/pre-push` delegates each pushed SHA to the pinned local gate tool.
