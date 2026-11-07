# quality-driver review, round 2

**Verdict: BLOCK.** Reviewed fixes `35a7d27..866dab7`, after reading the requested `main..job/quality-driver` history, full-range scope and round-1 review. Exact implementation head: **866dab7913d2aba32c0bb565925d345122197652**. No implementation fixes. The supplied pre-review gate_run PASS (08:04Z) was not rerun.

1. **P1-1 — named-switch exemption hides emitted Rust raw-string identifiers — bennett-driver-ocr.** `scripts/quality.py:103` applies the regex at line 21 without lexical context. Production Rust can emit an ignore-shaped line from a raw string:
   ```rust
   fn main() {
       print!("{}", r###"
   #[ignore = "bennett-driver-abc"]
   "###);
   }
   ```
   Record a temporary tracked repository's baseline with `ordinary output` in place of the identifier, then change only that string. Ran **`timeout 30 python3 -B -`**, invoking the actual quality CLI and `rustc --edition=2024`, then executing the binary: quality exits **0**, reports no regression, and the program prints the identifier. The probe exits **1** on the assertion requiring ratchet rejection. All 13 committed quality tests still pass. This is a remaining exemption gap in the a79 fix: product string bytes are mistaken for a legitimate named test switch. Limit the exemption to actual attributes outside literals and add this CLI mutation while retaining the genuine-switch control. Full executable repro is in the bead.

Round-1 blockers: **bennett-driver-av7 is fixed**. The independent original marked-`top` probe, extended to both configurable destinations, now rejects certificate overwrites with `BD-E-OUTPUT-PATH`, no traceback, intact producer and valid receipt certificate SHA. **bennett-driver-a79's original inline-body cases are fixed** (Rust, Python and code following a named switch); P1-1 above remains. New admission tests cover 11 evidence kinds × direct/symlink/hardlink aliases × record/executable destinations, preserving bytes with zero commands; missing/non-directory inventories fail loudly. The structural baseline JSON is byte-identical to `35a7d27`, and thresholds/source scope are unchanged.

P2+ nits — no new fix-diff nits; carried forward **bennett-driver-mqb**: applied controls labelled unused (`src/main.rs:691–699`), repeated defaults (`src/options.rs:124–129,224,299–300`). Required consolidated round-2 nit bead **bennett-driver-z4u** lists both and is closed as a duplicate of the existing open owner.

Verification used the prescribed headless environment, job-local TMPDIR/CARGO_TARGET_DIR and gate-pinned fixtures:

- `timeout 180 cargo test --offline -j3 --bin bennett-driver -- --nocapture --test-threads=4` — **20 passed**.
- `timeout 180 cargo test --offline -j3 --test fixtures -- output_paths comparison native_symbols --nocapture --test-threads=4` — **5 passed**, 25.02 s; LLVM 18/23 collisions and actual O0/O2 executions.
- `timeout 30 python3 -B tests/quality.py` — **13 passed**; `timeout 30 python3 -B scripts/quality.py` — **PASS**; `git diff 35a7d27..866dab7 --check` — **PASS**.
- Independent `timeout 90 python3 -B -` — **PASS** for the original certificate repro (record and executable) and baseline byte equality. Independent `timeout 30 python3 -B -` — **RED** for P1-1 as detailed above.

Read the main-side comparison code: its protected set omits published entry evidence, so the added certificate assertions would fail there; the reviewed pre-fix quality script skips whole function/ignore lines, so the inline-body mutations detect the original fault. No branch switch, worktree creation, full gate or sibling gate.

Coverage: read closely all six fix-diff files and admission/finalisation/alias callers; skimmed unrelated batch changes and measurement history. Checked every COMMON anti-slop rule: dispatch, state, defaults, predicates, constants, function phases/size, wrappers, process identifiers, litter and test-oracle independence. No additional narrowing or weakened assertions found. Published-evidence and restructuring checks pass; P1-1 blocks the hygiene claim.

Provenance: implementer **gpt-6.1-sol**; reviewer **gpt-6.1-sol**, fresh session, **D9**.
