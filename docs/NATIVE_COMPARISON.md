# Native comparison adapter

The driver keeps the original materialised bitcode unchanged. Comparison-only
adaptation, memory checks, transports and code generation have separate hashes
and artifacts. A linked binary is link evidence; it is not evidence that native,
ISA forward, reverse and replay outcomes agree.

For an actual produced entry, select its published plugin launch record:

```sh
bennett-driver --bennett-llvm-major=18 \
  --bennett-materialised=production/device.bc \
  --bennett-comparison-entry=top \
  --bennett-comparison-launch-record=production/top/launch-record.json \
  --bennett-plugin=/path/to/matching/libbennett-plugin-18.so \
  --bennett-plugin-sha256=ACTUAL_SHA256 \
  --bennett-native-input=harness.c \
  --bennett-comparison-layout=resolved-device-layout.json \
  --bennett-out=comparison
```

`top` is a selected callable component, not necessarily `main`. The launch
record path is configurable; if omitted, the current producer convention is
`device.bc`'s parent plus the selected entry plus `launch-record.json`. This
convention is behind the driver adapter and is not an ISA container format.
The whole-process R option's entry also selects its native comparison entry;
its startup and ISA0.8 typed-fault obligations remain separate.

The matching plugin must publish `bennett-native-comparison`,
`bennett-native-comparison-finalise` and `bennett-native-host-imports`, as
documented by its [native adapter](../../bennett-plugin/docs/NATIVE_COMPARISON.md).
The driver checks its public identity and requested SHA before executing it.
It then:

1. Runs the published prepare-only pass on the exact original module and selected
   record, preserving source correspondence and introducing no backend state.
2. Links the explicit comparison harness and required library closure, then runs
   the matching published runtime memory/fault checker. Harness globals are
   included in its live-object metadata.
3. Finalises the prepared/checked component with the plugin and records its
   native report, including binding symbol and source/global/function aliases.
   The external checker receipt remains the driver's evidence: finalisation
   alone does not claim memory checking.
4. Adds comparison-only support, closes newly introduced host imports using the
   public host-import pass, and verifies the result.
5. Generates O0/O2 machine code from the same checked IR with `llc`, without a
   second source IR optimiser. Both variants use branch lowering rather than
   backend-private jump tables (`jump-table-density=101` and the optsize
   equivalent), keeping their extra readonly data from moving the fixed heap
   page. This is a recorded code-generation choice, not a source-program limit.
   The codegen object hash, strict static link argv and original device hash are
   recorded. The exact resolved-layout assertion remains enforced.

Destinations are admitted before writes: comparison records, executables and
generated inputs/evidence must not alias one another or original inputs,
including canonical, symbolic and hard links. The final original module hash is
checked again after comparison work. A failed plugin stage cannot leave its
incomplete output bitcode as an apparently usable component.

`manifest.json` binds the selected entry, plugin, original module and launch
record, prepared/finalised bitcode and reports. `native-comparisons.json` and
`native-detection.json` distinguish a checked entry record from explicit module
input without a verified producer receipt. The latter remains useful for small
adapter diagnostics and cannot be presented as actual producer-corpus evidence.
Original-input UBSan classifiers remain separately labelled, with their own
layout and explicit coverage exclusions.

The gate retains the historical plugin used for frozen rung-2 expected objects.
A separately pinned `bennett-plugin-native-comparison` sibling supplies this
adapter; `BENNETT_DRIVER_NATIVE_PLUGIN_ROOT` selects it for the focused adapter
test. It never silently replaces historical expected outputs.

## Remaining acceptance

Current actual-component tests prepare/check/finalise real produced marked
entries, verify original module/record hashes, reject wrong entry/plugin pins,
and require the real `bennett_qreg_new/free` imports rather than fake source
marker definitions. The isolated provider profile below supplies owned startup and real launch/qreg
calls while the component keeps the strict freestanding link. Select the actual
provider and target explicitly; program binding and lifetime are evidenced per
execution. The producer's hosted example alone does not certify this driver path.

