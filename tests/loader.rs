//! Independent C providers implement only the published ISA 0.9 ABI.
use bennett_driver::launch::{DeviceRoot, LaunchShim, Provider, Role};
use std::{
    ffi::CString,
    fs,
    path::PathBuf,
    process::Command,
    sync::atomic::{AtomicUsize, Ordering},
};

static SERIAL: AtomicUsize = AtomicUsize::new(0);
struct Fixture {
    path: PathBuf,
}
impl Fixture {
    fn new(manifest: &[u8], query_status: i32, exports: &str) -> Self {
        let path = PathBuf::from(std::env::var_os("TMPDIR").unwrap()).join(format!(
            "loader-{}-{}",
            std::process::id(),
            SERIAL.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir(&path).unwrap();
        let bytes = manifest
            .iter()
            .copied()
            .chain(std::iter::once(0))
            .map(|b| b.to_string())
            .collect::<Vec<_>>()
            .join(",");
        let source = include_str!("fixtures/loader-provider.c")
            .replace("MANIFEST_BYTES", &bytes)
            .replace("QUERY_STATUS", &query_status.to_string());
        fs::write(path.join("provider.c"), source).unwrap();
        let output = Command::new("cc")
            .args([
                "-std=c11", "-shared", "-fPIC", "-Wall", "-Wextra", "-Werror",
            ])
            .args(exports.split(',').map(|name| format!("-DEXPORT_{name}")))
            .arg(path.join("provider.c"))
            .arg("-o")
            .arg(path.join("provider.so"))
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "{}",
            String::from_utf8_lossy(&output.stderr)
        );
        Self { path }
    }
    fn open(&self) -> Provider {
        // SAFETY: our independently compiled provider obeys the published C layouts.
        unsafe { Provider::open(&self.path.join("provider.so")) }.unwrap()
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        fs::remove_dir_all(&self.path).unwrap();
    }
}
const LAUNCH: &[u8] =
    br#"{"abi":"launch/0.9","features":["token_aliases/1"],"schema":"bennett.abi-features/1"}"#;
fn root(name: &str) -> DeviceRoot {
    DeviceRoot {
        name: name.into(),
        object: format!("object:{name}").into_bytes(),
        region: CString::new(name).unwrap(),
    }
}
#[test]
fn startup_dispatch_preserves_each_root_and_all_five_partitions() {
    let fixture = Fixture::new(LAUNCH, 0, "ALL");
    let provider = fixture.open();
    let left = LaunchShim::load(&provider, &root("left"), b"target").unwrap();
    let right = LaunchShim::load(&provider, &root("right"), b"target").unwrap();
    let token = left.budget([7, 8, 9, 10]).unwrap();
    let fresh = left.budget([7, 8, 9, 10]).unwrap();
    assert_ne!(token.raw(), fresh.raw());
    let other = right.budget([7, 8, 9, 10]).unwrap();
    for aliases in ["[0,0,0]", "[0,0,1]", "[0,1,0]", "[0,1,1]", "[0,1,2]"] {
        let mut partition = aliases.as_bytes().to_vec();
        let estimate = left
            .estimate(
                &token,
                c"forward",
                3,
                b"[[7,8,9,10],[7,8,9,10]]",
                &partition,
            )
            .unwrap();
        partition.fill(b'x');
        assert_eq!(
            estimate.certificate(),
            format!("left|{}|3|[[7,8,9,10],[7,8,9,10]]|{aliases}", token.raw()).as_bytes()
        );
        // A returned estimate keeps its copied binding even across later calls.
        let next = right
            .estimate(&other, c"forward", 3, b"[]", b"[0]")
            .unwrap();
        assert_eq!(
            next.certificate(),
            format!("right|{}|3|[]|[0]", other.raw()).as_bytes()
        );
        assert!(estimate.certificate().ends_with(aliases.as_bytes()));
    }
    assert_eq!(
        right
            .estimate(&token, c"forward", 0, b"[]", b"[0]")
            .err()
            .unwrap()
            .status,
        11
    );
}
#[test]
fn startup_fails_loud_before_load_or_request_without_erasing_input() {
    for exports in ["NO_QUERY", "NO_ALIAS"] {
        let fixture = Fixture::new(LAUNCH, 0, exports);
        let provider = fixture.open();
        let error = LaunchShim::load(&provider, &root("marked/root"), b"target")
            .err()
            .unwrap();
        assert_eq!(error.status, 1);
        assert!(error.to_string().contains("marked/root"));
        assert!(error.to_string().contains("token_aliases/1"));
        assert!(error.to_string().contains("deployment"));
    }
}
#[test]
fn manifest_matrix_rejects_malformed_and_incompatible_providers() {
    let malformed: &[&[u8]] = &[
        br#"{"abi":"launch/0.9","features":[],"schema":"bennett.abi-features/1"}"#,
        br#"{"abi":"launch/0.9","features":["token_aliases/2"],"schema":"bennett.abi-features/1"}"#,
        br#"{"abi":"launch/0.8","features":["token_aliases/1"],"schema":"bennett.abi-features/1"}"#,
        br#"{"abi":"sched/0.9","features":["token_aliases/1"],"schema":"bennett.abi-features/1"}"#,
        br#"{"abi":"launch/0.9","features":["token_aliases/1"],"schema":"bennett.abi-features/2"}"#,
        br#"{"abi":"launch/0.9","features":["token_aliases/1","token_aliases/1"],"schema":"bennett.abi-features/1"}"#,
        br#"{"abi":"launch/0.9","features":["z/1","token_aliases/1"],"schema":"bennett.abi-features/1"}"#,
        br#"{"abi":"launch/0.9","features":[""],"schema":"bennett.abi-features/1"}"#,
        br#"{"abi":"launch/0.9","features":["\u00e9","token_aliases/1"],"schema":"bennett.abi-features/1"}"#,
        br#"{"abi":"launch/0.9","features":["token_aliases/1"],"schema":"bennett.abi-features/1","extra":0}"#,
        br#"{"abi":"launch/0.9","features":["token_aliases/1"],"schema":"bennett.abi-features/1","schema":"bennett.abi-features/1"}"#,
        br#"{"features":["token_aliases/1"],"schema":"bennett.abi-features/1"}"#,
        br#"{"abi":"launch/0.9","features":"token_aliases/1","schema":"bennett.abi-features/1"}"#,
        br#"{"abi":9,"features":["token_aliases/1"],"schema":"bennett.abi-features/1"}"#,
        br#" {"abi":"launch/0.9","features":["token_aliases/1"],"schema":"bennett.abi-features/1"}"#,
        br#"{"schema":"bennett.abi-features/1","features":["token_aliases/1"],"abi":"launch/0.9"}"#,
        br#"{"abi":"launch/0.9","features":["token_aliases\/1"],"schema":"bennett.abi-features/1"}"#,
        b"\xff", b"{}", b"null", b"",
    ];
    for manifest in malformed {
        let fixture = Fixture::new(manifest, 0, "NO_EFFECTS");
        let provider = fixture.open();
        let request = root("rejected-deployment");
        let saved = request.object.clone();
        let error = LaunchShim::load(&provider, &request, b"target")
            .err()
            .unwrap();
        assert_eq!(error.status, 1, "{manifest:?}: {error}");
        assert_eq!(request.object, saved);
    }
}
#[test]
fn query_status_propagates_and_roles_negotiate_independently() {
    let failed = Fixture::new(LAUNCH, 6, "NO_EFFECTS");
    assert_eq!(
        failed
            .open()
            .negotiate("failing/root", Role::Launch)
            .err()
            .unwrap()
            .status,
        6
    );
    let launch = Fixture::new(LAUNCH, 0, "ALL");
    let provider = launch.open();
    provider.negotiate("a", Role::Launch).unwrap();
    assert_eq!(
        provider.negotiate("b", Role::Sched).err().unwrap().status,
        1
    );
    let sched = Fixture::new(
        br#"{"abi":"sched/0.9","features":["token_aliases/1"],"schema":"bennett.abi-features/1"}"#,
        0,
        "SCHED",
    );
    let scheduler = sched.open();
    scheduler.negotiate("b", Role::Sched).unwrap();
    assert_eq!(
        scheduler.negotiate("a", Role::Launch).err().unwrap().status,
        1
    );
}
#[test]
fn unknown_features_and_reloaded_providers_do_not_share_advertisements() {
    let good = Fixture::new(br#"{"abi":"launch/0.9","features":["a/1","token_aliases/1","z/1"],"schema":"bennett.abi-features/1"}"#, 0, "ALL");
    for _ in 0..3 {
        good.open().negotiate("root", Role::Launch).unwrap();
    }
    let absent = Fixture::new(
        br#"{"abi":"launch/0.9","features":[],"schema":"bennett.abi-features/1"}"#,
        0,
        "NO_EFFECTS",
    );
    assert_eq!(
        absent
            .open()
            .negotiate("root", Role::Launch)
            .err()
            .unwrap()
            .status,
        1
    );
}
#[test]
fn provider_argument_errors_remain_distinct_and_estimates_are_not_retried() {
    let fixture = Fixture::new(LAUNCH, 0, "ALL");
    let provider = fixture.open();
    let shim = LaunchShim::load(&provider, &root("errors"), b"target").unwrap();
    let token = shim.budget([7, 8, 9, 10]).unwrap();
    for invalid in ["[1,1]", "[0,2]", "[-1]", "[0,0,0,0]"] {
        assert_eq!(
            shim.estimate(&token, c"forward", 0, b"[]", invalid.as_bytes())
                .err()
                .unwrap()
                .status,
            11
        );
    }
}

#[test]
fn native_binding_forwards_live_program_and_device_minted_handles() {
    let fixture = Fixture::new(LAUNCH, 0, "ALL");
    let provider = fixture.open();
    let selected = root("native-boundary");
    let shim = LaunchShim::load(&provider, &selected, b"target").unwrap();
    // A native startup adapter receives this root's actual program; it must
    // retain its own runtime-layout/run lifetime obligations.
    let token = unsafe {
        shim.with_native_program(|program| {
            assert!(!program.is_null());
            let mint: unsafe extern "C" fn(*mut std::ffi::c_void) -> u64 =
                fixture_entry(&fixture, c"fixture_mint");
            mint(program)
        })
    };
    let live = unsafe { shim.token_from_native(token) };
    let estimate = shim.estimate(&live, c"forward", 0, b"[]", b"[0]").unwrap();
    assert!(estimate.certificate().starts_with(b"native-boundary|"));
    unsafe {
        shim.with_native_program(|program| {
            let reverse: unsafe extern "C" fn(*mut std::ffi::c_void, u64) =
                fixture_entry(&fixture, c"fixture_reverse");
            reverse(program, token);
        })
    };
    assert_eq!(
        shim.estimate(&live, c"forward", 0, b"[]", b"[0]")
            .err()
            .unwrap()
            .status,
        11
    );
    assert!(estimate.certificate().ends_with(b"|[0]"));
}
// Independent observer of the fixture, kept loaded by Provider for this scope.
unsafe fn fixture_entry<T: Copy>(fixture: &Fixture, name: &std::ffi::CStr) -> T {
    unsafe extern "C" {
        fn dlopen(path: *const i8, flags: i32) -> *mut std::ffi::c_void;
        fn dlsym(handle: *mut std::ffi::c_void, name: *const i8) -> *mut std::ffi::c_void;
        fn dlclose(handle: *mut std::ffi::c_void) -> i32;
    }
    let path = CString::new(fixture.path.join("provider.so").to_str().unwrap()).unwrap();
    let library = unsafe { dlopen(path.as_ptr(), 2) };
    assert!(!library.is_null());
    let symbol = unsafe { dlsym(library, name.as_ptr()) };
    assert!(!symbol.is_null());
    assert_eq!(unsafe { dlclose(library) }, 0);
    assert_eq!(std::mem::size_of::<T>(), std::mem::size_of_val(&symbol));
    unsafe { std::mem::transmute_copy(&symbol) }
}

#[test]
fn distinct_root_providers_cannot_borrow_each_others_features_or_symbols() {
    let good = Fixture::new(LAUNCH, 0, "ALL");
    let first = good.open();
    let first_root = root("supported");
    let running = LaunchShim::load(&first, &first_root, b"target").unwrap();
    let absent = Fixture::new(LAUNCH, 0, "NO_QUERY");
    let second = absent.open();
    let unresolved = root("unsupported");
    let error = LaunchShim::load(&second, &unresolved, b"target")
        .err()
        .unwrap();
    assert_eq!(error.status, 1);
    assert_eq!(error.root, "unsupported");
    assert_eq!(unresolved.object, b"object:unsupported");
    let token = running.budget([7, 8, 9, 10]).unwrap();
    assert!(
        running
            .estimate(&token, c"forward", 0, b"[]", b"[0]")
            .unwrap()
            .certificate()
            .starts_with(b"supported|")
    );
}

#[test]
fn each_roles_required_exports_are_checked_by_negotiation() {
    let manifest =
        br#"{"abi":"sched/0.9","features":["token_aliases/1"],"schema":"bennett.abi-features/1"}"#;
    for exports in ["SCHED,NO_ALIAS", "SCHED,NO_SCHEDULE"] {
        let fixture = Fixture::new(manifest, 0, exports);
        assert_eq!(
            fixture
                .open()
                .negotiate("scheduler/root", Role::Sched)
                .err()
                .unwrap()
                .status,
            1
        );
    }
    let fixture = Fixture::new(LAUNCH, 0, "NO_ALIAS");
    assert_eq!(
        fixture
            .open()
            .negotiate("launch/root", Role::Launch)
            .err()
            .unwrap()
            .status,
        1
    );
}

#[test]
fn driver_startup_command_dispatches_two_selected_roots_and_reports_a_gap() {
    let fixture = Fixture::new(LAUNCH, 0, "ALL");
    let mut command = Command::new(env!("CARGO_BIN_EXE_bennett-driver"));
    command.arg("--launch-estimate");
    for name in ["first", "second"] {
        if name == "second" {
            command.arg("--next-root");
        }
        let object = fixture.path.join(format!("{name}.object"));
        let certificate = fixture.path.join(format!("{name}.certificate"));
        fs::write(&object, format!("object:{name}")).unwrap();
        for (key, value) in [
            ("object", object),
            ("provider", fixture.path.join("provider.so")),
            ("certificate", certificate),
        ] {
            command.arg(format!("--{key}={}", value.display()));
        }
        for (key, value) in [
            ("root", name),
            ("region", name),
            ("budget", "7,8,9,10"),
            ("variant", "forward"),
            ("controls", "3"),
        ] {
            command.arg(format!("--{key}={value}"));
        }
        for (key, bytes) in [
            ("target", "target"),
            ("params", "[]"),
            ("aliases", "[0,1,0]"),
        ] {
            let path = fixture.path.join(key);
            fs::write(&path, bytes).unwrap();
            command.arg(format!("--{key}={}", path.display()));
        }
    }
    let output = command.output().unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    for name in ["first", "second"] {
        assert_eq!(
            fs::read(fixture.path.join(format!("{name}.certificate"))).unwrap(),
            format!("{name}|1|3|[]|[0,1,0]").as_bytes()
        );
    }
    let incompatible = Fixture::new(LAUNCH, 0, "NO_QUERY");
    let args = command
        .get_args()
        .map(|s| s.to_string_lossy().into_owned())
        .take_while(|s| s != "--next-root")
        .map(|s| {
            if s.starts_with("--provider=") {
                format!(
                    "--provider={}",
                    incompatible.path.join("provider.so").display()
                )
            } else {
                s
            }
        })
        .collect::<Vec<_>>();
    fs::remove_file(fixture.path.join("first.certificate")).unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_bennett-driver"))
        .args(args)
        .output()
        .unwrap();
    assert!(!output.status.success());
    let diagnostic = String::from_utf8_lossy(&output.stderr);
    assert!(
        diagnostic.contains("first")
            && diagnostic.contains("token_aliases/1")
            && diagnostic.contains("deployment"),
        "{diagnostic}"
    );
    assert!(!fixture.path.join("first.certificate").exists());
    assert_eq!(fs::read(fixture.path.join("aliases")).unwrap(), b"[0,1,0]");
}

#[test]
fn repeated_and_concurrent_queries_copy_exact_jcs_bytes() {
    // Canonical control escapes are valid ASCII feature identifiers too.
    let manifest=br#"{"abi":"launch/0.9","features":["\u0000","\b","\f","token_aliases/1"],"schema":"bennett.abi-features/1"}"#;
    let fixture = Fixture::new(manifest, 0, "ALL");
    std::thread::scope(|scope| {
        for _ in 0..4 {
            let path = fixture.path.join("provider.so");
            scope.spawn(move || {
                let provider = unsafe { Provider::open(&path) }.unwrap();
                for _ in 0..3 {
                    assert_eq!(
                        provider
                            .negotiate("queries", Role::Launch)
                            .unwrap()
                            .manifest,
                        manifest
                    );
                }
            });
        }
    });
    let advertisement = fixture.open().negotiate("queries", Role::Launch).unwrap();
    assert_eq!(advertisement.manifest, manifest);
}
