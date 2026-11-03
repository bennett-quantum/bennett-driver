# Selected-module device prologue handoff

Status: consumer requirements and a reproduced production blocker for `7y4`.
The runtime globals are published. This document adds no host launch ABI or
private plugin metadata. The semantics are dialect §§8.3, 11.3 and 16.2;
the concrete C state layout is the runtimes `device-models/README.md`.

The ten clock/entropy/block globals in the real LLVM18/23 runtime distributions
have the documented type, alignment and zero data image. That ABI audit does
not establish wrapper preparation. The wrapper is selected by a descriptor and
must initialise the corresponding model state in its oracle prefix, outside
control, before calling the selected region. Models absent from that descriptor
remain unbound; a process-wide initializer cannot supply this semantics.

| Model | Values supplied by the selected descriptor/preserved regions |
|---|---|
| Clock | `clock_bound:i32=1`, `clock_c:i64=value`; the counter advances modulo 2^64. |
| Entropy | `entropy_bound:i32=1`, `entropy_base:ptr=address(e0)`, `entropy_size:i64=2^A`, `entropy_pos:i64=0`. The input can be superposed; it is not replaced by host bytes. |
| Block | `block_bound:i32=1`, `block_base:ptr=address(k0)`, `block_nsect:i64=2^A'`, `block_overlay:ptr=null`. Overlay allocations and writes remain ordinary charged runtime state. |

Pointers and i64 fields align to eight, i32 fields to four. State and images
belong to the selected module's runtime closure and invocation construction.
The prefix must compose with entry replay, shadow-stack preparation, ordinary
live-object checks and the selected layout. Its writes and subsequent model
state reverse with that prefix, including nonzero preimages; clearing only a
length or cursor is insufficient. A repeated oracle starts from its descriptor's
private state. Action capacity/history/control rules remain separate requirements.
R effects retain the ISA tape. Ordinary H keeps host libc and host effects.

## Actual production probe

`tests/fixtures/device_clock.c` uses the published marker header and an ordinary
descriptor: `CLOCK(3)`, no parameters, an eight-wire result and four-wire fault
register. Its region reads twice, yielding 3 then 4, so the payload is 0x43.
The caller observes that payload/fault, applies the same oracle again and frees
the now-clean registers. This exposes missing binding, wrong initial value,
wrong increment, stale state between calls and incorrect private-state reset.

`tests/device_models.py` requires real production ISA, then the independent
reference's public `run-program` result 67, no faults/hostcalls/R tape and a
CLOSED run. It remains a mandatory success test, with no accepted-error branch.
The current real 0.2.13 plugin fails before model generation on both the
initial clock probe and the tracked fixture: `§8.4 scalar descriptor finite
dispatch (milestone 1)` at the actual `__bennett_oracle` call. No produced
wrapper or prologue can be audited at this frontier. Runtime-only model tests
or a driver-written constant initializer cannot replace this acceptance.

## Required producer edge

The plugin owns descriptor shape selection and the lifted wrapper body. It must
accept this static public descriptor through the production route, link the
needed ordinary model closure, and emit the normative prefix against the
published bound/state globals. If the driver must perform part of preparation,
publish the pass/input/receipt edge before implementation: selected module,
entry/root/shape, descriptor value or preserved-region mapping, exact source
global correspondence/layout, preparation ordering and provenance hash. The
driver must not edit generated ISA to insert private stores after certificates
and closure identities have been computed.

After the clock frontier, extend the same production acceptance to superposed
entropy with exhaustion preflight, immutable disk input and sparse overlay,
unbound models, controlled/action behavior and full prefix restoration. These
remain required capabilities. The small clock fixture proves none of them by
itself. No additional model tape, whole-process startup or unpublished mixed
host-memory shim is needed for this handoff.
