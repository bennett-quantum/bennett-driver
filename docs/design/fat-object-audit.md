# Mixed fat-object audit of bennett-driver

This is a design audit for `bennett-4ht`, not an implementation or a claim that mixed native/device execution works. The target remains an ordinary native binary with only selected marked closures represented by ISA objects. Whole-link analysis can see all relevant bitcode without making the device payload own the whole binary. Ordinary unmarked native code must remain reachable.

The driver currently targets dialect **0.2.10** and ISA **0.8** (`SPEC_VERSIONS.toml`). Source anchors below refer to the inspected checkout, whose file hashes are recorded at the end. No Git command, full gate, VM dual-engine run or rung-3 consumer gate was used in this audit. No production source or launch adapter was changed.

The controlling references are [North Star §§2,3.3,4.4](../../../bennett/docs/Bennett-NorthStar.md), [dialect §§19.1–19.8](../../../bennett-dialect-spec/spec/outline-0.2.md), the [0.2.10 process interpretation](../../../bennett-dialect-spec/spec/errata-0.2.10.md), and [ISA §§9,10,12,13](../../../bennett-isa-spec/spec/Bennett-ISA-Spec.md). These are separate concerns:

- Dialect19.2 deliberately puts a whole process in R. Its startup/exit obligations remain valid; they must not become the only way to call a marked module.
- ISA10 already specifies CC-entry launch, arguments/results, program-scoped handles, run states, budgets and reversal. The missing native caller integration is not an absence of the whole launch ABI.
- Dialect19.4 promotes pointer-rich H callers when necessary. The audit does not invent direct host-memory-by-reference or require every eligible native caller to be promoted.
- ISA9.3 requires compatible layout/data when objects are actually linked together. Separate loaded programs are not automatically one object with one identical layout.
- A final native container may index unchanged ISA payloads; it must not add unknown fields/sections to the pinned ISA0.8 inner grammar.

Each finding has one `fat-object` P3 bead. The findings describe future mixed-object mechanics and are **deferred under the explicit audit-only assignment**, which requests no launch ABI or host shim implementation. This postpones mechanics, not the capability. Existing rung-3/4 implementation blockers retain their current priorities: `cyg.2`, `cyg.3`, `i0v`, `3j4`, `fgv`, plugin `bp-xyn`/`bp-ivy` and runtime `brt-nuu.2`. None is replaced by these P3 items. Estimates are rough engineering days for implementation plus focused integration, excluding contract-review waiting and full-domain certification; shared prerequisites mean the rows must not be summed as a project schedule.

## Findings

| Item | Bead | Change area | Rough effort |
| --- | --- | --- | --- |
| F01 | `bennett-driver-2wd` | Preserve native input roles alongside selected bitcode modules | 3–5 driver days |
| F02 | `bennett-driver-fk3` | Separate host libc and arithmetic from selected device closures | 5–8 driver days; 3–5 plugin/runtime days |
| F03 | `bennett-driver-vc7` | Distinguish process startup from callable module entry | 2–4 driver days; 3–5 plugin/runtime days |
| F04 | `bennett-driver-1xf` | Scope argv and launch inputs to the owning process and run | 3–5 driver days; 5–8 plugin/runtime days |
| F05 | `bennett-driver-b0r` | Produce a native host artifact containing zero or more ISA payloads | 5–8 driver days; 5–10 runtime/tooling days |
| F06 | `bennett-driver-1ky` | Select native comparison by module entry instead of a standalone process | 4–7 driver days; 3–5 runtime/plugin days |
| F07 | `bennett-driver-i9n` | Resolve component layouts and shared native addresses explicitly | 5–8 driver days; 5–10 plugin/runtime days |
| F08 | `bennett-driver-30q` | Compose native and per-component certificate inventories | 3–5 driver days; 3–5 contract/consumer days |
| F09 | `bennett-driver-2f2` | Report diagnostics and source classifiers at component scope | 2–4 driver days; 2–4 conformance days |
| F10 | `bennett-driver-kcc` | Bind module launches to program-scoped budgets handles and history | 5–8 driver integration days; 10–15 runtime/consumer days |

### F01: Preserve native input roles alongside selected bitcode modules

