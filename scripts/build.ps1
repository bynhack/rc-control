# Windows 构建脚本（MSYS2 UCRT64 环境）。
# 等价于 macOS 的 `cargo build --release`：把工具链、CMake、pkg-config、
# FFmpeg/libusb/libsodium 头和 libclang path 一次性设置好。
# 用法：powershell -File scripts\build.ps1 [透传给 cargo 的参数]

$MsysRoot = "C:\msys64"
if (-not (Test-Path "$MsysRoot\ucrt64\bin\gcc.exe")) {
    Write-Error "MSYS2 UCRT64 工具链没找到（C:\msys64\ucrt64）。先装 MSYS2 并执行：`n" +
        "  C:\msys64\usr\bin\pacman.exe -S mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-cmake mingw-w64-ucrt-x86_64-ninja mingw-w64-ucrt-x86_64-pkgconf mingw-w64-ucrt-x86_64-clang mingw-w64-ucrt-x86_64-llvm mingw-w64-ucrt-x86_64-libusb mingw-w64-ucrt-x86_64-libsodium mingw-w64-ucrt-x86_64-ffmpeg mingw-w64-ucrt-x86_64-rust"
    exit 1
}

$env:PATH = "$MsysRoot\ucrt64\bin;$env:PATH"
$env:PKG_CONFIG_PATH = "$MsysRoot\ucrt64\lib\pkgconfig"
$env:CMAKE_GENERATOR = "Ninja"
$env:LIBCLANG_PATH = "$MsysRoot\ucrt64\bin"

cargo build @args
exit $LASTEXITCODE
