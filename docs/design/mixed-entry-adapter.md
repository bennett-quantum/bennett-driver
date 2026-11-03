# Driver entry adapter proposal

Status: reviewable producer/consumer design for `62k`, pending ISA-owned
publication. It defines no shipped schema, native shim or launch ABI. The
[ISA outer-inventory amendment](../../../bennett-isa-spec/docs/notes/2026-11-02-derive4/container-and-certificates.md)
proposes `bennett-mixed-inventory-1`; that name and its compatibility rules are
unpublished. The driver currently accepts ISA 0.8. Applying a proposal written
against 0.9, or shipping it with a later ISA version, requires an explicit
consumer contract upgrade. Unknown fields stay outside existing ISA objects.

The native host retains `main`, argv/envp, host libc and native-only libraries.
Each marked component supplies only its selected device closure. Independent
embedded programs keep independent namespaces, layouts and ledgers. Sharing a
native container does not perform an ISA link or register native memory.

## Producer handoff

The driver adapter consumes plugin-defined locators for materialised variants,
launch entries, inner ISA bytes, certificates, coverage, builds and layouts.
The locators are configurable adapter inputs. Neither `out/main` nor
`launches.json` becomes a normative ISA packaging rule. The adapter must resolve
an explicit component and local-entry key, rather than search for one global
`main` or infer an entry from a directory name.

| Association | Required data and validation |
|---|---|
| Native artifact | Final native bytes, length/digest, target, toolchain and native dependency provenance. Its digest differs from the detached inventory identity. |
| Program | Container-local program id; exact embedded or detached payload slice and digest; inner semantic object identity and versions; ordered source members and actual link recipe. Verify bytes, bounds and inner identity separately. |
| Device entry | `(program id, local CC entry)` plus actual CC signature/interface and linked closure. It is distinct from an R function or a quantum region root. |
| Native callable | Exported ABI symbol, target calling convention and versioned native adapter description; explicit device-entry key. Native-only symbols have no such association. |
| Region root | Every root invoked by that CC entry, with its interface/closure identity, certificate, optional schedule, build, layout and budget-selection references. |
| Images/layout | Selected fixed-address or future mapped profile; shared-image bytes and mappings; native/LLVM/device symbol correspondence. Check real linked ranges and identities. |
| Runtime | Required launch/runtime/service versions and providers, owning program/ledger, required images, load/unload and outstanding-run rules. |
| Invocation | A separate runtime record binds a static entry/root to its resolved arguments, selected budget tuple, token identity, program instance, run and replay profile. Runtime state is not part of an immutable executable inventory. |

All references resolve to the required artifact kind and verified bytes.
Native artifact, outer inventory, extracted byte slice, ISA object and device
closure identities are separate. The detached inventory avoids a self-hash
cycle. A future embedded inventory needs an explicit exclusion profile; the
driver must not invent one. Changed device links, wrappers, helper bodies or
layouts require fresh closure/certificate evidence. Copied inner objects stay
byte-identical and keep their existing semantic identities.

## Two selected entries in an ordinary host

These are concrete association examples, not serialized schema instances or
claims that the native adapter exists. `H_A`, `H_B`, `C_A`, `C_B`, `L_A` and
`L_B` denote separately verified payload, closure and layout identities; actual
production records must contain the prescribed digests and signatures.

| Native symbol/role | Program / device CC entry | Device root and proof association |
|---|---|---|
| `main`, `host_log` | none | Native argv/libc and host-only counter need no ISA frame, region or certificate. |
| `module_a_call(uint8_t)` | `A / run`, scalar adapter, payload `H_A` | `A / add_one`, closure `C_A`, layout `L_A`, certificate/build/budget selection for that root. |
| `module_b_call(uint8_t)` | `B / run`, scalar adapter, payload `H_B` | `B / xor_mask`, closure `C_B`, layout `L_B`, its own certificate/build/budget selection. |

Program A and B can each contain a private `helper` and a local entry named
`run`. They do not conflict merely by being packaged together. If a device
import actually crosses components, the producer must perform a real validated
ISA link, or use a future published cross-program protocol. Bare co-packaging
cannot resolve the import. Distinct selected roots may share a static callee;
each still has its own invocation binding and root-relative context `[]`.
Substituting A's certificate for B fails even when both local names are `run`.

The host sequence `A(x)`, `B(result)`, `A(result)` creates three invocation
records. Each names its owning loaded program instance and static entry/root,
resolved arguments, budget identity, run state, result/fault, journal profile
and eventual close. It does not reinitialise host libc or share one global tape
cursor across those calls. Ordinary native events remain owned by the host;
device R effects, CC replies and saved replay inputs keep their specified owners.

## Runtime ownership

Validate the selected inventory/profile and exact payload before loading it
through the published ISA launch API. Load each required linked program and
associate its runtime instance with the program id; the native ABI adapter
selects that instance and its declared CC entry. The forthcoming native-call
contract must define scalar/aggregate marshalling, return/fault propagation,
suspension, reverse eligibility, close and ordinary-pointer bindings. Integer
pointer bits alone never register an object or establish its lifetime.

Resource ids and tokens resolve in the owning loaded program. Runs retain the
specified exclusive ownership until CLOSED. Repeated calls in that program
retain identity; stale, unloaded or wrong-program use fails before a different
root executes. Communicating components may share one genuinely linked device
program. Cross-program resource transfer needs a published transfer/ledger
protocol and remains a required capability, not an implicit pointer cast.
Unload only after every run and resource meets the published release rules.

Whole-process R startup remains a separate entry profile. Callable marked
modules return to native callers and do not silently reset argv, errno, fenv,
models or invocation history. Native memory sharing needs the published
range/liveness, aliasing, synchronisation, writeback and reversal profile.
The first scalar adapter example does not replace that general obligation.

## Publication and acceptance

ISA dependencies `lop`, `8nx`, `x1y`, `ml0`, `at6` and dialect `dce` are open.
They own the outer format, selected-root proof scope, native-call/memory ABI,
ledger/run lifetime, journal association and layout profile respectively. The
driver will bind the plugin producer edge to that accepted version; it will
not canonise a private host shim while those publications are pending.

Required acceptance vectors include two programs with colliding local names;
two roots sharing one static callee with independent contexts; native-only
main/libc; tampered payload slice/digest/version; wrong root/certificate/build;
missing reachable device callee/proof/coverage; layout or signature mismatch;
stale/wrong-owner run ids; wrong-invocation replay; actual conflicting device
link; and unload with outstanding ownership. Fail before an unrelated device
effect. A future production mixed fixture must execute the native host through
the real adapter and check returns, state, faults, reversal and replay; merely
parsing this inventory or invoking an executor CLI cannot pass it.

Estimated driver work after publication: one day for the versioned inventory
adapter and integrity controls, then two to four days for packaging and the
published scalar launch/lifetime integration, with further work for general
native memory and layout profiles. These estimates defer mechanics, not scope.