**Source:** `src/main.rs:20`, `src/main.rs:440`, `src/main.rs:461`, `src/main.rs:490`, `src/main.rs:510`.

**Observed assumption or missing mechanics.** Options.inputs is one list. Every input must be C/LLVM IR or bitcode; every module is verified by the selected LLVM major, checked against one triple/layout and merged into linked.bc. There is no role for an ordinary native object, native archive member or a separately retained unmarked module. Whole-link analysis is appropriate; equating its analysis input with every eventual device payload is the limitation.

**Exact mixed-object change.** Represent input provenance and native/device eligibility separately from the bitcode analysis closure. Retain ordinary native object/archive inputs for the final host link; request bitcode only for tainted/promoted definitions under dialect19.1/19.4. Preserve one ABI-compatible host triple/layout for the link: native retention is not permission for mismatched pointer layouts. Keep H-only definitions native while the plugin decides which definitions also need materialised variants. Record missing tainted bitcode as published coverage rather than requiring all native libraries to become device code.

**Contract and coordination.** Existing North Star3.3 and dialect19.1/19.4/19.8 define placement obligations. Publish driver input-role and native-link adapter conventions; no ISA instruction change is implied.

**Acceptance evidence needed.** A native main and unmarked native-only helper link with two marked bitcode modules; only the selected closures produce ISA payloads, native outputs match, and a missing tainted definition still gets the required coverage/fault diagnostic.

**Tracking and cost.** `bennett-driver-2wd`, P3, deferred; 3–5 driver days.

### F02: Separate host libc and arithmetic from selected device closures

**Source:** `src/main.rs:386`, `src/main.rs:507`, `src/main.rs:513`, `src/main.rs:530`, `src/main.rs:547`, `src/arith.rs:11`, `src/arith.rs:74`, `scripts/arith-instances.py:50`, `src/process.rs:64`.

**Observed assumption or missing mechanics.** One runtime and arithmetic library pair is selected for the merged module. Runtime closure and generated-instance overrides run before any driver-level host/device selection; the arithmetic collector scans every supplied IR file. This supplies required device definitions today, but cannot express an ordinary native libc/fenv ownership domain plus a separately materialised runtime domain. Native-only arithmetic references can also trigger device-instance generation.

**Exact mixed-object change.** Keep whole-link visibility for analysis while attaching runtime/arith closure provenance to the selected materialised variants. Generate/bind concrete instances needed by those variants; preserve unchanged native implementations and native libc/TLS/stdio ownership on H paths. Resolve globals and aliases once per declared ownership domain, including shared state and callbacks. Preserve exact materialised definitions in comparison; do not replace them with host libc or reintroduce host numerical fallbacks. Retain any library definitions S2 needs before analysis; this is variant selection, not blindly moving required linkage after S2.

**Contract and coordination.** Dialect19.1 requires libraries before S2;19.4 governs promotion and19.5 shared addresses. Publish variant/ownership metadata with plugin/runtime consumers rather than renaming private libc globals as an adapter.

**Acceptance evidence needed.** A native FP/libc caller keeps its native implementation and state while a marked closure uses verified generated instances and published runtime bodies; alias/fenv identities remain consistent and both compilation routes bind the selected instance hashes.

**Tracking and cost.** `bennett-driver-fk3`, P3, deferred; 5–8 driver days; 3–5 plugin/runtime days.

### F03: Distinguish process startup from callable module entry

**Source:** `src/main.rs:172`, `src/main.rs:512`, `src/main.rs:544`, `src/process.rs:12`, `src/process-entry.cpp:30`, `src/process-entry.cpp:37`, `src/process-entry.cpp:42`, `src/process-entry.cpp:106`, `src/process-entry.cpp:164`, `src/process-entry.cpp:178`.

**Observed assumption or missing mechanics.** The explicit reversible tier/entry option denotes a whole-process R entry. It unconditionally invokes process preparation, requires a C-like i32 entry, renames/internalises the user function, synthesises an argc/argv/envp wrapper and routes its return through exit. This is valid for the present whole-process mode; reusing it as the generic mixed-module entry route would reset native-owned context and terminate a native caller.

