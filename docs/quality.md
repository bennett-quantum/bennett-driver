# Driver quality measurements

Round 1 preserves the pin-discipline branch and its plugin-native-comparison pin
`5a092cded3ba3351ba8cc2977a7eaf3b40f46526`.

The promised capability tests stay visible under named switches:
`cargo test --offline -j3 --test classes --test device_models --test pipeline --no-fail-fast -- --ignored --nocapture --test-threads=4`.
The quality job reproduced three failures: configured classes at dialect §3.4
(bennett-driver-9zg), scalar descriptor dispatch at §8.4 (bennett-driver-7y4),
and the missing tracked conformance `driver-regression/report.json`
(bennett-driver-ppz). Gate reports retain these expected failures. The exact
producer publication requests remain in their beads; these are capability
obligations, not accepted refusals or removed tests.

Default test timing before the split: `timeout 180 cargo test --offline -j3 -- --test-threads=4` timed out (exit 124). After consolidating 26 fixture wrappers and moving the two offline arithmetic generators to the gate's slow check, the same command passed in 154.19 s (7 unit tests, 24 active fixture tests, 2 pipeline checks; 5 named ignored tests). Test-profile debug information is line tables only. Job-local target/TMPDIR, headless environment and verified gate-pin checkouts were used. No consumer or full push gate was run.

Coverage before the stage refactor: **91.85% lines** (2,199/2,394), measured with
`timeout 240 cargo llvm-cov --offline -j3 --summary-only -- --test-threads=4`.
The run passed against the gate pins, including Python-spawned driver processes.
`environment` explicitly checks that `LLVM_PROFILE_FILE` survives external commands.
No coverage threshold is imposed.

Five least-covered Rust modules in that run:

| Module | Line coverage | Treatment |
|---|---:|---|
| llvm_utility | 86.14% | New red-first cache placement/execution and missing TMPDIR tests; remaining allocator/OS publication failures are platform error paths. |
| native_adapter | 88.66% | Real pinned prepare/check/finalise tests cover the published API; complete producer acceptance still depends on the open producer publications. |
| main | 89.91% | Option and stage boundary unit tests are part of the next refactor, alongside the existing target/alias/metadata matrices. |
| report | 90.32% | Structured error/code/exit integration tests execute the principal report classes; secondary report-write failure requires filesystem fault injection. |
| output_paths | 90.62% | Direct/canonical/symlink/hardlink/prior-artifact alias matrices execute real filesystem protection; uncommon metadata/read failures remain platform paths. |

Test quality pass: the merge differential runs actual `postlink.bc` under lazy
`lli` for LLVM 18/23 against an independently source-compiled native executable
and nine hand-derived `7*n + 13` results. Changing the helper to `8*n + 13`
provides a negative oracle control. It does not depend on the blocked rung-2
fixture. Native comparison tests retain ELF/import/execution and input-hash
oracles and remove redundant flag/provenance-literal assertions. Classifier tests
execute a real out-of-bounds input and inspect its UBSan failure instead of
asserting hard-coded coverage booleans. JSON tests cover Unicode, all special
control-escape classes and exact u64 maximum output.

The hook fixture checks this repo's pin inputs and delegation stub; protocol
execution belongs to the pinned gate tool's selftests. Reversible blocked output
is component evidence only: full producer acceptance remains in the open producer
beads and the unchanged promised tests, not an existence-only success claim.

Stage refactor validation: 17 unit tests pass with
`timeout 90 cargo test --offline -j3 --bin bennett-driver -- --nocapture --test-threads=4`;
`timeout 90 cargo clippy --offline -j3 --all-targets -- -D warnings` passes.
An old/new executable differential (`timeout 180 python3 .tmp/quality-driver/byte_identity.py`)
reused identical input/output paths and hashed every emitted file: LLVM 18 and 23
native-only builds (49 files each), device builds (49 each), and strict comparison
builds (82 each) were byte-identical. The independent merged-module fixture also
passes after the refactor. Typed option keys and execution controls have one parser
and one default owner; production environment/admission/link/lowering and comparison
admission/check/layout-and-closure/codegen stages each have a direct unit test.

The fail-fast sweep retained the earlier pin branch's explicit external-path and
TMPDIR requirements (no compile-time or live-sibling defaults). It also reproduced
and fixed a stale public receipt after a later device comparison failure:
`timeout 120 cargo test --offline -j3 --test fixtures pipeline_metadata -- --nocapture --test-threads=4`
went from red (`build.json complete`, manifest failed) to green on both majors.
Existing receipts now refresh their failure status and certificate/build bindings.

