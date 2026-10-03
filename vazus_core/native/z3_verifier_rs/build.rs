use std::path::Path;

fn main() {
    let z3_dir = Path::new(r"C:\vazus\.venv\Lib\site-packages\z3\lib");
    println!("cargo:rustc-link-search=native={}", z3_dir.display());
    println!("cargo:rustc-link-lib=z3");
    println!("cargo:rerun-if-changed=build.rs");

    // Copy libz3.dll to target deps folder so test executables can locate it
    let out_dir = std::env::var("OUT_DIR").unwrap_or_default();
    if let Some(target_dir) = Path::new(&out_dir).ancestors().nth(3) {
        let deps_dir = target_dir.join("deps");
        if deps_dir.exists() {
            let src = z3_dir.join("libz3.dll");
            let dst = deps_dir.join("libz3.dll");
            let _ = std::fs::copy(&src, &dst);
        }
    }
}