Resolved native ELF addresses must still be supplied to the production layout
and verified against source correspondence. Explicit nonempty global/region mappings are supported and audited as described
below. Automatic complete producer/ISA/native mapping and invocation evidence
remain part of the full comparison obligation. Full freestanding ASan remains
`brt-nuu.2`. Component receipts do not close `cyg.3` or `i0v` while these
native/device equality and diagnostic requirements remain unverified.

A mixed native/device object retains its ordinary native host and unmarked
modules. Entry selection, binding lifetime, runtime state and comparison address
maps belong to the selected component/program. Neither process preparation nor
native comparison may reset native main or claim that the device module owns
the whole binary. No host-memory-by-reference or new launch ABI is introduced
by this adapter.

## Explicit fixed-address range mapping

An explicit `--bennett-comparison-layout` adapter file can annotate its globals,
interface regions and arena with native storage correspondence. These fields
are **driver input annotations**; they are not written into ISA layout sections.
For example, a four-byte source global at the resolved device address can use:

```json
{
  "null_size": 4096, "ptr_width": 64,
  "heap_base": 69632, "heap_limit_max": 1048576,
  "materialised_sha256": "ACTUAL_INPUT_FILE_SHA256",
  "globals": {
    "G1": {
      "base": 65536, "size": 4, "image": "G1",
      "native_symbol": "counter", "llvm_name": "counter", "alignment": 4
    }
  },
  "interface_regions": {}
}
```

Use the selected producer report's native alias as `native_symbol` and its LLVM
storage name as `llvm_name`. The latter defaults to the native symbol for an
ordinary named object. For an explicitly sectioned or differently named storage
object, `native_section` selects its actual native input section instead.
Codegen emits individual data sections; the linker binds each declared range
and checks its exact extent and symbol address. No guessed sequential addresses
or private `__bennett_rt_blk.*` identities are used.

`interface_regions.<entry>.<region>` annotations supply `base`, `size`,
`native_symbol`, optional `llvm_name`/`native_section`, and `alignment`; `arena`
uses the same object form. These describe fixed native backing objects for the
selected comparison profile, not arbitrary host pointers or a new memory
registration/transfer ABI. The caller must supply the true source correspondence
and device extents. Ranges must not overlap each other or the heap. Interface
and arena storage above the heap has a separate ELF load segment, leaving the
actual heap mapping vacant. Source data and code also retain separate segments.
The first-page-after-native-data heap assertion is unchanged.

A nonempty map requires the exact original materialised file SHA. After linking,
the driver independently reads the real ELF symbol table and validates every
mapped object's address, extent, alignment and data-symbol kind. The resolved
binding inventory and codegen object hashes are recorded. Missing/stale maps,
wrong object extents, heap overlap and inconsistent aliases fail explicitly.
The focused test executes mapped globals, a preserved input image and mutable
arena at O0/O2 on both majors. This removes the old categorical nonempty-layout
refusal; a selected producer/ISA/native full comparison still requires the real
backend, complete source-map construction and invocation verification described
above.

## Published R device globals

For the receipt-bound R producer, the driver reads the preparation report's
`device_globals` association by ISA global ID. It verifies the selected entry,
materialised, launch-record, build and launch hashes, then matches each published
source key to exactly one global symbol row. The inventory, fixed base and size
must agree with the authenticated build and launch layout. Missing, duplicated,
stale or conflicting associations fail before native layout generation.

The resulting native alias, LLVM storage name and alignment annotate only the
driver's `resolved-layout.json`. The ISA objects and producer publication remain
unchanged. Explicit adapter annotations must agree with this correspondence;
legacy reports without the handoff retain the explicit-map route. The linker
section assertions and independent ELF address/size/alignment audit still apply.
This association establishes storage correspondence; the selected R component
also requires its real program binding and startup lifecycle.

## Isolated hosted launch provider