Hygiene verification: the tracked-source scan found the stale `docs/PROGRESS.md`
and 15 process identifiers in product/test bodies before cleanup; afterwards both
lists are empty. Named promised-test switches retain their bead names. Product
refusals now name the missing mixed-container/host-entry contract or freestanding
ASan capability directly. `SPEC_VERSIONS.toml` records the accepted 0.2.13 dialect,
its pinned published specification, explicit historical 0.2.10 compatibility and
unchanged ISA 0.8. README now describes explicit dependencies and the real test
split. Native-host and pipeline negative fixtures pass after the diagnostic changes.

The structural ratchet is one local gate check: `python3 scripts/quality.py`.
`--show` prints current measurements; `--record` explicitly records a baseline
change for review. The JSON below records each tracked Rust/C++/Python source
file's function count, longest function, counts longer than 25/50/100/200/300
lines, cognitive-complexity mass and trivial-wrapper count. Python uses AST
control nesting; Rust/C++ use a reproducible lexical control-nesting proxy after
removing comments/literals. This is a local regression measure, not a standard
Sonar score. Short single-expression forwarding functions (at most six lines)
are counted as wrappers; added wrappers cannot conceal a split.

The check rejects an increase in any per-file complexity, longest function,
length-tail count or wrapper count, plus new tracked litter or process identifiers.
New files start from zero, so moving complexity requires an explicit reviewed
baseline change. Deleted files cannot offset increases elsewhere. `Cargo.lock` is
required source metadata and is excluded from transient-lock litter. Source test
names and named promised switches may carry bead names; emitted messages and
fixture bodies may not. These definitions and hand-derived control-depth cases
are covered by nine ratchet mutation tests. No numerical target or coverage
threshold is imposed.

The anti-slop pass keeps backend arguments as parsed `(OptionKey, value)` pairs
through preparation/filtering/forwarding; no rendered argument is reparsed to
recover classes or dispatch backend controls. Repeated controls preserve input
order, covered directly in the 18-test unit suite. This follow-up passes the
existing structural baseline without relaxing it.

The hygiene grep covers all tracked content under `src/`, `scripts/` and `tests/`,
including extensionless hook/tool scripts; a dedicated mutation test prevents that
path from escaping the gate. Byte decoding for the grep preserves all ASCII
identifiers even in non-UTF-8 fixtures; language metrics still parse only the
listed source languages.

Final verification after typed forwarding and receipt/hygiene fixes:

| Command | Result |
|---|---|
| `timeout 180 cargo test --offline -j3 -- --test-threads=4` | PASS, **109.15 s** wall time; 18 unit + 26 fixture + 2 pipeline tests, 5 explicitly named ignored tests. |
| `timeout 240 cargo llvm-cov --offline -j3 --summary-only -- --test-threads=4` | PASS, **92.76% Rust lines** (2,510/2,706); subprocess profiles included. |
| `timeout 360 cargo test --offline -j3 --test fixtures -- --ignored --nocapture --test-threads=4` | PASS, both arithmetic generator fixtures; test binary finished in 56.37 s. |
| `python3 scripts/quality.py` | PASS; 60 tracked source files, 219 functions, longest 207 lines, 69 conservative wrapper matches, no litter/identifiers. |
| `timeout 30 python3 tests/quality.py` | PASS, 9 independent metric/mutation tests. |
| `cargo fmt --all --check` and `timeout 90 cargo clippy --offline -j3 --all-targets -- -D warnings` | PASS. |

The final forwarding follow-up also passed the six-build byte-identity matrix
(`timeout 180 python3 .tmp/quality-driver/forwarding_identity.py`): another 360
emitted files matched across both LLVM majors and all three build routes.

The final coverage run's five least-covered modules are llvm_utility (86.14%),
options (86.23%), native_adapter (88.89%), report (90.32%), and output_paths
(90.62%). The table above the refactor records the existing treatment for four;
the new options module has direct typed-default, repetition/order, forwarding,
unknown/duplicate and scope-validation tests plus CLI configuration matrices.
Remaining uncovered option branches are malformed-input/control variations;
opaque backend controls still depend on the named producer capabilities. The
whole suite includes their positive preparation paths and explicit error paths.

The final named promised/blocked report command
`timeout 60 cargo test --offline -j3 --test classes --test device_models --test pipeline --no-fail-fast -- --ignored --nocapture --test-threads=4`
returns 101 as expected: configured register classes, scalar descriptor finite
dispatch, and the missing tracked conformance report remain red. No success
assertion was removed or weakened. The plugin-native-comparison pin remains
`5a092cded3ba3351ba8cc2977a7eaf3b40f46526`. Full push-gate and review orchestration
remain the maintainer's merge step.

