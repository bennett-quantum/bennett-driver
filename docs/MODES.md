# Contract profiles and modes

Production callers explicitly request dialect `0.2.13` and ISA `0.8`. The driver
also accepts explicit historical dialect `0.2.10` for the frozen rung-2 regression.
Each profile requires its own exact plugin identity; installing a newer plugin
never changes an old caller's request. Materialised adapters default to `0.2.13`;
an old receipt requires its old profile explicitly. The lifting map remains
`0.2.9` and normaliser `0.2.8`, independently of the full dialect version.

The build record binds the actual selected library/module bytes and generated
instance manifests, executed pipeline, resolved budgets/layouts and refreshed
certificate receipts. Changed helper bodies require new materialisation and
closure evidence. Passing a version negotiation test does not certify allocator
bookkeeping, PPC arithmetic, or all dialect semantics. Current publication and
root configuration adoption remain tracked by `0ai` and `193`.

The driver admits the published oracle/bind/dev/payload, snapshot, platform,
class, vscale/CPU, qreg/inplace/warning and arena controls, and records their
order and values. Bind, device and class options may repeat.
`-bennett-closed-unit` accepts its specified flag spelling, as well as an explicit
boolean. A snapshot input is opened and hash-bound before backend processing;
only successful processing can attach that snapshot hash to a build record.

Snapshot input is a driver adapter format, with exactly `schema` and `globals`:

```json
{"schema":"bennett-driver-snapshot-1","globals":{"g":"07"}}
```

Each key names a defined mutable LLVM global; each value is its complete storage
image in hex, including padding. The extent must equal the target DataLayout's
allocation size. The external synthesis tool preserves alignment, address space,
aliases and byte representation, including pointer-valued images. It applies
the image before post-link optimization, without modifying the original input.
Unknown globals, constants and wrong images fail explicitly. This format adds
no fields to ISA objects. Native-only snapshot builds keep ordinary host libc.

Class options append unique names after the input modules' normative
`bennett.classes` lists, retaining link/option order. Fixed-vscale preparation
runs on the complete linked closure before LTO. Equal fixed source attributes
take precedence; otherwise the requested link value fixes the intrinsic and
representable exact LLVM range attributes. A non-power-of-two scalar vscale
constant works directly; scalable vector cases not expressible by exact LLVM
range attributes retain an explicit backend dependency. The driver does not
substitute a different vector width.

Closed-unit processing uses the plugin's closedness check and fallback. Tests
compare both a closed entry and a function-pointer entry with whole-program ISA
output; the current 0.2.13 component passes on both LLVM majors. The historical
producer cannot compile that latter indirect CC call.

Other controls still require a published backend edge. Oracle synthesis must
retain the program root before LTO and settle the generated callable entry's
register arguments/results and ownership. The descriptor ABI alone does not
choose that operational entry adapter. The existing device CC launch API can
support a device-only profile once its generated entry/register associations
are settled; this need not wait on the future mixed native-callable contract.
Oracle requests stop at that preparation decision. The driver does not invent
a native shim. Registering only a late option cannot restore a deleted root.
The remaining platform/CPU/control options reach the backend unchanged. The
current plugin does not register them. Such requests fail as `BD-B-MODE-BACKEND`, retaining
the complete argv and backend diagnostics and producing no successful build or
certificate. These are required capabilities held under `9zg`, not unsupported
source programs. Admission tests for this explicit dependency are separate from
feature acceptance. The configured-class production test also remains red:
the actual plugin rejects class 1 under §3.4 even with the proper merged table.
That test is mandatory; class metadata preparation alone is not class execution.
Mode publication must preserve ordinary native H and
scope runtime bindings to selected device closures.
