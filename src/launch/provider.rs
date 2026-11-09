use super::{Advertisement, Error, Result, Role};
use std::{
    ffi::{CStr, CString, c_char, c_int, c_void},
    marker::PhantomData,
    os::unix::ffi::OsStrExt,
    path::Path,
    ptr::NonNull,
};

#[link(name = "dl")]
unsafe extern "C" {
    fn dlopen(path: *const c_char, flags: c_int) -> *mut c_void;
    fn dlsym(handle: *mut c_void, name: *const c_char) -> *mut c_void;
    fn dlclose(handle: *mut c_void) -> c_int;
    fn dlerror() -> *const c_char;
}
const RTLD_NOW: c_int = 2;
type Query = unsafe extern "C" fn(*mut *const u8, *mut usize) -> c_int;

/// A selected native provider. Borrowing by shims prevents unload while its
/// code, manifests, programs or estimates are in use. No global loader cache.
pub struct Provider {
    handle: NonNull<c_void>,
    path: String,
    // The ABI does not pledge arbitrary program operations are thread safe.
    _local: PhantomData<*mut ()>,
}
impl Provider {
    /// Load provider code in the host process, with local symbol visibility.
    ///
    /// # Safety
    /// The library and its dependencies must obey the published C ABI, pointer
    /// ownership and query contracts. Loading native code is a trust boundary;
    /// negotiation checks compatibility, not the safety of arbitrary code.
    pub unsafe fn open(path: &Path) -> Result<Self> {
        let filename = CString::new(path.as_os_str().as_bytes())
            .map_err(|e| Error::new(11, "provider", e.to_string()))?;
        let handle =
            NonNull::new(unsafe { dlopen(filename.as_ptr(), RTLD_NOW) }).ok_or_else(|| {
                let message = unsafe { dlerror() };
                let reason = if message.is_null() {
                    "dlopen returned NULL".into()
                } else {
                    unsafe { CStr::from_ptr(message) }
                        .to_string_lossy()
                        .into_owned()
                };
                Error::new(1, &path.display().to_string(), reason)
            })?;
        Ok(Self {
            handle,
            path: path.display().to_string(),
            _local: PhantomData,
        })
    }
    pub fn negotiate(&self, root: &str, role: Role) -> Result<Advertisement> {
        // All symbols are resolved on this handle; neither a different role nor
        // another selected root's provider can supply an advertisement.
        let query: Query = unsafe { self.function(root, role.query())? };
        let mut pointer = std::ptr::null();
        let mut length = 0;
        let status = unsafe { query(&mut pointer, &mut length) };
        if status != 0 {
            return Err(Error::new(
                status,
                root,
                format!("{} query failed in {}", role.abi(), self.path),
            ));
        }
        if pointer.is_null() {
            return Err(Error::new(1, root, "successful query returned NULL"));
        }
        let bytes = unsafe { std::slice::from_raw_parts(pointer, length) };
        super::manifest::validate(bytes, role.abi()).map_err(|e| Error::new(1, root, e))?;
        for symbol in role.required() {
            self.symbol(root, symbol)?;
        }
        Ok(Advertisement {
            role,
            manifest: bytes.to_vec(),
        })
    }
    fn symbol(&self, root: &str, name: &CStr) -> Result<NonNull<c_void>> {
        NonNull::new(unsafe { dlsym(self.handle.as_ptr(), name.as_ptr()) }).ok_or_else(|| {
            Error::new(
                1,
                root,
                format!("{} missing {}", self.path, name.to_string_lossy()),
            )
        })
    }
    // Private callers select the exact published function type for each symbol.
    pub(super) unsafe fn function<T: Copy>(&self, root: &str, name: &CStr) -> Result<T> {
        let pointer = self.symbol(root, name)?.as_ptr();
        assert_eq!(std::mem::size_of::<T>(), std::mem::size_of_val(&pointer));
        Ok(unsafe { std::mem::transmute_copy(&pointer) })
    }
}
impl Drop for Provider {
    fn drop(&mut self) {
        assert_eq!(
            unsafe { dlclose(self.handle.as_ptr()) },
            0,
            "provider unload failed: {}",
            self.path
        );
    }
}