Round-2 review fixes preserve the baseline below. Comparison admission now
inventories every existing output file and directory before writing comparison
artifacts. The direct unit matrix covers 11 evidence kinds, both configurable
destinations, and direct/symlink/hardlink aliases; it asserts unchanged bytes
and zero executed commands. The real LLVM 18/23 marked-`top` reproduction covers
the launch inventory, root build/hash, and each required entry artifact, including
the certificate. All fail with `BD-E-OUTPUT-PATH` before comparison writes; the
certificate retains its producer and the error-finalisation refresh keeps its
receipt hash valid. This closes bennett-driver-av7.

The hygiene classifier now masks only a named Rust `#[ignore = "..."]`
attribute span. Code following it on the same line is scanned. Rust production
and Python test function bodies are scanned too; valid function identifiers
need no exemption. The actual CLI mutations first failed for three previously
hidden inline bodies, then all **13 tests passed**, including the legitimate
promised-switch control. This closes bennett-driver-a79.

Round-2 verification (headless, job-local TMPDIR/CARGO_TARGET_DIR, pinned siblings):

| Command | Result |
|---|---|
| `timeout 900 cargo test --offline -j3 -- --test-threads=4` | PASS, **60.85 s** wall; 19 unit + 26 fixture + 2 pipeline tests, 5 existing named ignored tests. |
| `timeout 90 cargo test --offline -j3 --bin bennett-driver -- --nocapture --test-threads=4` | PASS, 19 tests; artifact bytes unchanged during admission rejection. |
| `timeout 180 cargo test --offline -j3 --test fixtures output_paths -- --nocapture --test-threads=4` | PASS, real LLVM 18/23 evidence collision matrix, 9.61 s. |
| `timeout 30 python3 -B tests/quality.py` | PASS, 13 CLI/metric mutation tests; three new cases demonstrated red before the fix. |
| `timeout 300 cargo llvm-cov --offline -j3 --summary-only -- --test-threads=4` | PASS, **92.73% Rust lines** (2,564/2,765); subprocess profiles included. |
| `cargo fmt --all --check`, `timeout 90 cargo clippy --offline -j3 --all-targets -- -D warnings`, `git diff --check` | PASS. |
| `timeout 30 python3 scripts/quality.py` | **RED (exit 1)**, structural growth listed below; zero litter/process identifiers. |

At `ebe54e5`, the added inventory guard and exhaustive regressions exceeded the
existing structural baseline. The follow-up for bennett-driver-qrd reproduced
that failure, then restored the ratchet through restructuring. **The baseline,
thresholds and source scope are unchanged**; the baseline JSON is byte-identical
to reviewed `35a7d27`.

| Source | Existing baseline | At `ebe54e5` | After restructuring |
|---|---:|---:|---:|
| `src/native.rs` complexity | 138 | 153 | 136 |
| `src/native.rs` functions over 25 lines | 5 | 6 | 5 |
| `src/output_paths.rs` complexity | 33 | 40 | 33 |
| `tests/output_paths.py` complexity | 8 | 12 | 7 |

The admission regression retains all 11 artifact kinds and all six combinations
of destination option and alias kind, with byte-preservation and zero-command
assertions. Named setup and rejection phases replace the nested test body. Missing
and non-directory inventories are additional table-driven admission error cases.
The recursive inventory has one owner; opening and collecting directory entries
share its contextual error mapping. Input and earlier-destination collisions
share one rejection branch, preserving their order and diagnostic text. Native
variant paths are table data, and the marker audit selects the same first marker.
Python conjunctions become individual assertions; every original check remains.

Follow-up verification (same headless job environment and gate pins):

| Command | Result |
|---|---|
| `timeout 30 python3 scripts/quality.py` | PASS; previously reproduced all four structural overages at `ebe54e5`. |
| `timeout 900 cargo test --offline -j3 -- --test-threads=4` | PASS, **60.57 s** wall; 20 unit + 26 fixture + 2 pipeline tests, the same 5 named ignored tests. Includes the LLVM 18/23 published-evidence collisions and native O0/O2 execution fixtures. |
| `timeout 30 python3 -B tests/quality.py` | PASS, all 13 hygiene/metric mutation tests and legitimate exemption controls. |
| `timeout 30 .tmp/quality-driver/alias-differential/check "$PWD/.tmp/quality-driver/alias-differential/inventory"` | PASS; modules compiled from `ebe54e5` and current source agree on exact results/diagnostics for 512 alias admissions and on four inventory results/path vectors. |
| `cargo fmt --all --check`, `timeout 90 cargo clippy --offline -j3 --all-targets -- -D warnings`, `git diff --check` | PASS. |

