# Process preparation ownership

The Rust driver does not link LLVM. It launches stock LLVM tools, the Bennett
plugin and a driver-owned external synthesis tool. `src/process-entry.cpp`
builds that last tool against the selected major's public LLVM libraries;
its source/hash, binary/hash, compiler command and resulting bitcode are retained
in the preparation receipt. This is an additional LLVM-linked utility, so
“only the plugin links LLVM” would be an inaccurate description of this build.

The utility owns only the explicit whole-process R adapter required by dialect
§19.2: validate the C process signature and vectors, call the published
`__bennett_rt_prepare_process` helper, retain its public process aliases and
route normal C return through the published `exit` path. It writes ordinary
LLVM bitcode before post-link analysis. It performs no Bennett recognition,
points-to analysis, materialisation, ISA construction, certificate generation
or runtime model execution. Those remain with the plugin/runtime/executors.

This is an implementation inside the driver repository, using LLVM's public
API and the published runtime helper ABI. It is not another repository's code
or an unpublished plugin handshake. Its private wrapper attribute is used
only by the driver's own definition audit. A future published plugin preparation
pass can replace this utility through an explicit tool/receipt migration;
removing working preparation before that edge exists would lose the current
whole-process component behavior.

The adapter runs only for a requested reversible process entry. An ordinary
native host and callable marked modules do not acquire a C-main signature,
argv reset, libc reinitialization or per-call process exit. The future mixed
callable adapter needs its separately published entry/lifetime contract.
