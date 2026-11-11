# bennett-driver

## What this repo is

The link-time driver: bitcode merge, LLVM optimiser and plugin invocation via external opt/lld processes (the driver itself never links LLVM), fat objects, launch, and coverage reports. Per-front-end integration notes: clang via -flto; rustc via bitcode emission; Julia via LLVM.jl.

It is one of several independent repositories in the Bennett reboot. It talks to
the others only through published specs.

## Where the spec is

Objects/linking: Bennett-ISA-Spec.md section 9 (object 0.3); launch: section 10 (launch 0.3); coverage: section 13 (coverage 0.3). The plugin is invoked as an external binary, never linked.
The conformance suites for the versions in SPEC_VERSIONS.toml live in bennett-isa-spec.
Spec sources of truth: Bennett-ISA-Spec.md and Bennett-NorthStar.md in the Bennett.jl repo
until bennett-isa-spec is published.

## Rules

The one rulebook is bennett/docs/process/COMMON.md; it binds here. Gate: `scripts/pre-push`. Tasks: `bd` (`bd prime` lists its commands).