After that follow-up, totals were 60 tracked source files, 228 functions, longest function 207
lines, and 69 wrapper matches, with zero litter/process identifiers. No per-file
limit grows. No full push gate was run. The nits in bennett-driver-mqb and existing
publication obligations remain open.

The final hygiene follow-up for bennett-driver-ocr restricts the named-switch
exemption to Rust attribute tokens in code position. Lexical scanning skips
nested block and line comments, character/byte-character literals (without
confusing lifetimes), escaped normal/byte/C strings, and raw strings with arbitrary
hash delimiters before recognising attributes. Only attribute bytes are masked;
comments, literal contents and following code remain subject to the identifier
scan. Line numbers survive multiline attributes; unterminated strings/comments
fail loudly.

The review's temporary-repository reproduction was red first: the actual quality
CLI accepted a new identifier that the compiled Rust program emitted. The first
generated table also failed before implementation. The final independent table
covers **4,615 cases**: six string kinds, raw hash counts 0/1/2/3/16/255/256,
first/interior/last/single-line positions, three column positions, literal versus
real-attribute placement, eight lexical contexts and seven explicit controls.
Zero-hash raw literals use identifier text because their contents cannot include
double quotes. The 256-hash cases stress the scanner beyond Rust's compiler limit.
Expected identifier lists come from the placement table, independent of the lexer.
The CLI regression verifies exact emitted output, rejection and diagnostic line;
the genuine promised-test switch controls still pass. All **17 quality tests pass**.

The structural baseline, thresholds, measured languages and tracked-source scope
remain unchanged; baseline JSON is byte-identical to `35a7d27`. Regression messages
now use one comparison table for scalar and length-tail metrics; 4,096 comparisons
against the reviewed implementation produced byte-identical diagnostics. The
script remains at complexity **79**, maximum function length **28**, two functions
over 25 lines and zero wrappers. Its tests remain at complexity **2**, maximum
length **13** and one wrapper. Current totals: **60 source files, 240 functions,
longest 207 lines, 69 wrappers**, with zero litter/process identifiers.

Final lexical-fix verification (headless, job-local TMPDIR/CARGO_TARGET_DIR,
unchanged gate pins; implementation `b6d789a`):

| Command | Result |
|---|---|
| `timeout 900 cargo test --offline -j3 -- --test-threads=4` | PASS, **62.54 s** wall; 20 unit + 26 fixture + 2 pipeline tests, the same five named ignored tests. The fixture run includes all 17 quality tests. |
| `timeout 30 python3 -B tests/quality.py` | PASS, **17 tests**, including the 4,615-case table, executable CLI reproduction and genuine-switch controls. |
| `timeout 30 python3 scripts/quality.py` | PASS under the unchanged baseline, with zero litter/process identifiers. |
| `git diff 5bccf0e --check` | PASS. |

The nonblocking bennett-driver-mqb and publication obligations
bennett-driver-9zg/7y4/ppz remain open. No full push gate was run.

K91 startup/shim evidence (ISA contract `618b16f`, implementation `a3833e3`):
`cargo test --offline -j4 --test loader driver_startup_command -- --nocapture`
was red against the old driver: `--launch-estimate` had no startup path.
The final `cargo test --offline -j4 -- --test-threads=4` passes in **70.39 s**
wall (**111.60 s** user, **86.25 s** system), including 11 loader fixtures and
two compile-fail lifetime examples; the six existing ignored cases retain
their explicit switches. `cargo fmt --all --check`,
`cargo clippy --offline -j4 --all-targets -- -D warnings` and
`python3 -B scripts/quality.py` pass. Headless commands use job-local temporary
and Cargo target directories. Width 4 is derived with shared-host headroom
from 64 threads and about 52 GiB available memory. Focused/default command
guards use the earlier measured suite times above with at least 10x headroom;
a guard trip is UNKNOWN. No full push gate was run by the implementation job.

Independent public-C-ABI fixture providers exercise both role manifests,
malformed/unsupported manifests, absent queries/features/required exports,
original query/request statuses, concurrent and repeated byte-identical queries,
provider reload, all five three-position partitions, separate root/provider
bindings, fresh equal-tuple handles and native-program/token forwarding with
revocation. Abort-on-effect fixtures make compatibility bypass observable.
Five deliberate mutations (skip manifest validation, skip required-symbol
validation, discard query status, erase the partition, allow cross-root tokens)
all fail their named tests; restored code passes. The lifetime examples fail
specifically with E0505 when dropping the borrowed provider/program.
These fixtures verify loader transport and dispatch, not VM estimation semantics.

