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
class, vscale/CPU, qreg/inplace/warning and arena controls, and preserves their
order and values for the backend. Bind, device and class options may repeat.
`-bennett-closed-unit` accepts its specified flag spelling, as well as an explicit
boolean. A snapshot input is opened and hash-bound before backend processing;
only successful processing can attach that snapshot hash to a build record.

Closed-unit processing uses the plugin's closedness check and fallback. Tests
compare both a closed entry and a function-pointer entry with whole-program ISA
output; the current 0.2.13 component passes on both LLVM majors. The historical
producer cannot compile that latter indirect CC call.

Other controls still require a published backend transform edge. The current
plugin does not register the descriptor binding/payload, snapshot, platform,
class or vscale controls. Such requests fail as `BD-B-MODE-BACKEND`, retaining
the complete argv and backend diagnostics and producing no successful build or
certificate. These are required capabilities held under `9zg`, not unsupported
source programs. Admission tests for this explicit dependency are separate from
feature acceptance. No private descriptor metadata or snapshot convention is
invented by the driver. Mode publication must preserve ordinary native H and
scope runtime bindings to selected device closures.