The reviewed dialect §17.7 boundary in publication
`9bbf6dee3ab6ce94030e01a1af98df28fe19e683` permits a genuine launch provider
in an isolated hosted domain. Select it explicitly:

```sh
bennett-driver --bennett-llvm-major=18 -bennett-dialect=0.3-r1 -bennett-isa=0.9 \
  --bennett-materialised=production/device.bc --bennett-comparison-entry=top \
  --bennett-plugin=PLUGIN --bennett-runtimes=RUNTIMES --bennett-arith=ARITH \
  --bennett-sysroot=SYSROOT --bennett-native-provider=libbennett_vm.so \
  --bennett-native-target=TARGET_JCS --bennett-layout-data-base=65536 \
  --bennett-out=comparison
```

The target must be the canonical target document accepted by the public launch
API. Use the same data/text placement when producing the ISA object. On a host
that forbids mapping the first 64 KiB, the producer's published
`--bennett-layout-data-base=65536` option supplies that common layout. The driver
fails on mapping collisions or a different returned mapping; it never relocates
an already produced object or edits its device layout.

The driver emits a freestanding static `native-O0.component`/`native-O2.component`
and a hosted launcher at the usual executable path. The component retains the
matching-major runtime/arithmetic closure, checks, fixed device-global ranges,
heap boundary and linker/ELF assertions. Dedicated comparison-only sections
prevent MC string pooling from coalescing mapped storage. This changes storage
attributes in the comparison copy after adaptation while preserving global
initialisers and the original materialised artifact. Native-only
shadow-stack and backend bookkeeping occupy a separate segment after text,
outside the device's declared global/heap ranges. The component is readable
and deliberately lacks standalone execute permission; the launcher owns startup.

The hosted PIE bootstrap maps those ELF segments at their exact addresses and
loads the provider using `dlmopen(LM_ID_NEWLM, ..., RTLD_NOW | RTLD_LOCAL)`.
The component is not registered with the dynamic linker. Provider/libc symbol
resolution therefore cannot substitute for its materialised/runtime/arithmetic
functions; component calls to the launch API use an explicit driver gateway.
That gateway forwards to the genuine provider functions. The bootstrap loads
the authenticated selected ISA object through `bennett_load`, passes its real
live program to the exact binding symbol, invokes the selected native entry,
and calls `bennett_unload` after component execution and cleanup.

An explicit native input defining C `main` can call the selected component with
its required arguments. Otherwise the generated caller invokes the selected
entry directly using its C process ABI. A supplied binding relocation alone
never establishes startup or lifetime; a reversible comparison without the
provider configuration stops before code generation. The sjn reference-only
control verifies this. Native process exit and typed-fault signals are observed
at the component boundary so the provider can be unloaded; their actual status,
stdout/stderr and signal outcome are preserved. For normalised exit, comparison
instrumentation checks the published §14.4/§14.7 EH record at protected control
boundaries. Active4 transfers its stored selector through the driver bootstrap
after the actual runtime cleanup and EH writes. This realises the non-returning
exit instead of spinning in the normaliser's unreachable continuation. Original
instructions and cleanup stay in the comparison copy; the immutable producer
artifact is not changed. Other EH selectors retain their original handling.

The provider plan and per-variant configuration bind the component, bootstrap,
original materialisation/launch identities, target and provider. They separately
hash the provider's and bootstrap's transitive library closures. Each execution
checks these hashes, verifies the actually loaded provider namespace/closure,
and writes `native-O*.runtime.json` with binding/entry/unload outcomes and real
qreg allocation/free successes. Failed execution cannot reuse an old successful
receipt. A linked build record says execution is pending; the runtime receipt
and actual comparison observations provide execution evidence.

`native_startup` executes real marked allocation/clean free/return7, an allocator
isolation witness, typed-fault cleanup, real provider dirty-free rejection, the
unused-binding control, immutable
input checks, and the unmodified musl hello workload on LLVM18/23 at O0/O2.
Full freestanding ASan, complete function-address correspondence and broader
mixed-container acceptance retain their separate outstanding obligations.