Reader audit: the new startup path writes the provider certificate bytes
unchanged and never inserts manifests or process handles into artifacts.
Its certificate accessor transports opaque bytes and does not attest an
independent checker. The existing plugin native adapter, layout/ELF reader and
build finaliser remain on the separately selected ISA 0.8 compilation/comparison
path; layout ABI 1 and launch-record validation confer no K91 support. No
scheduler request dispatcher participates in this startup; separately selected
scheduler adapters must use their own role negotiation, including both required
exports. Full native-container packaging and run/tape integration remain in
bennett-driver-b0r/kcc under bennett-4ht. The startup command and embeddable shim
retain separate bindings per selected device root and impose no records on
native main, argv/envp or host libc.

Only the eight owned source rows (main, launch CLI/library, manifest/provider
loader and fixtures) were added/refreshed below. The pre-merge receipt is
`git diff 8b1b4a1..HEAD -- docs/quality.md`; all other baseline rows are unchanged.

The classical R compatibility update records only its owned rows: the explicit
contract enum, isolated selected-profile identity query, profile-aware reports,
and their focused fixtures. Historical pins and comparison static-link audits
retain their existing tests. This receipt does not claim complete rung-3 native
execution; the exact commands and remaining frontiers are in the job evidence.

The R global correspondence consumer adds receipt/build/launch authentication,
complete device-global and unique source-symbol checks, and conflicting-map
rejections in `scripts/native-layout.py`. `src/native.rs` passes the selected
preparation report, launch record and entry to that layout step. The positive
R fixture also exercises altered publication bytes, stale identities, missing
or inconsistent associations and explicit-map conflicts. The baseline updates
only those three files to account for these checks; `read_layout`,
`resolve_layout` and the fixture assertion helpers keep function lengths within
the previous maxima. The linker extent/address assertions and ELF audit remain
unchanged.

The R process-input consumer adds explicit argv/envp byte serialization and
validation in `scripts/finalise-build.py`, selected by the published build
protocol. Finalization is a callable function so independent codec tests can
check both pointer widths, exact offsets, raw bytes and malformed replies.
`src/options.rs` validates the two input channels and `src/main.rs` records their
hashes through one artifact table. The baseline adds the full driver process
fixture, its codec controls and the small oracle adapter that links the pinned
reference library binary. That adapter uses the public run/reply/reverse API and
checks the unchanged complete process, exact console/status, both host requests
and complete state restoration. It avoids the CLI's per-instruction memory trace;
the first CLI attempt hit its 180-second guard and provided no execution result.
No product execution checks or assertions were removed. The update is restricted
to these seven changed/new source rows.

The isolated-provider implementation follows reviewed dialect §17.7 at
`9bbf6de`. Its baseline records the new driver gateway, fixed-address ELF
bootstrap, namespace/dependency/lifetime audits, and two real-provider fixtures.
The original runtime/arithmetic component keeps its static link and range
assertions. Native-only bookkeeping has a separate segment; exact global
sections disable string pooling without changing the producer artifact.
Comparison exit polling realises the published EH exit transfer after actual
cleanup, while retaining original instructions and leaving other selectors
unchanged. Function/call attributes are adjusted for the added native checks.
The CLI also forwards the existing shared layout options to explicit R-contract production;
historical producer invocations retain their prior flags. The compatibility
guard was verified against the unchanged output-path collision matrix.
The update is restricted to these fifteen changed/new source rows.

Focused verification: the first LLVM18 O0 marked root allocates and clean-frees
one real VM qubit and returns7. The expanded matrix executes both majors/O0/O2,
actual musl hello, the full driver process with buffered `tailbye` output and
exit7, the unused-binding rejection, immutable/hash controls, and source-fault
cleanup. A dirty-precondition control sets a real VM register via the public
prepare API then calls its actual free: backend status7 becomes fault4, and
program unload succeeds. Source qprep/gate materialisation failures remain a
separate producer followup, not passing source-operation evidence. Tests retain
all outcome/lifetime assertions. Execution guard trips are UNKNOWN; timed-out
children are cleaned by process groups and bootstrap parent-death handling.