**Exact mixed-object change.** Keep whole-process R startup and C main exit semantics intact. Introduce an explicit entry role for callable module entries, retaining each published signature/calling convention, exported identity and return/fault behavior. Native main owns its startup; a module call receives only the required launch/context bindings and returns to the caller without process preparation or exit. Associate static images, errno/fenv/locale/stdio state with a declared owner and specify shared/reversible state lifetime. Follow dialect19.4 promotion when required instead of pretending arbitrary native state is directly reversible.

**Contract and coordination.** ISA10 already has CC-entry launch arguments/results. This needs an entry-role and context-ownership adapter, not replacement of ISA10. Preserve dialect19.2 and the lbq C-main interpretation.

**Acceptance evidence needed.** A native main with nondefault process state calls a non-main marked entry twice, receives its values without process exit/reset, and can reverse its device run under the applicable lifetime rules; the existing C0/C2/C3 whole-process preparation/exit regressions still pass.

**Tracking and cost.** `bennett-driver-vc7`, P3, deferred; 2–4 driver days; 3–5 plugin/runtime days.

### F04: Scope argv and launch inputs to the owning process and run

**Source:** `src/main.rs:169`, `src/main.rs:428`, `scripts/finalise-build.py:39`, `scripts/finalise-build.py:40`, `scripts/finalise-build.py:41`, `scripts/finalise-build.py:44`, `src/process-entry.cpp:130`, `tests/reversible.py:34`.

**Observed assumption or missing mechanics.** One invocation-level argv reply artifact is copied into every reversible launch directory. The finaliser admits exactly one bennett.argv request/reply with a fixed 4+2*pointer-width header, defaulting it to zero. It does not describe string/vector byte images, module/run ownership, or native-to-device address correspondence. The process wrapper later dereferences the supplied pointers. The empty-header fixture is not general argv/envp marshalling.

**Exact mixed-object change.** Retain bennett.argv only for the explicit process-start route that requests it. Bind supplied argument bytes and any backing regions to the selected entry/run; module entries called by native code use their declared arguments and an explicit process-context policy rather than mandatory process argv fetches. Complete the published argv adapter with byte-object ownership/lifetimes and device address mapping. Use ISA10 copied arguments or dialect19.4 promotion where applicable; do not treat a host pointer or qreg/token number as a device pointer or invent host-memory-by-reference semantics.

**Contract and coordination.** Existing ISA10 copies argument/entropy buffers and scopes tokens to a program. Exact argv byte transport and host-object mapping need a published adapter with plugin/executor consumers; fixed raw header addresses alone do not establish it. Existing bp-ivy/cyg.2 track the rung3 argv frontier.

**Acceptance evidence needed.** Nonempty process argv/envp strings survive forward/reverse/replay in the whole-process route. A separate module call needs no bennett.argv service, has independent run arguments, and cannot consume another run/program's argument objects or handles.

**Tracking and cost.** `bennett-driver-1xf`, P3, deferred; 3–5 driver days; 5–8 plugin/runtime days.

### F05: Produce a native host artifact containing zero or more ISA payloads

**Source:** `src/main.rs:594`, `src/main.rs:613`, `src/main.rs:625`, `src/main.rs:630`, `scripts/finalise-build.py:10`, `scripts/finalise-build.py:11`, `scripts/finalise-build.py:14`, `src/main.rs:687`.

**Observed assumption or missing mechanics.** Production completion verifies one host.bc/device.bc pair and launches.json, then finalises per-entry directories. It does not code-generate/link host.bc into an ordinary native artifact, embed/index multiple ISA objects, or connect native call sites to the published launch ABI. The finaliser requires at least one launch and identifies its output directory by entry alone; a native-only link or separately named modules with colliding local entry names have no container representation. This is missing final-link mechanics, not evidence that the existing per-entry split is wrong.

**Exact mixed-object change.** Add a final native code-generation/link phase retaining unmarked native inputs and binding selected host call sites through a published launch adapter. Package unchanged validated ISA object payloads beside/inside that native artifact with a versioned component/entry index, distinct component identities, native relocation/import records and explicit initialization/finalization ownership. Handle zero, one and many payloads; do not force an unmarked native-only link to manufacture a device launch. Choose/publish the outer packaging convention separately from the fixed ISA object grammar.

