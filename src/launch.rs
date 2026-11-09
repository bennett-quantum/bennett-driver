//! Alias-aware native startup/shim for selected device roots (ISA 0.9 §10.1).
//!
//! A host supplies each marked ISA payload and its selected region separately.
//! `LaunchShim::load` negotiates against the selected provider before loading
//! that payload. Requests and errors borrow caller buffers; no failure erases
//! them or retries a legacy entry point. The provider owns semantic validation
//! of partitions and exact estimation. No native layout revision grants support.
//!
//! The general mixed-container, native-memory and tape/run ABI remains the
//! separate §12.3 boundary obligation. This shim neither serializes host handles
//! nor assigns device alias entries to native main, argv/envp or host libc.
mod manifest;
mod provider;
pub use provider::Provider;
use std::{
    ffi::{CStr, CString, c_void},
    fmt,
    ptr::NonNull,
};
type Result<T> = std::result::Result<T, Error>;
#[derive(Debug)]
pub struct Error {
    pub status: i32,
    pub root: String,
    detail: String,
}
impl Error {
    fn new(status: i32, root: &str, detail: impl Into<String>) -> Self {
        Self {
            status,
            root: root.into(),
            detail: detail.into(),
        }
    }
}
impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "device root {:?}: token_aliases/1 {} (status {}): {}",
            self.root,
            if self.status == 1 {
                "deployment incompatibility; conforming provider required, unresolved request retained"
            } else {
                "provider/request failure"
            },
            self.status,
            self.detail
        )
    }
}
impl std::error::Error for Error {}
#[derive(Clone, Copy, Debug)]
pub enum Role {
    Launch,
    Sched,
}
impl Role {
    fn abi(self) -> &'static str {
        match self {
            Self::Launch => "launch/0.9",
            Self::Sched => "sched/0.9",
        }
    }
    fn query(self) -> &'static CStr {
        match self {
            Self::Launch => c"bennett_launch_features",
            Self::Sched => c"bennett_sched_features",
        }
    }
    fn required(self) -> &'static [&'static CStr] {
        match self {
            Self::Launch => &[c"bennett_estimate_run_with_token_aliases"],
            Self::Sched => &[
                c"bennett_sched_request_set_token_aliases",
                c"bennett_sched_schedule",
            ],
        }
    }
}
/// Deployment evidence only: never insert it into ISA artifacts or their hashes.
pub struct Advertisement {
    pub role: Role,
    pub manifest: Vec<u8>,
}
#[derive(Clone)]
pub struct DeviceRoot {
    pub name: String,
    pub object: Vec<u8>,
    pub region: CString,
}
type Load = unsafe extern "C" fn(*const u8, usize, *const u8, usize, *mut *mut c_void) -> i32;
type Unload = unsafe extern "C" fn(*mut c_void) -> i32;
type Budget = unsafe extern "C" fn(*mut c_void, *const i8, u64, u64, u64, u64, *mut u64) -> i32;
type EstimateCall = unsafe extern "C" fn(
    *mut c_void,
    *const i8,
    u64,
    *const i8,
    u32,
    *const u8,
    usize,
    *const u8,
    usize,
    *mut *mut c_void,
) -> i32;
type Certificate = unsafe extern "C" fn(*const c_void, *mut usize) -> *const u8;
type Free = unsafe extern "C" fn(*mut c_void);
struct Api {
    unload: Unload,
    budget: Budget,
    estimate: EstimateCall,
    certificate: Certificate,
    free: Free,
}
/// Lifetime examples are compile failures: provider code cannot unload while a
/// selected root uses it, and a program cannot unload while an estimate borrows it.
///
/// ```compile_fail
/// use bennett_driver::launch::{Provider, DeviceRoot, LaunchShim};
/// let provider = unsafe { Provider::open(std::path::Path::new("provider.so")) }.unwrap();
/// let root = DeviceRoot { name: "marked".into(), object: vec![], region: c"marked".into() };
/// let shim = LaunchShim::load(&provider, &root, b"{}").unwrap();
/// drop(provider);
/// let token = shim.budget([7,8,9,10]).unwrap();
/// ```
///
/// ```compile_fail
/// use bennett_driver::launch::{Provider, DeviceRoot, LaunchShim};
/// let provider = unsafe { Provider::open(std::path::Path::new("provider.so")) }.unwrap();
/// let root = DeviceRoot { name: "marked".into(), object: vec![], region: c"marked".into() };
/// let shim = LaunchShim::load(&provider, &root, b"{}").unwrap();
/// let token = shim.budget([7,8,9,10]).unwrap();
/// let estimate = shim.estimate(&token, c"forward", 0, b"[]", b"[0]").unwrap();
/// drop(shim);
/// assert!(!estimate.certificate().is_empty());
/// ```
///
/// One live selected device program. Multiple shims may use the same provider.
pub struct LaunchShim<'p> {
    _provider: &'p Provider,
    root: DeviceRoot,
    program: NonNull<c_void>,
    api: Api,
    advertisement: Advertisement,
}
/// A program-scoped host budget handle, never interned by its tuple.
pub struct Token<'s> {
    shim: &'s LaunchShim<'s>,
    raw: u64,
}
impl Token<'_> {
    pub fn raw(&self) -> u64 {
        self.raw
    }
}
pub struct Estimate<'s> {
    shim: &'s LaunchShim<'s>,
    handle: NonNull<c_void>,
}
impl<'p> LaunchShim<'p> {
    pub fn load(provider: &'p Provider, root: &DeviceRoot, target: &[u8]) -> Result<Self> {
        let advertisement = provider.negotiate(&root.name, Role::Launch)?;
        // Resolve every function used here before creating provider state.
        let (load, api): (Load, Api) = unsafe {
            (
                provider.function(&root.name, c"bennett_load")?,
                Api {
                    unload: provider.function(&root.name, c"bennett_unload")?,
                    budget: provider.function(&root.name, c"bennett_budget")?,
                    estimate: provider
                        .function(&root.name, c"bennett_estimate_run_with_token_aliases")?,
                    certificate: provider.function(&root.name, c"bennett_estimate_certificate")?,
                    free: provider.function(&root.name, c"bennett_estimate_free")?,
                },
            )
        };
        let mut program = std::ptr::null_mut();
        let status = unsafe {
            load(
                root.object.as_ptr(),
                root.object.len(),
                target.as_ptr(),
                target.len(),
                &mut program,
            )
        };
        check(status, &root.name, "bennett_load")?;
        let program = NonNull::new(program)
            .ok_or_else(|| Error::new(1, &root.name, "load returned NULL program"))?;
        Ok(Self {
            _provider: provider,
            root: root.clone(),
            program,
            api,
            advertisement,
        })
    }
    /// Pass this root's live program through a native startup binding.
    ///
    /// # Safety
    /// The adapter must use this provider's ABI and respect §10 program/run and
    /// §12.3 native-layout ownership. It must not unload the program, free shim
    /// objects, or retain the pointer beyond this shim's lifetime. This is not
    /// a general host-memory-by-reference interface.
    pub unsafe fn with_native_program<T>(&self, bind: impl FnOnce(*mut c_void) -> T) -> T {
        bind(self.program.as_ptr())
    }
    /// Retain an existing handle unchanged, including a live device-minted one.
    /// The provider revalidates liveness at every operation; reversal/close may
    /// revoke the token, but cannot retarget a returned estimate.
    ///
    /// # Safety
    /// `raw` must have originated from this loaded program through its actual
    /// launch/runtime ABI. A tuple, integer cast or another root's handle is
    /// never a substitute for that association.
    pub unsafe fn token_from_native(&self, raw: u64) -> Token<'_> {
        Token { shim: self, raw }
    }
    pub fn root(&self) -> &DeviceRoot {
        &self.root
    }
    pub fn advertisement(&self) -> &Advertisement {
        &self.advertisement
    }
    pub fn budget(&self, tuple: [u64; 4]) -> Result<Token<'_>> {
        let mut raw = 0;
        let [steps, heap, stack, depth] = tuple;
        let status = unsafe {
            (self.api.budget)(
                self.program.as_ptr(),
                self.root.region.as_ptr(),
                steps,
                heap,
                stack,
                depth,
                &mut raw,
            )
        };
        check(status, &self.root.name, "bennett_budget")?;
        Ok(Token { shim: self, raw })
    }
    pub fn estimate(
        &self,
        token: &Token<'_>,
        variant: &CStr,
        controls: u32,
        params: &[u8],
        aliases: &[u8],
    ) -> Result<Estimate<'_>> {
        if !std::ptr::eq(self, token.shim) {
            return Err(Error::new(
                11,
                &self.root.name,
                "token belongs to another loaded device root",
            ));
        }
        let mut estimate = std::ptr::null_mut();
        let status = unsafe {
            (self.api.estimate)(
                self.program.as_ptr(),
                self.root.region.as_ptr(),
                token.raw,
                variant.as_ptr(),
                controls,
                params.as_ptr(),
                params.len(),
                aliases.as_ptr(),
                aliases.len(),
                &mut estimate,
            )
        };
        check(
            status,
            &self.root.name,
            "bennett_estimate_run_with_token_aliases",
        )?;
        let handle = NonNull::new(estimate)
            .ok_or_else(|| Error::new(1, &self.root.name, "estimate returned NULL"))?;
        Ok(Estimate { shim: self, handle })
    }
}
fn check(status: i32, root: &str, operation: &str) -> Result<()> {
    if status != 0 {
        return Err(Error::new(status, root, operation));
    }
    Ok(())
}
impl Drop for LaunchShim<'_> {
    fn drop(&mut self) {
        assert_eq!(
            unsafe { (self.api.unload)(self.program.as_ptr()) },
            0,
            "device root {} unload failed",
            self.root.name
        );
    }
}
impl Estimate<'_> {
    /// Opaque K91 bytes. This is transport, not an independent certificate check.
    /// A checker must validate §12.3 bindings itself; advertisements do not attest it.
    pub fn certificate(&self) -> &[u8] {
        let mut length = 0;
        let pointer = unsafe { (self.shim.api.certificate)(self.handle.as_ptr(), &mut length) };
        assert!(
            !pointer.is_null(),
            "device root {} returned NULL certificate",
            self.shim.root.name
        );
        unsafe { std::slice::from_raw_parts(pointer, length) }
    }
}
impl Drop for Estimate<'_> {
    fn drop(&mut self) {
        unsafe { (self.shim.api.free)(self.handle.as_ptr()) };
    }
}
