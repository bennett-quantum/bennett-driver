## Resume

Review fixes closed:7gi (output aliases),4r1 (original target metadata),bcl (executed pipeline provenance),crx (mapped native globals/interface/arena). Native symbol mappings bind the original module SHA, fix real ELF placement and audit addresses/extents/alignment. Separate high mapped regions leave the heap vacant; exact first-free-page assertion remains. Actual O0/O2 values and heap use pass on LLVM18/23.

Native-only round2 portion of116 is fixed: ordinary source modules produce host executables/library objects with native libc, argv and startup, before any device-library closure. Empty selected-device inventories are valid. Mixed native.o/.a refusal names4ht/116. The mixed native/VM link remains OPEN P1 outside round2 under advisorR15; see NATIVE_HOST.md.

Verified with headless job TMPDIR/target,-j4,testthreads2:
- Immutable0ac plugin plus hash-bound library copies, timeout240 cargo test --offline -j4 --test native_host --test output_paths --test inputs --test input_headers --test pipeline_metadata -- --nocapture --test-threads=2: PASS4.11/3.35/1.21/8.31/4.93s. Original missing-header diagnostics specifically checked.
- timeout300 cargo test --offline -j4 --test native_symbols --test comparison --test native_memory --test native_faults -- --nocapture --test-threads=2: PASS7.37/7.30/6.99/12.44s; final mapped heap-use check PASS.
- timeout480 cargo test --offline -j4 --test process --test process_runtime_apis -- --nocapture --test-threads=2: PASS11.72/1.92s. Fixed-IR codegen changed measured fixture heap page to73728; exact assertion retained.
- Arithmetic conversions, offline instances and byval components PASS14.31/72.66/2.56s.
- cargo fmt --all --check and timeout120 cargo clippy --offline -j4 --all-targets -- -D warnings PASS.

Selected-entry native comparison now integrates public prepare/check/finalise/host-import stages and preserves original device/receipt hashes. Actual live-plugin component probes passed both majors with real qreg imports; strict no-host startup still lacks a true VM binding/backend (r1p BLOCKED, cross-repo request filed). cyg.3 and i0v are not full acceptance. A later immutable0ac probe found that commit lacks prepare-only; the live plugin concurrently moved to dialect0.2.13. New published plugin/API/arith pins and explicit dialect adoption are required; prior live component evidence does not establish isolated-gate acceptance.

Gate runtime pin248e468 and scripts/native-check hash fixedrw8; hook test now config/stub only, tool owns protocol. fgv localeconv/getpagesize closed after unchanged API checks passed. 3j4/ppz still need tracked successful conformance fixture plus historical runtime/arith aliases. Missing fixture fails BD-E-TEST-FIXTURE; no live conformance .tmp fallback or silent skip. No full gate or rung3 consumer was run; orchestrator owns them.

Next:9zg modes/controls, explicit0ai dialect0.2.13 adoption and pins, ppz fixture dependency,62k adapter design/publication,7y4 device-model wrapper/prologue,aea nit. Ten fat-object audit followups remain deferred; audit source hashes are a historical snapshot. Earlier closed process preparation mno, numerical instances q4d, byval m2m, native-check1fx and fenv4wi are component evidence, not full rung3. Runner owns commits.