<!-- quality-baseline -->
```json
{
  "files": {
    "scripts/arith-instances.py": {
      "complexity": 179,
      "functions": 9,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 18,
      "wrappers": 3
    },
    "scripts/finalise-build.py": {
      "complexity": 34,
      "functions": 13,
      "length_tails": [
        1,
        0,
        0,
        0,
        0
      ],
      "max_length": 40,
      "wrappers": 4
    },
    "scripts/native-layout.py": {
      "complexity": 135,
      "functions": 13,
      "length_tails": [
        3,
        0,
        0,
        0,
        0
      ],
      "max_length": 47,
      "wrappers": 0
    },
    "scripts/native-provider-plan.py": {
      "complexity": 27,
      "functions": 4,
      "length_tails": [
        1,
        1,
        0,
        0,
        0
      ],
      "max_length": 52,
      "wrappers": 1
    },
    "scripts/native-provider-run.py": {
      "complexity": 18,
      "functions": 5,
      "length_tails": [
        1,
        0,
        0,
        0,
        0
      ],
      "max_length": 39,
      "wrappers": 1
    },
    "scripts/pinned_siblings.py": {
      "complexity": 14,
      "functions": 2,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 15,
      "wrappers": 0
    },
    "scripts/plugin-identity.py": {
      "complexity": 4,
      "functions": 0,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 0,
      "wrappers": 0
    },
    "scripts/quality.py": {
      "complexity": 79,
      "functions": 6,
      "length_tails": [
        2,
        0,
        0,
        0,
        0
      ],
      "max_length": 28,
      "wrappers": 0
    },
    "src/arith.rs": {
      "complexity": 14,
      "functions": 1,
      "length_tails": [
        1,
        1,
        0,
        0,
        0
      ],
      "max_length": 77,
      "wrappers": 0
    },
    "src/classifier.rs": {
      "complexity": 35,
      "functions": 1,
      "length_tails": [
        1,
        1,
        1,
        1,
        0
      ],
      "max_length": 207,
      "wrappers": 0
    },
    "src/contract.rs": {
      "complexity": 4,
      "functions": 5,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 12,
      "wrappers": 1
    },
    "src/json.rs": {
      "complexity": 15,
      "functions": 10,
      "length_tails": [
        1,
        0,
        0,
        0,
        0
      ],
      "max_length": 33,
      "wrappers": 7
    },
    "src/launch.rs": {
      "complexity": 27,
      "functions": 16,
      "length_tails": [
        2,
        0,
        0,
        0,
        0
      ],
      "max_length": 39,
      "wrappers": 2
    },
    "src/launch/manifest.rs": {
      "complexity": 32,
      "functions": 4,
      "length_tails": [
        2,
        0,
        0,
        0,
        0
      ],
      "max_length": 34,
      "wrappers": 0
    },
    "src/launch/provider.rs": {
      "complexity": 14,
      "functions": 5,
      "length_tails": [
        1,
        0,
        0,
        0,
        0
      ],
      "max_length": 27,
      "wrappers": 0
    },
    "src/launch_cli.rs": {
      "complexity": 36,
      "functions": 4,
      "length_tails": [
        1,
        1,
        0,
        0,
        0
      ],
      "max_length": 60,
      "wrappers": 0
    },
    "src/lib.rs": {
      "complexity": 0,
      "functions": 0,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 0,
      "wrappers": 0
    },
    "src/llvm_utility.rs": {
      "complexity": 20,
      "functions": 3,
      "length_tails": [
        3,
        1,
        0,
        0,
        0
      ],
      "max_length": 53,
      "wrappers": 0
    },
    "src/main.rs": {
      "complexity": 223,
      "functions": 41,
      "length_tails": [
        12,
        6,
        2,
        0,
        0
      ],
      "max_length": 136,
      "wrappers": 7
    },
    "src/mode-preparation.cpp": {
      "complexity": 198,
      "functions": 4,
      "length_tails": [
        1,
        1,
        1,
        0,
        0
      ],
      "max_length": 182,
      "wrappers": 0
    },
    "src/mode_preparation.rs": {
      "complexity": 23,
      "functions": 1,
      "length_tails": [
        1,
        1,
        0,
        0,
        0
      ],
      "max_length": 79,
      "wrappers": 0
    },
    "src/native.rs": {
      "complexity": 150,
      "functions": 33,
      "length_tails": [
        7,
        5,
        3,
        0,
        0
      ],
      "max_length": 170,
      "wrappers": 1
    },
    "src/native_adapter.rs": {
      "complexity": 23,
      "functions": 2,
      "length_tails": [
        2,
        1,
        0,
        0,
        0
      ],
      "max_length": 80,
      "wrappers": 0
    },
    "src/native_bootstrap.c": {
      "complexity": 180,
      "functions": 10,
      "length_tails": [
        3,
        0,
        0,
        0,
        0
      ],
      "max_length": 44,
      "wrappers": 0
    },
    "src/native_component.c": {
      "complexity": 15,
      "functions": 3,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 14,
      "wrappers": 0
    },
    "src/native_component_adapt.cpp": {
      "complexity": 67,
      "functions": 3,
      "length_tails": [
        2,
        0,
        0,
        0,
        0
      ],
      "max_length": 40,
      "wrappers": 0
    },
    "src/native_host.rs": {
      "complexity": 14,
      "functions": 1,
      "length_tails": [
        1,
        1,
        0,
        0,
        0
      ],
      "max_length": 72,
      "wrappers": 0
    },
    "src/native_provider.rs": {
      "complexity": 32,
      "functions": 6,
      "length_tails": [
        2,
        1,
        1,
        0,
        0
      ],
      "max_length": 113,
      "wrappers": 1
    },
    "src/native_provider_api.h": {
      "complexity": 0,
      "functions": 0,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 0,
      "wrappers": 0
    },
    "src/options.rs": {
      "complexity": 80,
      "functions": 10,
      "length_tails": [
        1,
        1,
        1,
        0,
        0
      ],
      "max_length": 190,
      "wrappers": 5
    },
    "src/output_paths.rs": {
      "complexity": 33,
      "functions": 3,
      "length_tails": [
        1,
        0,
        0,
        0,
        0
      ],
      "max_length": 32,
      "wrappers": 0
    },
    "src/plugin_identity.py": {
      "complexity": 5,
      "functions": 0,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 0,
      "wrappers": 0
    },
    "src/process-entry.cpp": {
      "complexity": 38,
      "functions": 2,
      "length_tails": [
        1,
        1,
        1,
        0,
        0
      ],
      "max_length": 182,
      "wrappers": 0
    },
    "src/process.rs": {
      "complexity": 17,
      "functions": 1,
      "length_tails": [
        1,
        1,
        1,
        0,
        0
      ],
      "max_length": 103,
      "wrappers": 0
    },
    "src/report.rs": {
      "complexity": 40,
      "functions": 2,
      "length_tails": [
        1,
        1,
        0,
        0,
        0
      ],
      "max_length": 99,
      "wrappers": 0
    },
    "tests/arith_conversions.py": {
      "complexity": 14,
      "functions": 3,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 4,
      "wrappers": 1
    },
    "tests/arith_instances.py": {
      "complexity": 19,
      "functions": 2,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 4,
      "wrappers": 1
    },
    "tests/arith_production.py": {
      "complexity": 4,
      "functions": 2,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 4,
      "wrappers": 1
    },
    "tests/classes.py": {
      "complexity": 5,
      "functions": 1,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 4,
      "wrappers": 0
    },
    "tests/classes.rs": {
      "complexity": 0,
      "functions": 1,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 3,
      "wrappers": 1
    },
    "tests/classifier.py": {
      "complexity": 11,
      "functions": 1,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 4,
      "wrappers": 0
    },
    "tests/closed_unit.py": {
      "complexity": 1,
      "functions": 1,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 6,
      "wrappers": 0
    },
    "tests/comparison.py": {
      "complexity": 21,
      "functions": 1,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 4,
      "wrappers": 0
    },
    "tests/device_models.py": {
      "complexity": 6,
      "functions": 0,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 0,
      "wrappers": 0
    },
    "tests/device_models.rs": {
      "complexity": 0,
      "functions": 1,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 3,
      "wrappers": 1
    },
    "tests/dialect_profile.py": {
      "complexity": 7,
      "functions": 2,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 6,
      "wrappers": 1
    },
    "tests/environment.py": {
      "complexity": 1,
      "functions": 0,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 0,
      "wrappers": 0
    },
    "tests/fixtures.rs": {
      "complexity": 0,
      "functions": 33,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 3,
      "wrappers": 33
    },
    "tests/fixtures/device_clock.c": {
      "complexity": 2,
      "functions": 2,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 20,
      "wrappers": 0
    },
    "tests/fixtures/loader-provider.c": {
      "complexity": 31,
      "functions": 13,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 12,
      "wrappers": 2
    },
    "tests/fixtures/native_dirty_provider.c": {
      "complexity": 7,
      "functions": 2,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 10,
      "wrappers": 0
    },
    "tests/fixtures/r3-hello.c": {
      "complexity": 0,
      "functions": 1,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 4,
      "wrappers": 0
    },
    "tests/fixtures/r3-integer-printf.c": {
      "complexity": 0,
      "functions": 1,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 5,
      "wrappers": 0
    },
    "tests/fixtures/r_process_reference.rs": {
      "complexity": 1,
      "functions": 2,
      "length_tails": [
        1,
        0,
        0,
        0,
        0
      ],
      "max_length": 38,
      "wrappers": 0
    },
    "tests/hook.py": {
      "complexity": 4,
      "functions": 0,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 0,
      "wrappers": 0
    },
    "tests/input_headers.py": {
      "complexity": 34,
      "functions": 0,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 0,
      "wrappers": 0
    },
    "tests/inputs.py": {
      "complexity": 1,
      "functions": 1,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 4,
      "wrappers": 0
    },
    "tests/integration.py": {
      "complexity": 25,
      "functions": 3,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 8,
      "wrappers": 1
    },
    "tests/loader.rs": {
      "complexity": 25,
      "functions": 16,
      "length_tails": [
        7,
        1,
        0,
        0,
        0
      ],
      "max_length": 81,
      "wrappers": 2
    },
    "tests/merged_module.py": {
      "complexity": 4,
      "functions": 1,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 4,
      "wrappers": 0
    },
    "tests/modes.py": {
      "complexity": 18,
      "functions": 1,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 6,
      "wrappers": 0
    },
    "tests/native_byval.py": {
      "complexity": 8,
      "functions": 0,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 0,
      "wrappers": 0
    },
    "tests/native_faults.py": {
      "complexity": 13,
      "functions": 0,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 0,
      "wrappers": 0
    },
    "tests/native_host.py": {
      "complexity": 13,
      "functions": 2,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 2,
      "wrappers": 2
    },
    "tests/native_materialisation.py": {
      "complexity": 18,
      "functions": 2,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 4,
      "wrappers": 1
    },
    "tests/native_memory.py": {
      "complexity": 26,
      "functions": 3,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 4,
      "wrappers": 2
    },
    "tests/native_process_startup.py": {
      "complexity": 8,
      "functions": 1,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 11,
      "wrappers": 0
    },
    "tests/native_scalar.py": {
      "complexity": 14,
      "functions": 2,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 4,
      "wrappers": 1
    },
    "tests/native_scalar.rs": {
      "complexity": 0,
      "functions": 2,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 3,
      "wrappers": 2
    },
    "tests/native_scalar_binding.py": {
      "complexity": 6,
      "functions": 3,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 4,
      "wrappers": 2
    },
    "tests/native_startup.py": {
      "complexity": 46,
      "functions": 13,
      "length_tails": [
        1,
        0,
        0,
        0,
        0
      ],
      "max_length": 30,
      "wrappers": 2
    },
    "tests/native_symbols.py": {
      "complexity": 47,
      "functions": 1,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 4,
      "wrappers": 0
    },
    "tests/output_paths.py": {
      "complexity": 8,
      "functions": 0,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 0,
      "wrappers": 0
    },
    "tests/pin_discipline.py": {
      "complexity": 62,
      "functions": 20,
      "length_tails": [
        2,
        0,
        0,
        0,
        0
      ],
      "max_length": 38,
      "wrappers": 0
    },
    "tests/pinned_fixture.py": {
      "complexity": 2,
      "functions": 0,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 0,
      "wrappers": 0
    },
    "tests/pipeline.rs": {
      "complexity": 0,
      "functions": 4,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 19,
      "wrappers": 1
    },
    "tests/pipeline_metadata.py": {
      "complexity": 6,
      "functions": 0,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 0,
      "wrappers": 0
    },
    "tests/preparation.py": {
      "complexity": 16,
      "functions": 1,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 4,
      "wrappers": 0
    },
    "tests/process.py": {
      "complexity": 54,
      "functions": 2,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 4,
      "wrappers": 1
    },
    "tests/process_arguments_codec.py": {
      "complexity": 9,
      "functions": 5,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 21,
      "wrappers": 0
    },
    "tests/process_runtime_apis.py": {
      "complexity": 6,
      "functions": 1,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 4,
      "wrappers": 0
    },
    "tests/quality.py": {
      "complexity": 2,
      "functions": 11,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 13,
      "wrappers": 1
    },
    "tests/r_contract.py": {
      "complexity": 11,
      "functions": 5,
      "length_tails": [
        1,
        0,
        0,
        0,
        0
      ],
      "max_length": 47,
      "wrappers": 1
    },
    "tests/r_native_layout.py": {
      "complexity": 25,
      "functions": 7,
      "length_tails": [
        2,
        1,
        0,
        0,
        0
      ],
      "max_length": 59,
      "wrappers": 2
    },
    "tests/r_process_arguments.py": {
      "complexity": 10,
      "functions": 6,
      "length_tails": [
        1,
        0,
        0,
        0,
        0
      ],
      "max_length": 29,
      "wrappers": 1
    },
    "tests/reports.py": {
      "complexity": 37,
      "functions": 0,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 0,
      "wrappers": 0
    },
    "tests/reversible.py": {
      "complexity": 13,
      "functions": 0,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 0,
      "wrappers": 0
    },
    "tests/support/mod.rs": {
      "complexity": 0,
      "functions": 1,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 19,
      "wrappers": 0
    },
    "tests/toolchain.py": {
      "complexity": 4,
      "functions": 3,
      "length_tails": [
        0,
        0,
        0,
        0,
        0
      ],
      "max_length": 15,
      "wrappers": 0
    }
  },
  "litter": [],
  "process_identifiers": []
}
```