**Contract and coordination.** North Star2/3.3/4.4 requires this composition; ISA9/10 already defines inner objects and launches. Publish the outer native-container/index and binding convention. ISA0.8 rejects unknown inner fields/sections, so embedding must not silently extend its grammar.

**Acceptance evidence needed.** An ordinary native executable retains unmarked code, invokes two selected modules (including equal local entry names), and carries verifiable payload indexes; a native-only executable also links. Extracted ISA object bytes and closure hashes remain unchanged by packaging.

**Tracking and cost.** `bennett-driver-b0r`, P3, deferred; 5–8 driver days; 5–10 runtime/tooling days.

### F06: Select native comparison by module entry instead of a standalone process

**Source:** `src/native.rs:54`, `src/native.rs:75`, `src/native.rs:111`, `src/native.rs:143`, `src/native.rs:172`, `src/native.rs:278`, `src/native.rs:386`, `src/native.rs:401`, `src/native.rs:411`, `src/native.rs:467`, `tests/comparison.py:38`.

**Observed assumption or missing mechanics.** Comparison consumes one device module and emits standalone native O2/O0 executables with _start, comparison-only support, an optional C harness/backend and a strict static no-host link. The harness permits non-main callees already, so the current adapter does not literally require the materialised entry to be main. It still provides no component/entry selector, callable native comparison artifact or explicit association with the original native H callers and state.

**Exact mixed-object change.** Keep the existing strict whole-process/reference-component route. Add a selected module/entry comparison plan binding its actual materialised bytes, matching libraries, shared layout and input/result/fault ABI. Permit a comparison harness around a callable entry without applying process startup/exit to that entry. Separately identify the ordinary native H portion of a composed executable and any original native dependencies; retain the no-host-libc/libm requirement for the selected materialised device closure. Never solve marker imports by fake marker definitions or source-module substitution. Record per-component coverage and input/output observations.

**Contract and coordination.** Dialect17.7/19.5 and ISA9/10 supply identity/launch constraints; plugin must publish per-entry comparison variant provenance and symbol correspondence (bp-xyn). The new composition does not waive current cyg.3/ASan blockers.

**Acceptance evidence needed.** The same non-main marked entry used by native H code is compared at O0/O2 using its actual materialised variant, with exact bytes/return/fault/state observations and audited device imports. The native caller continues afterward; whole-process strict/no-host comparison regressions remain intact.

**Tracking and cost.** `bennett-driver-1ky`, P3, deferred; 4–7 driver days; 3–5 runtime/plugin days.

### F07: Resolve component layouts and shared native addresses explicitly

**Source:** `scripts/native-layout.py:18`, `scripts/native-layout.py:25`, `scripts/native-layout.py:29`, `scripts/native-layout.py:32`, `scripts/native-layout.py:45`, `scripts/native-layout.py:49`, `src/native.rs:243`, `src/native.rs:272`, `src/native.rs:399`, `src/process-entry.cpp:48`.

**Observed assumption or missing mechanics.** The default comparison layout reader requires every adjacent launch layout to be identical. It emits one LP64 heap table and one linker script that collects all native rodata/data/bss before the device heap. Device globals/regions deliberately fail because their LLVM symbol mapping is absent. This is honest fail-loud behavior, but cannot associate independently loaded modules with different compatible layouts or distinguish native-private data from boundary-visible storage. LP64 itself is an explicit current runtime capability, not proof of a whole-program assumption.

**Exact mixed-object change.** Select the authoritative layout by component/program and entry closure. Preserve the exact layout-table ABI for each comparison, map shared global/function identities to the corresponding LLVM/native symbols and enforce the production host link addresses when A(F) crosses the boundary. Reconcile layout entries under ISA9.3 when objects are actually linked into one program; do not force unrelated separately loaded programs to share an identical layout. Record ownership of native-private, copied and shared/promoted regions. Replace whole-native-data placement with contract-preserving placement of the relevant ranges plus explicit disjointness/import constraints, retaining strict equality and low-address/no-merge rules where the accepted dialect requires them.

**Contract and coordination.** Existing rung3/4 shared-symbol-map repair is cyg.3/bp-xyn at its current priority; this P3 finding adds mixed-component selection/ownership. Any new address-translation or host-reference mode beyond dialect19.4/19.5 needs an explicit contract amendment, not a private driver rule.

