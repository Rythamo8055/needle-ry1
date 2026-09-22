use once_cell::sync::OnceCell;
use std::ffi::{CStr, CString};
use std::os::raw::{c_char, c_int};
use std::sync::Mutex;

type NeedleInitFn = unsafe extern "C" fn(*const c_char, *const c_char, *const c_char) -> c_int;
type NeedleCompleteFn = unsafe extern "C" fn(*const c_char, c_int, *mut c_char, c_int) -> c_int;
type NeedleResetFn = unsafe extern "C" fn();

struct NeedleLib {
    _lib: libloading::Library,
    init: NeedleInitFn,
    complete: NeedleCompleteFn,
    reset: NeedleResetFn,
}

static LIB: OnceCell<Mutex<NeedleLib>> = OnceCell::new();

fn lib_path() -> String {
    let candidates = [
        "src-tauri/binaries/libneedle.so",
        "binaries/libneedle.so",
        "/home/rythamo/truing stuff/ry1/src-tauri/binaries/libneedle.so",
        "/home/rythamo/.cache/cactus-needle/2.0.3/libneedle.so",
    ];
    for p in candidates {
        if std::path::Path::new(p).exists() {
            return p.to_string();
        }
    }
    let home = std::env::var("HOME").unwrap_or_else(|_| "/home/rythamo".to_string());
    format!("{}/.cache/cactus-needle/2.0.3/libneedle.so", home)
}

fn get_lib() -> Option<std::sync::MutexGuard<'static, NeedleLib>> {
    let cell = LIB.get_or_init(|| {
        let path = lib_path();
        let lib = unsafe { libloading::Library::new(&path).expect(&format!("failed to load {}", path)) };
        let (init_fn, complete_fn, reset_fn) = unsafe {
            let init: libloading::Symbol<NeedleInitFn> = lib.get(b"needle_init").unwrap();
            let complete: libloading::Symbol<NeedleCompleteFn> = lib.get(b"needle_complete").unwrap();
            let reset: libloading::Symbol<NeedleResetFn> = lib.get(b"needle_reset").unwrap();
            (*init, *complete, *reset)
        };
        Mutex::new(NeedleLib {
            _lib: lib,
            init: init_fn,
            complete: complete_fn,
            reset: reset_fn,
        })
    });
    cell.lock().ok()
}

pub fn init(tools_json: &str, tool_index_path: Option<&str>) -> bool {
    let lib = match get_lib() {
        Some(l) => l,
        None => return false,
    };
    let system = CString::new("").unwrap();
    let tools = CString::new(tools_json).unwrap();
    let index_cstr;
    let index_ptr = if let Some(p) = tool_index_path {
        index_cstr = CString::new(p).unwrap();
        index_cstr.as_ptr()
    } else {
        std::ptr::null()
    };
    let init = lib.init;
    let rc = unsafe { init(system.as_ptr(), tools.as_ptr(), index_ptr) };
    rc >= 0
}

pub fn complete(prompt: &str, max_tokens: i32) -> Option<serde_json::Value> {
    let lib = get_lib()?;
    let complete = lib.complete;
    let c_prompt = CString::new(prompt).ok()?;
    let mut buf = vec![0u8; 65536];
    let rc = unsafe {
        complete(
            c_prompt.as_ptr(),
            max_tokens,
            buf.as_mut_ptr() as *mut c_char,
            buf.len() as c_int,
        )
    };
    if rc < 0 {
        return None;
    }
    let cstr = unsafe { CStr::from_ptr(buf.as_ptr() as *const c_char) };
    let s = cstr.to_string_lossy();
    serde_json::from_str(&s).ok()
}

pub fn reset() {
    if let Some(lib) = get_lib() {
        let reset = lib.reset;
        unsafe { reset() }
    }
}
