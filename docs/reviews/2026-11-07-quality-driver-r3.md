# quality-driver review, round 3 (final)

**Verdict: BLOCK.** Reviewed fixes `5bccf0e..ea40cf6`, after reading the requested `main..job/quality-driver` history/full-range scope, binding laws and both earlier reviews. Exact implementation head: **ea40cf6e36e03b3e75b682f0b614df770b932a16**. No implementation edits. Supplied pre-review gate_run PASS (08:35Z) was not rerun.

1. **P1-1 — switch exemption still hides emitted macro token data — bennett-driver-v4f.** `scripts/quality.py:70–71` masks every lexed ignore-shaped token sequence without establishing that it is a named test switch. This valid production code emits the masked identifier:
   ```rust
   fn main() {
       print!("{}", stringify!(
   #[ignore = "bennett-driver-abc"]
   ));
   }
   ```
   In a temporary tracked repository, record the baseline with `ordinary output` instead of the identifier, then change only that text. Ran **`timeout 30 python3 -B -`**, invoking the actual quality CLI, `rustc --edition=2024` and the resulting binary: the CLI exits **0**, with no stderr; the binary prints **`#[ignore = "bennett-driver-abc"]`**. The independent probe exits **1** on its rejection assertion. Lexical position outside literals does not make macro input an attribute on a test. This is a remaining exemption gap in the reviewed fix, violating the required hygiene ratchet; all 17 committed quality tests pass. Full standalone repro is in the bead. Exempt genuine named test switches without hiding token data, retaining the existing controls.

Earlier blockers: **bennett-driver-ocr's original raw-string repro is fixed**: the same independent probe now receives CLI exit 1 and the correct `src/work.rs:3` process-identifier diagnostic and the binary emits the expected raw-string text. **bennett-driver-a79 remains fixed**: Rust/Python inline-body and trailing-code mutations reject, and the genuine promised-switch control passes. **bennett-driver-av7 remains fixed**: the independent original marked-`top` probe rejects both certificate record/executable destinations with `BD-E-OUTPUT-PATH`, no traceback, intact producer and valid receipt SHA; focused tests also preserve direct/symlink/hardlink evidence aliases and reject unreadable inventories.

Oracle integrity: the **4,615-case lexical table has independent expectations**. `PLACEMENTS` and seven explicit controls supply literal expected identifier lists; the Cartesian generator chooses source placement without consulting the lexer or its output. The executable raw-string test separately pins exact output and diagnostic line. The table lacks macro token-data placement, which explains P1-1; its existing expectations are not self-derived. No tests were weakened, deleted or newly skipped. Baseline JSON is byte-identical to `35a7d27`; thresholds, tracked-source scope and languages are unchanged. The metric refactor preserves all diagnostics in 4,096 independent comparisons with the pre-fix implementation.

P2+ nits — no new fix-diff nits; carried **bennett-driver-mqb**: applied controls labelled unused (`src/main.rs:691–699`) and repeated defaults (`src/options.rs:124–129,224,299–300`), confirmed unchanged by inspection. Consolidated round-3 nit bead **bennett-driver-3pp** lists both and is closed as a duplicate of that open owner.

Verification used the prescribed headless environment, `TMPDIR=$PWD/.tmp/rev-quality-driver-r3/tmp`, `CARGO_TARGET_DIR=$PWD/.tmp/rev-quality-driver-r3/target` and gate-pinned fixtures:

- `timeout 180 cargo test --offline -j3 --bin bennett-driver -- --nocapture --test-threads=4` — **20 passed**.
- `timeout 180 cargo test --offline -j3 --test fixtures -- output_paths comparison native_symbols --nocapture --test-threads=4` — **5 passed**, 22.30 s; both LLVM majors, published-evidence collisions and actual O0/O2 executions.
- `timeout 30 python3 -B tests/quality.py` — **17 passed**, including 4,615 generated cases and original inline/raw-string controls.
- `timeout 30 python3 -B scripts/quality.py` — **PASS**; `git diff 5bccf0e..ea40cf6 --check` — **PASS**.
- Independent `timeout 90 python3 -B -` — **PASS**, original certificate repro for both destinations. Independent `timeout 30 python3 -B -` — **PASS**, baseline byte equality and 4,096 metric comparisons. Independent executable hygiene probe under `timeout 30 python3 -B -` — original raw-string control **PASS**, P1-1 rejection assertion **RED**.

Read `git show main:src/native.rs`: its protected set omits published entry evidence, so the certificate regression would fail there. Main has no quality script; reading `5bccf0e:scripts/quality.py` confirms the original raw-string line is wrongly exempted before this fix. No branch switches, worktree creation, full gate or sibling gate.

Coverage: read closely all three fix-diff files, lexical cases/controls, admission/inventory/alias callers and relevant main-side code; skimmed unrelated batch scope and historical measurement material. Checked every COMMON anti-slop rule: dispatch, state, failure defaults, predicates, constants, function phases/size, wrappers, process identifiers, litter and test-oracle independence. P1-1 remains; no additional narrowing found. This is the third and final review; remaining blockers go to the advisor/maintainer under policy, with no fourth round.

Provenance: implementer **gpt-6.1-sol**; reviewer **gpt-6.1-sol**, fresh session, **D9**.