**Acceptance evidence needed.** Two components with distinct layouts load as separate programs; shared symbols agree with the native host address map; actual links with conflicting shared layout/data still fail. Native-private data does not silently relocate the device heap or become device state. Existing exact-layout mismatch tests stay enforced.

**Tracking and cost.** `bennett-driver-i9n`, P3, deferred; 5–8 driver days; 5–10 plugin/runtime days.

### F08: Compose native and per-component certificate inventories

**Source:** `src/main.rs:506`, `src/main.rs:613`, `src/main.rs:679`, `scripts/finalise-build.py:13`, `scripts/finalise-build.py:20`, `scripts/finalise-build.py:23`, `scripts/finalise-build.py:33`, `scripts/finalise-build.py:36`, `src/native.rs:420`.

**Observed assumption or missing mechanics.** The driver has one build manifest and host/device hash pair. The finaliser collects layouts/budgets by entry string and writes one driver build digest into every entry certificate/receipt. Existing per-entry certificates and immutable ISA bytes are useful foundations, and an aggregate build digest is valid provenance; it is not an inventory of a final native executable plus independently identified module payloads, exports/imports/relocations and launch bindings.

**Exact mixed-object change.** Keep ISA symbol/closure/object identities separate from a versioned outer container identity and build provenance. Inventory the native artifact, each selected ISA component and entry signature/closure, referenced data/layout images, required services/runtime variants, relocation/binding records and component-scoped budget/coverage/certificate artifacts. Use component identity plus local entry as the key. Preserve per-entry verification and certificate composition; package hashing must not replace closure-hash bindings or grant unmarked native code a reversible proof label. Bind native-only dependencies as native provenance, not as materialised device coverage.

**Contract and coordination.** ISA9.2/9.3/12 owns semantic identity and certificate composition, and13 coverage. Publish outer inventory fields with certificate/conformance consumers; do not add unrecognised fields to the pinned inner certificate/object schema.

**Acceptance evidence needed.** Changing unmarked native bytes changes the outer/native provenance without silently changing an untouched ISA semantic identity; mutating a selected payload, binding or required shared image invalidates its verification. Two modules with the same local entry name remain distinct, and all per-entry artifacts verify after packaging.

**Tracking and cost.** `bennett-driver-30q`, P3, deferred; 3–5 driver days; 3–5 contract/consumer days.

### F09: Report diagnostics and source classifiers at component scope

**Source:** `src/report.rs:53`, `src/report.rs:58`, `src/report.rs:68`, `src/classifier.rs:7`, `src/classifier.rs:16`, `src/classifier.rs:119`, `src/classifier.rs:129`, `src/classifier.rs:152`, `src/native.rs:205`.

**Observed assumption or missing mechanics.** Structured failures identify the function as <whole-program>, and the global reversible option adds the R typed-fault prerequisite to failures. Native detection names one materialised subject. The original-input classifier compiles all original C inputs plus a harness into a standalone executable with an independent diagnostic layout/native runtime. These labels are honest for current component tests, but would not identify which native/module entry failed or which parts of a composed artifact were checked.

**Exact mixed-object change.** Carry component/entry/stage provenance into failures, native detection and classifier observations. Associate R prerequisites with affected R entries; keep a true link/build failure fatal without reporting it as evidence that every module executed. Retain separate original-input definedness classifiers and their explicit exclusions, with source/variant mapping for each claimed comparison. Native H source diagnostics are separate coverage, not evidence of device instrumentation. Use published ISA program-point identifiers where applicable rather than inventing a whole-binary proof label.

**Contract and coordination.** ISA13 and dialect25 govern coverage/refusals. Component identifiers belong in the published outer adapter/report mapping; preserve canonical inner coverage/proof semantics and explicit UBSan/ASan limitations.

**Acceptance evidence needed.** A host-only link failure, a selected-module materialisation failure and a device-run fault have distinguishable scopes and truthful overall status. An undefined source input is excluded only for its associated observation; uninstrumented native modules cannot inherit the device-memory coverage claim.

**Tracking and cost.** `bennett-driver-2f2`, P3, deferred; 2–4 driver days; 2–4 conformance days.

