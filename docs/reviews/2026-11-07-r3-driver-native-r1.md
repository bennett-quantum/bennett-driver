# Native comparison review, round 1

**BLOCK — P0-1: bennett-driver-sjn.**

Reviewed `main..job/r3-driver-native`: base `22c06d26a3ca87e5cf5a55a3dfba30bce9b183ce`, commits `085e3cb`, `5f495e6`, `413ee59`; exact reviewed head **413ee591c164669fb7b89b93347d133c79591d9c**.

**P0-1 — Rung 3: a binding relocation admits an unbound, incorrectly executing baseline.** At `src/native.rs:544-558`, any undefined symbol matching the report's binding is accepted; `src/native.rs:507-509` then permits executable publication. Starting with the genuine pinned scalar R hello artifact, supply `--bennett-native-input` containing only:

```c
__asm__(".data\n.globl unused_binding_reference\nunused_binding_reference:\n.quad BINDING_SYMBOL\n.text\n");
```

Substitute the actual report binding symbol. This creates a data relocation and never calls the binding or loads a program. On **LLVM 18 and 23, O0 and O2**, the driver returns 0 with manifest status `linked` and startup status `binding reference present; lifecycle not certified`. All four binaries instead terminate with SIGILL (subprocess returncode −4), empty stdout, and `bennett runtime fault 2\n`. Expected: exit 0 and `hello, world\n`. Original device and launch-record hashes remain unchanged. The lifecycle caveat does not prevent this wrong rung-3 native result. Require actual startup/binding enforcement, with an unused-reference regression, before publishing a usable baseline.

Command run: `.tmp/r3-driver-native/build-slot 180 env TMPDIR=$PWD/.tmp/rev-r3-driver-native-r1/tmp CARGO_TARGET_DIR=$PWD/.tmp/rev-r3-driver-native-r1/target python3 -B -`; stdin replayed `tests/native_scalar_binding.py`, adding the above native input and executing both variants. Complete executed stdin is in the review progress Resume block. Genuine specimens, input C, manifests, reports and ELFs remain under `.tmp/rev-r3-driver-native-r1/tmp/asm-binding-probe/{18,23}/`.

Verification: build-slot-wrapped `timeout 180 cargo test --offline -j3` runs with `--nocapture --test-threads=4`: `--test fixtures native` (9 pass), `--test native_scalar` (1 pass/1 ignored), `--test fixtures comparison::` and `output_paths::` (1 pass each), `--bin bennett-driver native::tests` (6 pass). The exact ignored printf test remains red with LLVM18 fault7; independent case isolation retaining its assertion establishes prepared hello PASS and integer printf fault7 on both majors. The printf Python script is byte-identical to `085e3cb`; no other failing workload was found. `timeout 30 python3 -B scripts/quality.py` and `git diff --check main...job/r3-driver-native` pass. No full gate was run.

P2+ nits — **bennett-driver-prl** (priority 3): receipt audits accept an empty variant list (`tests/native_materialisation.py:67`); the single expected-red script stops before LLVM23 cases (`tests/native_scalar.py:33`). Known upstream lifecycle/printf gaps remain open; no full R/native agreement is established.

Coverage: read closely the entire job diff, main-side native implementation, adapter/link/startup flow, changed tests/fixtures, published native adapter contract, gate/report wiring and quality baseline; skimmed unchanged host/classifier/library support. Phase splitting preserves link commands, ordering and error precedence. Inventory covers the actual retained link inputs; no host libc/libm fallback was found. Checked every COMMON anti-slop rule and plan items 9–11: structural gate present, existing source baselines preserved, HANDOFF.md retired and README points to the meta handoff.

Provenance: implementer gpt-6.1-sol; reviewer gpt-6.1-sol, fresh session (D9). Reviewer fixes nothing.

