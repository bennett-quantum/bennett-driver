# Process initialization and finalization

For reversible R process entries, the driver binds ELF array boundaries after
whole-program linking and LTO, before plugin analysis and materialisation.
`llvm.global_ctors` and `llvm.global_dtors` supply their real callbacks, priorities
and selected associations. LLVM's link selection resolves associated COMDATs.
Pointer objects in `.preinit_array`, `.init_array[.priority]` and
`.fini_array[.priority]` contribute their actual entries. Stable ascending-priority
storage preserves repeated registrations and input order within a priority.
These rules follow the [LLVM global registration contract](https://llvm.org/docs/LangRef.html#the-llvm-global-ctors-global-variable).

Each nonempty array has one ordinary LLVM backing object. Section contributors
become alias views at their own offsets; start/end symbols alias the actual
start and one-past-end addresses. An empty inventory uses coincident aliases one
past the existing process empty-argv object, without allocating a dummy table or
null callback. Existing defined bounds retain their backing storage and must
cover the linked registrations in order. The consumed LLVM registration lists
are removed, so native code generation cannot register the callbacks twice.

After process state preparation, startup dispatches preinitializers, then the
real libc init dispatcher when present, otherwise the real `_init` hook and init
array. The runtime's existing exit path runs atexit callbacks, traverses the fini
array in reverse and flushes buffered output. No replacement exit implementation
or synthetic callback is introduced.

`process-init-fini.json` records the selected callbacks, associations, priorities,
input order, backing object and byte offsets. The manifest binds the report and
rewritten bitcode by hash. `--bennett-emit=process-bitcode` binds the complete
preparation-stage inventory without running LTO or claiming execution. Full
production binds the post-LTO inventory. The ordinary device global/native
symbol mapping and fixed-layout audit apply to the backing objects and aliases.