### F10: Bind module launches to program-scoped budgets handles and history

**Source:** `src/main.rs:78`, `src/main.rs:424`, `src/main.rs:432`, `src/main.rs:579`, `src/main.rs:625`, `scripts/finalise-build.py:23`, `scripts/finalise-build.py:39`.

**Observed assumption or missing mechanics.** The driver forwards build-time budget/disk/entry options, records artifacts, writes replay-style argv replies and reports compilation completion. It does not load a program or call run/wait/reply/reverse/close; there is no implemented native caller adapter here. Thus a compiled launch is not evidence that a native host can suspend, service a request, resume or reverse a selected module. There is also no driver code casting qreg/token handles to pointers; absence of the adapter must not be misreported as an existing handle-representation bug.

**Exact mixed-object change.** Integrate a native caller adapter using the existing ISA10 program/run APIs, with per-loaded-program budget tokens/register ids, copied arguments/entropy and explicit service dispatch. Keep R effect tapes and invocation-tree history owned by the run; do not reset them during each module call. Respect run states, exclusive memory/register ownership until CLOSED and reverse eligibility before host mutation/reuse. Choose/document whether compatible modules link into one program or load as separate programs; never conflate handle namespaces or put runtime mutable state into object identity. Distinguish compile-complete from linked/loaded/executed evidence.

**Contract and coordination.** ISA10 already specifies these handles, copying, states and ownership. No wholesale launch ABI invention is needed. Missing outer binding/context/service conventions must be published; no new host-memory-by-reference or tape mechanism is authorised by this audit.

**Acceptance evidence needed.** Native code launches two modules, handles a declared HOST_REQUEST, resumes and observes results/faults, reverses an eligible run and closes/unloads cleanly. Cross-program handle reuse and forbidden concurrent/mutating accesses fail as the ISA requires; startup and tape history are not rerun/reset per callback.

**Tracking and cost.** `bennett-driver-kcc`, P3, deferred; 5–8 driver integration days; 10–15 runtime/consumer days.

## Coverage of the source review

| Surface reviewed | Findings or reason no additional finding is needed |
| --- | --- |
| `src/main.rs` input/options, library closure, orchestration, outputs and failure routing | F01–F05,F08–F10. The same-major/triple check is a valid link ABI constraint; it must not be mistaken for a requirement that native code execute on the device. |
| `src/process.rs`, `src/process-entry.cpp` | F02–F04,F07. Current whole-process preparation is intentional; the risk is reusing it for callable module entries. |
| `src/native.rs` | F02,F06–F09. It supports an explicit non-main callee harness already and preserves materialised input hashes. Its static process/reference route is not a completed mixed executable. |
| `src/classifier.rs` | F09. Independent source diagnostics are correctly separate from materialised results; they need explicit source/component association for composition. |
| `src/arith.rs`, `scripts/arith-instances.py` | F02. Literal type/hash verification and arbitrary-width support are reusable; selection/cache provenance currently covers one build closure. |
| `scripts/native-layout.py` | F07. No default heap or fake global placement is acceptable in either route. |
| `scripts/finalise-build.py` | F04,F05,F08,F10. Per-entry directories, layout/budget records and unchanged ISA object bytes are useful existing foundations. |
| `src/report.rs` | F09. Preserve fail-loud overall build status while identifying the affected component/entry. |
| `src/json.rs`, `scripts/plugin-identity.py` | Generic canonical serialization and public pass-plugin identity querying; neither decides program placement, object ownership or host/device lifetime. |
| `scripts/pre-push`, `scripts/install-hooks.sh` | Operational pinned-gate/hook tooling, not the product launch ABI or fat-object format. Gate isolation is tracked in3j4. |
| `tests/inputs.py`, `tests/arith_production.py` | Existing multi-input/marked-entry tests establish useful component baselines, not final native packaging (F01,F02,F05). |
| `tests/process.py`, `tests/reversible.py` | Whole-process C entry and zero-header argv expectations are correctly scoped current fixtures; retain them and add separate callable-module cases (F03,F04,F10). |
| `tests/comparison.py`, `tests/native_memory.py`, `tests/native_faults.py`, `tests/native_byval.py` | Strict adapter, explicit harness, layout and memory/fault coverage remain required; they do not establish all mixed host/module observations (F06,F07,F09). |
| `tests/classifier.py`, `tests/integration.py`, `tests/reports.py` | Source-vs-materialised labels, frozen launch/reference values and diagnostics are useful; final composed coverage and provenance require F08/F09. |
| Remaining arithmetic/API tests, Rust test launchers, `tests/toolchain.py` | Component numerical/publication checks and explicit immutable tool inputs, not host/device placement decisions; preserve them when adding mixed cases. |

