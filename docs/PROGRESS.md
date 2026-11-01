# M1 implementation — 2026-11-01

Pass 1: external full-LTO pipeline, ABI plugin identity, major-matched libraries,
optional SHA pins, hashes/tool versions/commands, canonical build metadata and
certificate association. Real rung-2 hash regression on LLVM 18 and 23.
Red receipt: stub accepted wrong dialect and omitted linked.bc.
Upstream publications are mutable: integration recovers plugin-pinned arith bytes
from local git into driver .tmp, and distinguishes latest run from latest object
receipts when a prerequisite failed. No sibling code changes.
