# R process argument inputs

`--bennett-process-arguments=FILE` supplies the process context for a reversible
entry. The driver records this input's SHA-256 in its build and manifest and
emits authenticated `ENTRY/argv-replies.json` for the executor's `--replies`
input. The compiler's own environment is separate from the requested context.

```json
{
  "schema": "bennett-driver-process-arguments-1",
  "argv": ["program", "abc", ""],
  "envp": ["VALUE=abc", "EMPTY="]
}
```

Each array preserves order and duplicate strings. A JSON string supplies UTF-8
bytes; `{"hex":"ff"}` supplies arbitrary native byte contents. Native strings
must exclude NUL; the serializer adds each terminator. `argc` is the argv count.
Both vectors are present, including when empty. Omitting the option requests
empty vectors. An explicit input may contain the calling host's actual argv and
envp bytes; the driver never serializes their native addresses.

When the published build names
`entry_initialisation.arguments = "bennett-argv-bytes-1"`, the driver follows
producer `docs/R_PROCESS_ARGUMENTS.md`: little-endian argc/reserved/envc/size,
target-pointer-width relative offsets and null sentinels, then string bytes.
It supplies the same complete payload for the initial zeroed 24-byte header
request and the second zeroed allocation request. Storage limits remain the
selected program's ordinary heap limits.

`--bennett-argv-replies=FILE` remains available for an explicit executor reply
array. Byte-import replies must match both request capacities/services, repeat
exactly the same complete payload, and contain valid lengths, offsets, strings
and sentinels. The two input options are mutually exclusive. Historical entries
without the byte-import handoff retain their `bennett.argv` header protocol;
only the requested argc is observable there when pointer arguments are unused.

These records provide process inputs to the selected ISA launch. Driver process
preparation still links the actual runtime preparation and exit bodies before
materialisation. Normal return retains exit handlers, flushing, exit status and
whole-run reversal. The static finalizer arrays belong to the actual link
context. The full-process regression has genuine empty static arrays plus a
registered atexit handler; it checks getenv and argument bytes, exit 7, exact
`abc\nbye\n` output, and restoration of the complete entry state.
