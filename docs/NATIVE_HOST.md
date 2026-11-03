# Ordinary native output

A build with no reserved `__bennett_` symbols in any verified source module,
and no explicit whole-process reversible entry, produces an ordinary native
host. The driver checks all source modules together; unmarked modules remain
valid inputs beside marked modules.

For the native-only case, `llvm-link` merges the verified source modules and
`opt` runs the requested post-link pipeline. Clang compiles `host.bc` using
normal host startup and libraries, with the explicit sysroot when supplied.
Device runtimes and arithmetic bitcode are outside that host closure. This
preserves native libc, argv, floating point and process return behavior.

A defined `main` produces `native-host`; a library without `main` produces
`native-host.o`. The manifest and canonical build record bind the actual output
bytes and commands. `launches.json` is empty, as are the selected device build,
layout and budget inventories. There are no device certificates for native-only
symbols. Required plugin/library identities and requested hashes are still
checked; this route does not bypass version admission.

Mixed native machine objects and marked bitcode still require the deferred
mixed host/VM link. Such inputs fail explicitly naming `bennett-4ht` and
`bennett-driver-116`, without a partial successful link. This native-only route
does not implement or certify that mixed launch boundary.

`tests/native_host.py` exercises both LLVM majors: trivial main, multi-module
stdio/argv/status behavior, a library object, empty device inventories and the
explicit mixed-link dependency. Comparison destinations also preserve recorded
artifacts from earlier build stages; `tests/output_paths.py` covers host and
linked bitcode alongside external input and output aliases.