No qreg/token handle representation or independent production effect-tape mechanism is implemented by the driver. Do not infer one from C++ `ptr` values used for C process vectors. F04/F10 require the eventual adapter to use the published handle/copying/ownership rules, and any extra host-reference capability must be specified rather than smuggled through integer arguments. Build-time budget artifacts already have per-entry records; F08/F10 add component/program ownership instead of discarding this support.

## Dependency order and scope of follow-up

F01/F02 establish input and closure roles. F03/F04 specify entry and process input ownership. F07's selected layout/shared symbol mapping and F08's container inventory make F05/F06 packaging and comparison auditable. F10 integrates the existing ISA run lifecycle; F09 keeps observations and failures scoped throughout. This is a proposed implementation order, not a newly adopted wire format, handle scheme or gate stop condition.

Cross-repository publication requests are queued under this job's `cross-repo-beads.md`: native container/index conventions, plugin comparison/variant/symbol provenance, and argv/process-context/run binding conventions. The requests explicitly reuse ISA9/10 and do not demand a silent ISA upgrade, a new unchecked host-pointer ABI, fake marker definitions, or replacement of materialised runtime bodies with hosted libc.

## Verification and source snapshot

Verification for this audit checks every source anchor is in range, every reviewed production file has a disposition, every finding maps to exactly one exported P3 deferred `fat-object` bead, all local Markdown file links resolve, and the snapshot hashes match. It does not execute or validate the proposed mixed-object mechanics. The prior focused component checks and current blockers remain in `docs/PROGRESS.md`; an audit-only change does not justify repeating heavy gates.

| Reviewed production source | SHA-256 |
| --- | --- |
| `scripts/arith-instances.py` | `7af2e930dd7ca9ab726eabb41870844c84f33d52beb71764d65f5b7de540b697` |
| `scripts/finalise-build.py` | `c4d6259168ee461b96176a519ce69cfa84bb7b6fd2595d9c0dbb802dfa6d483b` |
| `scripts/install-hooks.sh` | `f86e32efa671fb5ecedf69a4205b3ef79346c24b15731fa5b878c2e6f67661f8` |
| `scripts/native-layout.py` | `8c5289f59a67d9ffadc4af6cc765ab83e7dceca9dfcc27d366aa17a2af017e67` |
| `scripts/plugin-identity.py` | `4355ee506ea12db4d40d7f343d1e8b201e1145f7afd59757b0baf9908b68ec98` |
| `scripts/pre-push` | `c8286d665a2c8b79e9e42e97d7c996164fc571887f37e0dd8240717eac2bfad0` |
| `src/arith.rs` | `e0ff17256cf2d0f970882f9be06bed28d56aec1e5c76b160fd4770aff54c5f61` |
| `src/classifier.rs` | `031dc1159efaf72f31ac6cf1d05a6f03c146d13304ee0cd38c42cc55eb4517d0` |
| `src/json.rs` | `adae9229b12753b5064b105a206eff0c91d57bbeb2564a46f82fe58b93d7b7da` |
| `src/main.rs` | `70829dbcbb188d956c94a5666f75f531eb298e0dfede769e16da03d33e357052` |
| `src/native.rs` | `0dc4ddb69439a087e42c570277337e92c73629f4b39a5df4084c7524dfbf2ba2` |
| `src/process-entry.cpp` | `f88ac0274dcb8ff0dacc5fc8e750f477e88886b5e46f709c85c2364cbf3ad66a` |
| `src/process.rs` | `b7e688bb37f49ff5f273a1165e82db974a0602cbbf63ab9979d95355bcfb8f20` |
| `src/report.rs` | `6f7f4399be4f98ef16269309b90a90842fc0ade39424fe8110a441651a73aec4` |
