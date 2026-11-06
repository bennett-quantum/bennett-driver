# pin-driver review, round 1 — BLOCK

Reviewed main..job/pin-driver: b14a3152eda949a2395d352a3a731c7d471d4679..8208879ce127fe90eb1a950062c562642d9e0828, commits dd53af9, 8208879; exact implementation head **8208879ce127fe90eb1a950062c562642d9e0828**. No implementation changes.

**P0-1 — advertised sysroot environment setting silently uses host headers** — **bennett-driver-5ab**.
src/main.rs:22 advertises BENNETT_DRIVER_SYSROOT, but src/main.rs:405–407 reads only the flag and silently returns no frontend controls otherwise; the caller is src/main.rs:541. src/native_host.rs:56 and src/native.rs:474 also read only the flag. The new resolver at src/main.rs:250 never normalizes the environment setting into those consumers. A caller can configure a sysroot through the advertised environment, get a successful build against host headers, and execute a different result than with the equivalent flag. tests/toolchain.py:17–20 sets this variable without asserting that production uses it. Honor the optional setting consistently and test independently derived output; preserve ordinary native compilation when no sysroot is requested.

Ran an independent probe with timeout 60 python3 -B -: **both driver builds exited 0**, but executing probe returned **env=3, flag=0**, expected **0** for either spelling. A second probe with a sysroot-only header failed with environment configuration and passed with the flag. Reproduction (also in the bead):

    import os, pathlib, subprocess, sys, tempfile
    sys.path.insert(0, 'tests')
    from toolchain import configure
    configure(23)
    exe = pathlib.Path('.tmp/rev-pin-driver-r1/target/debug/bennett-driver').resolve()
    with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as tmp:
        d = pathlib.Path(tmp)
        sysroot = d/'sysroot'
        (sysroot/'include').mkdir(parents=True)
        (sysroot/'include/limits.h').write_text('#define INT_MAX 17\n')
        source = d/'probe.c'
        source.write_text('#include <limits.h>\nint probe(void) { return INT_MAX == 17 ? 0 : 3; }\n')
        environment = dict(os.environ, BENNETT_DRIVER_SYSROOT=str(sysroot))
        for mode in ('env', 'flag'):
            out = d/mode
            args = [str(exe), '--bennett-llvm-major=23', '--bennett-dialect=0.2.10',
                    '--bennett-out='+str(out), str(source)]
            if mode == 'flag':
                args += ['--bennett-sysroot='+str(sysroot)]
            built = subprocess.run(args, env=environment, capture_output=True, timeout=25)
            assert built.returncode == 0, built.stderr
            result = subprocess.run(['/usr/lib/llvm-23/bin/lli', '--entry-function=probe',
                                     str(out/'host.bc')], capture_output=True, timeout=10)
            print(mode, result.returncode)

Verification: from this worktree, DISPLAY/WAYLAND_DISPLAY/DBUS_SESSION_BUS_ADDRESS/BROWSER unset, TMPDIR=$PWD/.tmp/rev-pin-driver-r1/tmp, CARGO_TARGET_DIR=$PWD/.tmp/rev-pin-driver-r1/target:

- timeout 240 cargo test --offline -j3 --test pin_discipline --bin bennett-driver -- --nocapture --test-threads=4 — PASS: six unit tests and the pin wrapper's ten Python cases.
- timeout 240 cargo test --offline -j3 --test dialect_profile --test preparation --test closed_unit --test native_materialisation --test comparison --test classifier --test environment --test pipeline --test hook -- --nocapture --test-threads=4 — PASS: ten tests, one explicitly ignored publication test.
- timeout 240 cargo test --offline -j3 --test process --test process_runtime_apis --test reversible -- --nocapture --test-threads=4 — PASS: three tests, including the changed exact heap-layout fixtures.
- Explicit timeout 120 cargo test --offline -j3 ... -- --ignored --nocapture --test-threads=4 runs: --test classes --test device_models --test pipeline stopped at classes' expected configured-register-class failure; separate --test device_models failed on scalar descriptor dispatch and --test pipeline failed on the missing pinned publication. All exit 101. Named ignores/reports retain bead references and full capability assertions; no narrowing found.
- Read main-side fallback code using git show: the missing-path/TMPDIR regressions would reject main's implicit defaults; head tests pass. No branch switch or baseline execution was performed.
- Plugin public-ABI queries show 0ac6180 advertises dialect 0.2.10 and 5a092cd advertises 0.2.13. A temporary copied fixture layout repinned to 0ac6180, run with timeout 90 python3 -B -, fails dialect_profile.py with the expected BD-E-VERSION; the head pin passes. The repin is needed for the existing modern-profile tests. 5a092cd is absent from cached origin/main (present on remote wip refs); the note honestly leaves producer publication pending. Dialect e0456ee and interpreter 8d9a5c6 are on cached origin/main; all three resolver HEAD checks pass, and the dialect header blob matches de5f939 exactly.

P2+ nits — **bennett-driver-9hd**: README.md:113–124 describes removed artifact overrides/default rung-2 execution; Round-1 baseline/ratchet and HANDOFF retirement remain pending (gate.toml:10, HANDOFF.md:3, README.md:130, tracked docs/PROGRESS.md; this is R0.2); tests/integration.py:31 retains a bead id in emitted fixture-error text rather than only the named switch/report.

Coverage: read closely every changed hunk across all 45 files, resolver/fixture isolation, path consumers, promised assertions, pin metadata, laws and main-side fallback code; skimmed surrounding unchanged execution/link/report code. Checked every COMMON anti-slop rule: the sysroot silent default is the blocking semantics issue; test-only identifier/stale-context issues are nits; no new dispatch chains, flag state, repeated compound predicates, unexplained numeric policy, trivial wrappers or tracked scratch litter found. Existing long execute/compare functions and Round-1 housekeeping remain later quality-driver work. No full repository gate or sibling gate run.

Provenance: implementer gpt-6.1-sol; reviewer gpt-6.1-sol, fresh session, D9.
