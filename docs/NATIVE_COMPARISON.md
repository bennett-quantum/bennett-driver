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
marker definitions. The strict freestanding link currently lacks that real
launch backend (`bennett-driver-r1p`). The backend must load the actual selected
ISA object, call the report's `binding_symbol` with an owned live
`bennett_program_t`, and preserve register state, class and clean-free faults.
The producer's hosted CRT/VM DSO example does not certify this startup path.

Resolved native ELF addresses must still be supplied to the production layout
and verified against source correspondence. The current nonempty global/region
mapping gap is tracked by `bennett-driver-crx`; it is an implementation
obligation, not a source-language restriction. Full freestanding ASan remains
`brt-nuu.2`. Component receipts do not close `cyg.3` or `i0v` while these
native/device equality and diagnostic requirements remain unverified.

A mixed native/device object retains its ordinary native host and unmarked
modules. Entry selection, binding lifetime, runtime state and comparison address
maps belong to the selected component/program. Neither process preparation nor
native comparison may reset native main or claim that the device module owns
the whole binary. No host-memory-by-reference or new launch ABI is introduced
by this adapter.
