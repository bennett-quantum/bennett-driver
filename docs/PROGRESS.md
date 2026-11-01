# M1 implementation — 2026-11-01

Pass 1: external full-LTO pipeline, ABI plugin identity, major-matched libraries,
optional SHA pins, hashes/tool versions/commands, canonical build metadata and
certificate association. Real rung-2 hash regression on LLVM 18 and 23.
Red receipt: stub accepted wrong dialect and omitted linked.bc.
Upstream publications are mutable: integration recovers plugin-pinned arith bytes
from local git into driver .tmp, and distinguishes latest run from latest object
receipts when a prerequisite failed. No sibling code changes.

Pass 2: R-mode/entry validation and exact plugin forwarding pass on LLVM18/23.
The real plugin refuses both options; bp-xkg records the §19.2/argv and §25.1
BD-B-ISA7 dependency. No R launch or argv reply was fabricated. Slice remains
blocked until the plugin implements the entry/argv ABI and ISA-0.8 reporting.
