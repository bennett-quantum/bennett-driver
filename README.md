# bennett-driver

The link-time driver: bitcode merge, LLVM optimiser and plugin invocation via external opt/lld processes (the driver itself never links LLVM), fat objects, launch, and coverage reports. Per-front-end integration notes: clang via -flto; rustc via bitcode emission; Julia via LLVM.jl.

Depends (by published spec, not by shared code) on: bennett-plugin (binary), bennett-isa-spec, bennett-dialect-spec.

Part of the Bennett reboot workspace. Status: skeleton; see HANDOFF.md.
