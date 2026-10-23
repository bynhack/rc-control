//! Builds the radio receive library (Aviateur's wifi code + devourer, see
//! native/CMakeLists.txt) and links it with libusb and libsodium.

fn main() {
    println!("cargo:rerun-if-changed=native");
    println!("cargo:rerun-if-changed=third_party/aviateur/src/wifi");

    let mut cfg = cmake::Config::new("native");
    cfg.build_target("rcwfb").profile("Release");
    if cfg!(target_os = "macos") {
        cfg.define("CMAKE_OSX_DEPLOYMENT_TARGET", "13.3");
    }
    let build = cfg.build().join("build");

    println!("cargo:rustc-link-search=native={}", build.display());
    println!("cargo:rustc-link-search=native={}", build.join("devourer").display());
    println!("cargo:rustc-link-lib=static=rcwfb");
    println!("cargo:rustc-link-lib=static=devourer");
    pkg_config::probe_library("libusb-1.0").expect("libusb-1.0 not found (brew install libusb)");
    pkg_config::probe_library("libsodium").expect("libsodium not found (brew install libsodium)");

    let target = std::env::var("CARGO_CFG_TARGET_OS").unwrap_or_default();
    match target.as_str() {
        "macos" => println!("cargo:rustc-link-lib=c++"),
        "linux" => println!("cargo:rustc-link-lib=stdc++"),
        _ => {}
    }
}
