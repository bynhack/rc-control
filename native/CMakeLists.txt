# Builds Aviateur's radio receive path (devourer + wfb-ng) plus a small C API
# as a static library for rc-control. Aviateur's sources are compiled
# unmodified; only its GUI header is swapped for native/gui_interface.h.
cmake_minimum_required(VERSION 3.18)
project(rcwfb C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

set(AVIATEUR ${CMAKE_CURRENT_SOURCE_DIR}/../third_party/aviateur)
if (NOT EXISTS ${AVIATEUR}/3rd/devourer/CMakeLists.txt)
    message(FATAL_ERROR
        "Aviateur sources missing. Run:\n"
        "  git submodule update --init third_party/aviateur\n"
        "  git -C third_party/aviateur submodule update --init 3rd/devourer")
endif ()

find_package(PkgConfig REQUIRED)
pkg_check_modules(LIBSODIUM REQUIRED IMPORTED_TARGET libsodium)

# Only the library; devourer's demos and tests stay out of the build.
add_subdirectory(${AVIATEUR}/3rd/devourer devourer EXCLUDE_FROM_ALL)

# Stage src/wifi next to our gui_interface.h so `#include "../gui_interface.h"`
# in Aviateur's sources resolves to the stand-in.
set(STAGE ${CMAKE_BINARY_DIR}/aviateur/src)
file(COPY ${AVIATEUR}/src/wifi DESTINATION ${STAGE})
configure_file(${CMAKE_CURRENT_SOURCE_DIR}/gui_interface.h ${STAGE}/gui_interface.h COPYONLY)

# Replaces `old` with `new` in a staged file, failing loudly if upstream
# changed and the anchor is gone, so every patch gets reviewed.
function(patch_staged file old new why)
    file(READ ${file} src)
    string(FIND "${src}" "${old}" pos)
    if (pos EQUAL -1)
        message(FATAL_ERROR "${file} changed upstream; review the patch: ${why}")
    endif ()
    string(REPLACE "${old}" "${new}" src "${src}")
    file(WRITE ${file} "${src}")
endfunction()

# MinGW (MSYS2 UCRT64) fixes. Both sit inside Windows-only #ifdefs upstream,
# so other platforms are unaffected.
# - winpthreads already provides clock_gettime; the inline copy clashes.
patch_staged(${STAGE}/wifi/net_compat.h
        "    inline int clock_gettime(int clk_id, struct timespec *tp) {"
        "    #if !defined(__MINGW32__)\n    inline int clock_gettime(int clk_id, struct timespec *tp) {"
        "MinGW clock_gettime")
patch_staged(${STAGE}/wifi/net_compat.h
        "        return 0;\n    }\n    #ifdef __cplusplus\n    }\n    #endif"
        "        return 0;\n    }\n    #endif /* !defined(__MINGW32__) */\n    #ifdef __cplusplus\n    }\n    #endif"
        "MinGW clock_gettime (end)")
# - weak getopt globals are duplicate definitions under the PE linker; nothing
#   references them, so MinGW gets none (MSVC keeps its selectany copies).
patch_staged(${STAGE}/wifi/compat/getopt.h
        "#else\nchar *optarg __attribute__((weak)) = nullptr;\nint optind __attribute__((weak)) = 1, opterr __attribute__((weak)) = 1, optopt __attribute__((weak)) = 0;\n#endif"
        "#endif"
        "MinGW getopt globals")

# Upstream fix: TxFrame::run never closes its uplink socket (UDP 8001), so
# starting the link again in the same process fails to bind and the uncaught
# exception aborts the program. Close the sockets on the staged copy; fail
# loudly if upstream changes this code so the patch can be reviewed.
set(TXF ${STAGE}/wifi/tx_frame.cpp)
file(READ ${TXF} TXF_SRC)
set(TXF_ANCHOR "        std::fprintf(stderr, \"Error in TxFrame::run: %s\\n\", ex.what());\n    }\n}")
string(FIND "${TXF_SRC}" "${TXF_ANCHOR}" TXF_POS)
if (TXF_POS EQUAL -1)
    message(FATAL_ERROR "tx_frame.cpp changed upstream; review the socket-close patch in native/CMakeLists.txt")
endif ()
string(REPLACE "${TXF_ANCHOR}"
        "        std::fprintf(stderr, \"Error in TxFrame::run: %s\\n\", ex.what());\n    }\n    for (int fd : rxFds) {\n        wfb_close(fd);\n    }\n}"
        TXF_SRC "${TXF_SRC}")
file(WRITE ${TXF} "${TXF_SRC}")

file(GLOB WIFI_SRC ${STAGE}/wifi/*.cpp)
file(GLOB WFB_SRC ${STAGE}/wifi/wfb-ng/*.c ${STAGE}/wifi/wfb-ng/*.cpp)
if (NOT WIN32)
    file(GLOB PLATFORM_SRC ${STAGE}/wifi/linux/*.cpp)
endif ()

add_library(rcwfb STATIC rcwfb.cpp ${WIFI_SRC} ${WFB_SRC} ${PLATFORM_SRC})
target_include_directories(rcwfb PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${STAGE}
        ${STAGE}/wifi
        ${STAGE}/wifi/compat
        ${STAGE}/wifi/wfb-ng/include)
# Same FEC tuning as Aviateur's own build.
target_compile_definitions(rcwfb PRIVATE
        ZFEX_UNROLL_ADDMUL_SIMD=8
        ZFEX_USE_INTEL_SSSE3
        ZFEX_USE_ARM_NEON
        ZFEX_INLINE_ADDMUL
        ZFEX_INLINE_ADDMUL_SIMD)
if (MSVC)
    target_compile_options(rcwfb PRIVATE /utf-8)
endif ()
target_link_libraries(rcwfb PUBLIC devourer PkgConfig::LIBSODIUM)
