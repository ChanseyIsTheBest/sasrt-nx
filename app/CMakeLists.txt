# Sonic & All-Stars Racing Transformed (Xbox 360): static recompilation host application.
#
# The game code is not in this repository: run the code generator first (tools/codegen.ps1), which writes generated/
# from your own default.xex together with the CMake glue (generated/rexglue.cmake, made by `rexglue codegen`).
#
# Stage 1, Windows PC:
#   cmake --preset win-pc && cmake --build --preset win-pc        (from app/, inside tools\win\env.ps1)
# Nintendo Switch (devkitA64), later:
#   cmake -S app -B out/nx -G Ninja -DCMAKE_BUILD_TYPE=Release \
#     -DCMAKE_TOOLCHAIN_FILE=tools/switch/cmake/switch-devkitA64.cmake -DREXGLUE_SWITCH_NVK_SDK=<mesa sdk>

cmake_minimum_required(VERSION 3.25)
project(sasrt LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# The SDK is built from source in this repository unless another tree is given.
set(REXSDK_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../sdk" CACHE PATH "Path to the ReXGlue SDK source tree")
# base port 239 (banjo-nx, 2026-11-20, the render thread against renut-nx 1.0.2): full debug info (-g, with the
# inlined functions) for Renut's renderer and plume, so a console profile's samples can be named by the source
# function they fall in even where PGO and LTO inlined it. -g does not change the code.
option(BANJO_SWITCH_RENUT_DEBUG_INFO "Switch: -g for Renut's renderer and plume (profiling aid)" OFF)
# base port 236 (banjo-nx, 2026-11-20): the renderer's diagnostic censuses (blur_renut_diag_stage_census,
# blur_renut_diag_batch_census) compiled in. OFF (the Switch's default): their checks are constant false and every
# census block compiles away; the keys do nothing. In Showdown Town the checks with the keys off cost N&B's render
# thread ~0.1 us a draw. (Set on the renderer's targets below.)
option(BANJO_SWITCH_DIAG_CENSUS "Switch: compile in the renderer's diagnostic censuses" OFF)

# devkitA64's GCC 16.1: the AArch64 early register allocation pass (-mearly-ra, on from -O2) is off for everything
# built for the console. peggle2-nx found on a console (2026-10-13) that the pass drops table lookups in a recompiled
# function that uses the NEON vperm helper's two-register lookup (38 of 145 in the XDK's streaming copy, and a
# register holding a constant is overwritten inside the loop): garbage textures, with the PC build (clang) and every
# PC check correct. Set here, before the SDK is added, and on the link line too, so the SDK libraries and the LTO
# link have it. Nothing of this game's code showed the fault where it was looked for (tools/early_ra_check.py), and
# the pass is worth 0 to 0.3 % of the instructions here: not worth trusting. tools/check_switch_build.py fails a
# build with a compile statement that lacks the flag.
if(REXGLUE_PLATFORM_SWITCH)
    option(SASRT_SWITCH_NO_EARLY_RA "GCC's AArch64 early register allocation pass off (-mearly-ra=none)" ON)
    if(SASRT_SWITCH_NO_EARLY_RA)
        add_compile_options(-mearly-ra=none)
        add_link_options(-mearly-ra=none)
    endif()
    # sasrt-nx (2026-11-09, from rr6-nx / banjo-nx's package 27): atomics inline. GCC's default for AArch64 calls
    # out-of-line helpers (__aarch64_cas4_acq, __aarch64_ldadd8_rel, ...) that test for LSE atomics at run time; the A57
    # has none, so every atomic was a call, a load and a branch before the same load-exclusive / store-exclusive loop this
    # writes inline. The same instructions. Before the SDK is added, so its libraries get it too.
    option(SASRT_SWITCH_OUTLINE_ATOMICS "Switch: GCC's out-of-line atomic helpers (its default; OFF writes them inline)" OFF)
    if(NOT SASRT_SWITCH_OUTLINE_ATOMICS)
        add_compile_options(-mno-outline-atomics)
    endif()
    # sasrt-nx (2026-11-09, renut-ultimate's of 2026-11-07): the SDK's libraries in each Switch build folder
    # (sdk/CMakeLists.txt), so they can be built with each folder's LTO and PGO options (SASRT_SWITCH_SDK_OPT below).
    set(REXGLUE_OUTPUT_IN_BUILD ON CACHE BOOL "The SDK's libraries and tools in this build folder")
endif()

# sasrt-nx (2026-11-11): the SDK's small helpers forced inline (sdk/include/rex/ppc/diet_ops.h, REX_SMALL_HELPER).
# Before the SDK's targets (generated/rexglue.cmake adds them) so the switch reaches them too (round A's audit).
# sasrt-nx (2026-11-11, machine-copy batch 3 (2026-11-11), idea 43 F1 / F2): VMX's estimates and multiply-add in their
# faster AArch64 forms (tools/vmx_float_macros.py): NOT the same results as today (closer to the 360's own, which
# estimates and rounds once); on since the fuzz was read (below). Global, so the SDK sees the same.
# sasrt-nx (2026-11-11, machine-copy batch 3, idea 46 part 2): the copies' loops with the stable globals built in.
option(SASRT_HOT_FROZEN "Localized copies: stable guest globals built into their loops behind an entry check" ON)
if(NOT SASRT_HOT_FROZEN)
    add_compile_definitions(SASRT_HOT_FROZEN_OFF)
endif()
# sasrt-nx (2026-11-11 ~09:45, the user: "keep all three on and tell ridge racer 6 to keep them on"): ON. The console's
# fuzz (gv4, 64 M lanes each): the fast estimates within 3 ulp (vrsqrtefp) and 1 ulp (vrefp) of the exact results the
# port computed before, the fused multiply-add different in 2.4 % of lanes (one rounding, as the 360's vmaddfp); the
# 360's own estimates are good to about 1/4096 (~2,000 ulp). Not bit-identical to the port before; AArch64 only (the PC
# keeps the exact expressions). An existing build folder keeps its cached OFF: cmake -DSASRT_VMX_FAST_ESTIMATES=ON
# -DSASRT_VMX_FUSED_MADD=ON on it.
option(SASRT_VMX_FAST_ESTIMATES "VMX vrsqrtefp / vrefp as frsqrte / frecpe with two Newton steps (not bit-exact)" ON)
option(SASRT_VMX_FUSED_MADD "VMX vmaddfp as one fused multiply-add (not bit-exact)" ON)
if(SASRT_VMX_FAST_ESTIMATES)
    add_compile_definitions(REX_VMX_FAST_ESTIMATES)
endif()
if(SASRT_VMX_FUSED_MADD)
    add_compile_definitions(REX_VMX_FUSED_MADD)
endif()
option(SASRT_FORCE_INLINE_HELPERS "The SDK's one-instruction helpers forced inline (OFF: REX_NO_FORCED_HELPERS)" ON)
if(NOT SASRT_FORCE_INLINE_HELPERS)
    add_compile_definitions(REX_NO_FORCED_HELPERS)
endif()

if(NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/generated/rexglue.cmake")
    message(FATAL_ERROR "app/generated/rexglue.cmake is missing: run tools/codegen.ps1 first")
endif()
# sasrt-nx (2026-11-13, base port 96; blur-nx 2026-11-12, the user there: "Please do the fmadds change", and for the
# base: "I want 96 on by default"): the scalar fmadds / fmsubs / fnmadds / fnmsubs rounded once in single precision, as
# the Xenon does (tools/fma_single.py, a post_codegen.py step; sdk/include/rex/ppc/fma_single.h: one fmaf when the three
# inputs are floats, the double form otherwise), instead of the double fused multiply-add rounded again to single: one
# unit in the last place apart in rare cases (about one operation in a few hundred million; the double form is the one
# that is off), and single-precision chains stay in float registers. OFF: the double rounding, as before
# (REX_FMADDS_DOUBLE_ROUNDING). The base's and blur-nx's name for it: BLUR_FMADDS_SINGLE. With BLUR_FPCR_ONE_MODE (not
# bit-exact anyway) a denormal single input is flushed by the fmaf too.
option(SASRT_FMADDS_SINGLE "Scalar fmadds and kin rounded once in single precision (the Xenon's rounding; not bit-exact to the double form)" ON)
if(NOT SASRT_FMADDS_SINGLE)
    add_compile_definitions(REX_FMADDS_DOUBLE_ROUNDING)
endif()
# renut-ultimate (2026-11-16, port 144; tw2de_nx's fix, off by default at the user's word): fnmadd / fnmsub and their
# single forms with the PowerPC's sign of zero and NaN (sdk/include/rex/ppc/fpu_fma.h, tools/fnm_sign.py's
# REX_FNEG_FUSED). GCC folds the generated -std::fma(...) into FNMADD / FMSUB, which give +0 where the 360 gives -0 and
# negate a NaN result (Xenia's hardware-recorded tests: 160 cases). ON: the fused result kept by an empty asm, then
# negated unless NaN (an instruction or two more a site; Katamari: 272 sites). A compile-time switch: retrain the PGO
# profile.
option(TW2DE_FNMADD_SIGN "fnmadd / fnmsub with the PowerPC's sign of zero and NaN (exact; off by default)" OFF)
if(TW2DE_FNMADD_SIGN)
    add_compile_definitions(REX_FNMADD_SIGN_EXACT)
endif()
# renut-ultimate (2026-11-16, port 144; tw2de_nx's, off by default at the user's word): vsl / vsr with a count per byte,
# as the hardware shifts (rex/ppc/intrinsics.h REX_VSHIFT_PER_BYTE; Xenia's hardware-recorded tests: 453 of 475 vsl
# cases with counts that differ between bytes). The same as before for the ISA's uniform counts; on AArch64 five NEON
# instructions each (the default vsl goes through memory). Katamari: 112 vsr sites. Retrain the PGO profile.
option(TW2DE_VSHIFT_PER_BYTE "vsl / vsr with each byte's own shift count, as the hardware (off by default)" OFF)
if(TW2DE_VSHIFT_PER_BYTE)
    add_compile_definitions(REX_VSHIFT_PER_BYTE)
endif()
# blur-nx (2026-11-12, codegen-ideas-3 CG-13; the user: "build CG 13 ... it probably should be off by default"): all guest
# float code with the host's flush mode on (rex/ppc/context.h, rex/ppc/diet_ops.h): no `msr fpcr` switch in the game code
# after a thread's first, and the any-mode float helpers as the plain operations. NOT bit-exact: the Xenon's scalar FPU
# keeps denormals (values below FLT_MIN / DBL_MIN), which this flushes to zero as its VMX unit does. The PC census
# (banjo_diag_runtime_census: "[census] CG-13" lines, tools/census_sites.py --denormal) counts the results it changes.
# A compile-time switch: every generated file, the copies and the SDK runtime change with it (retrain the PGO profile).
# sasrt-nx (2026-11-13, the user's choice: "Yes, on by default"): ON in this port's Switch build. Console A/B against
# the bit-exact synced build, same session: process CPU 80.63 -> 78.77 ms a frame (-2.3 %), Main XThread -4.3 %,
# WaterThread -5.4 %, fps +1.8 %; picture check over three laps right (docs/ultimate-base.md). A bit-exact build for
# an A/B: tools/win/build_switch.ps1 -BitExact (or -DBLUR_FPCR_ONE_MODE=OFF). Since base port 133 the base has it ON
# on the Switch too (and OFF on the PC, which stays exact for the guard and census runs): the base's form below.
# renut-ultimate (2026-11-13, port 133; the user: "turn it on by default in the base ... because it's universal big CPU
# benefit"): ON by default in the Switch build (each switch is an `msr fpcr` on the console: Katamari's game code does
# about 1.2 million a second on the PC; blur-nx's console +4.6 % fps). OFF by default in the PC build, which stays
# exact: the census counts what the Switch build changes only where the mode still switches
# (tools/cg13_census.ps1). An existing build folder keeps its cached value: -DBLUR_FPCR_ONE_MODE=ON / OFF changes it.
if(REXGLUE_PLATFORM_SWITCH)
    set(_blur_fpcr_one_mode_default ON)
else()
    set(_blur_fpcr_one_mode_default OFF)
endif()
option(BLUR_FPCR_ONE_MODE "All guest float code in the flush mode (no FPCR switches; not bit-exact for scalar denormals)"
       ${_blur_fpcr_one_mode_default})
if(BLUR_FPCR_ONE_MODE)
    add_compile_definitions(REX_FPCR_ONE_MODE)
endif()
# renut-ultimate (2026-11-14, port 140; blur-nx's docs/cpu-near-exact-50-1113.md): the compile-time near-exact switches
# (rex/ppc/diet_ops.h, context.h, tools/near_exact.py), each the code before when off. NOT bit-exact in rare cases:
# #1 REX_NX_SNAN_PASS, #2 REX_NX_FCTI_NO_NAN, #17 REX_NX_DIV_NO_CHECK, #41 REX_NX_FCMP_NO_UN, #42 REX_NX_VMINMAX_FAST,
# #5 REX_NX_XER_SO_ZERO, #19 REX_NX_NO_TRAPS (a trap only logs). OFF in the base: each game runs the PC census
# (banjo_diag_runtime_census, the "[census] near-exact" lines) before turning them on. blur-nx's census took #2 (NaN
# conversions not rare: 80 a second) and #42 (4 % of vector max/min lanes differ) out of the set; BLUR_NX_ONLY names
# switches to use alone (a ;-list, for a bisect; #2 and #42 only this way), BLUR_NX_SKIP leaves some out. Every
# generated file, the copies and the SDK change with them: retrain the PGO profile.
option(BLUR_NEAR_EXACT "blur-nx's near-exact compile-time switches (not bit-exact in rare cases)" OFF)
set(BLUR_NX_ONLY "" CACHE STRING "With BLUR_NEAR_EXACT: only these switches (a ;-list, for a bisect; empty: all)")
set(BLUR_NX_SKIP "" CACHE STRING "With BLUR_NEAR_EXACT: every switch but these (a ;-list)")
set(_blur_nx_switches REX_NX_SNAN_PASS REX_NX_DIV_NO_CHECK REX_NX_FCMP_NO_UN REX_NX_XER_SO_ZERO REX_NX_NO_TRAPS)
if(BLUR_NEAR_EXACT AND NOT BLUR_NX_ONLY STREQUAL "")
    list(APPEND _blur_nx_switches REX_NX_FCTI_NO_NAN REX_NX_VMINMAX_FAST)
endif()
if(BLUR_NEAR_EXACT)
    foreach(_s ${_blur_nx_switches})
        if((BLUR_NX_ONLY STREQUAL "" OR _s IN_LIST BLUR_NX_ONLY) AND NOT _s IN_LIST BLUR_NX_SKIP)
            add_compile_definitions(${_s})
            message(STATUS "near-exact: ${_s}")
        endif()
    endforeach()
endif()
# renut-ultimate (2026-11-14, port 140; blur-nx's #66, exact): the generated tree's store cards by the copies' rule
# (tools/store_cards.py: only the pages whose cards Renut reads, a card written only when not set yet). ON, as in
# blur-nx's every build; OFF: every store marks its card as before.
option(BLUR_CARD_VIEWS_ONLY "The generated tree's store cards only for Renut's views, written only when set (exact)" ON)
if(BLUR_CARD_VIEWS_ONLY)
    add_compile_definitions(REX_CARD_VIEWS_ONLY)
endif()
include(generated/rexglue.cmake)
# Port 158 (from fnxf_xiii, its note of 2026-10-26): the function registration (generated/renut_register.cpp, one
# function of about 44,000 SetFunction calls, run once at start) without optimisation in the Switch build. GCC's
# optimisation of it was the build's critical path: 1,171 s of a 1,195 s full Switch build (Katamari, 2026-11-18;
# fnxf_xiii: 81 minutes at -O2). Appended to the generated sources' options, so it comes after their -O level and
# wins. Without the precompiled header: GCC does not use a PCH made with optimisation in an -O0 file ("__OPTIMIZE__ not
# defined"); renut_init.h includes renut_pch.h itself. LTO keeps each function's own level. OFF: as before.
option(BANJO_REGISTER_O0 "Switch: the function registration file at -O0, without the PCH (build time)" ON)
if(BANJO_REGISTER_O0 AND REXGLUE_PLATFORM_SWITCH AND EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/generated/renut_register.cpp")
    set_property(SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/generated/renut_register.cpp" APPEND PROPERTY COMPILE_OPTIONS -O0)
    set_property(SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/generated/renut_register.cpp" PROPERTY SKIP_PRECOMPILE_HEADERS ON)
endif()

# The build re-runs the generator by itself whenever an input in codegen.d changes (manifest, toml, xex, the generator
# binary). That rewrites app/generated and would silently drop the codegen flavour's post-codegen steps (no-volatile
# pch, direct calls): they are appended to the same command (docs/enhancements.md, "Build-time"; futari-nx's and
# sa2-nx's finding). The Switch cross build has no generator target, so this only applies on the PC.
if(TARGET sasrt_codegen)
    find_package(Python3 COMPONENTS Interpreter REQUIRED)
    add_custom_command(OUTPUT "${CMAKE_CURRENT_SOURCE_DIR}/generated/default/codegen.build.stamp" APPEND
        COMMAND "${CMAKE_COMMAND}" -E env "REXSDK_DIR=${REXSDK_DIR}"
                "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/../tools/post_codegen.py")
endif()

# renut-ultimate (2026-11-20, port 193): the game's name in the build stamp (src/build_stamp.cpp).
set(RENUT_GAME_NAME "Sonic and All-Stars Racing Transformed")

set(SASRT_SOURCES
    src/main.cpp
    src/build_stamp.cpp  # port 193: the build stamp, the first line of every log (cmake/build_stamp.cmake)
    # The game's frame counter (its D3DDevice_Swap) and the Direct3D trace (cvar sasrt_d3d_trace, off by default).
    src/sasrt_d3d_trace.cpp
    # Video recordings of the game image for testing (cvar sasrt_video_s; tools/make_video.sh makes the MP4).
    src/sasrt_capture.cpp
    src/sasrt_renderdoc.cpp
    # DLC: installs the content packages in dlc/ next to the executable (cvar sasrt_dlc_dir).
    src/sasrt_dlc.cpp
    # Scripted controller presses for unattended test runs (cvar sasrt_input_script).
    src/sasrt_input_script.cpp
    # Every performance enhancement's on/off key, the group masters and verify mode (docs/enhancements.md).
    src/sasrt_enhancements.cpp
    # The PC side of the generated code's self-checks and the indirect call census; the start-up check of the forms
    # only one processor has (both from sa2-nx's CPU rounds of 2026-10-12).
    src/sasrt_codegen_checks.cpp
    src/sasrt_forms_selfcheck.cpp
    # sasrt-nx (2026-11-19, base port 151; blur-nx #220): small C++ allocations per thread (Switch; 32 MB arena,
    # blur_small_alloc_mb; enabled in SasrtApp::OnPostSetup).
    src/blur_small_alloc.cpp
    # sasrt-nx (2026-11-19, the user: "can you port the game menu please"; base ports 177-182, Blur's): the game menu
    # (A+B+X+Y+L+R on the Switch, F8 on the PC; SasrtApp::OnCreateDialogs).
    src/game_menu.cpp
    # sasrt-nx (2026-11-13, base port 90; blur-nx 2026-11-11): timings of a few processor forms at boot (cvar
    # blur_microbench, off; called after the forms self-check).
    src/cpu/blur_microbench.cpp
    # sasrt-nx (2026-11-19, the user's request; tw2de_nx's tw2de_usm_ffmpeg.cpp): the USM movies' MPEG video decoded by
    # FFmpeg on the host (sasrt_usm_ffmpeg; sdk/thirdparty/FFmpeg/config_sasrt_usm.h turns the MPEG-1/2 decoder on).
    src/cpu/sasrt_usm_ffmpeg.cpp
    # CPU enhancement: the game's Direct3D GPU wait sleeps on the ring thread's progress (sasrt_cpu_gpu_wait_sleep).
    src/sasrt_gpu_wait.cpp
    # PC sampling profiler (sasrt_pc_profile_s; futari-nx's; tools/pc_hot_functions.py). Nothing on the Switch.
    src/sasrt_pc_profiler.cpp
    # CPU enhancements: native replacements of hot guest functions (localized copies generated into generated/hot/ by
    # tools/localize_native.py from src/hot/localized.txt, the CRT memcpy by hand), with their guards.
    src/hot/sasrt_hot_guest.cpp
    # sasrt-nx (2026-11-08, katamari-nx's docs/optimising-functions.md): the localized copies of the console profile's
    # hot functions (src/cpu/hot/localized.txt, localized_bulk.txt in twelve shards) and the hand-written natives
    # (src/cpu/hot/hand.txt), with katamari-nx's guard.
    src/cpu/banjo_hot_guest.cpp
    src/cpu/banjo_hot_shard_0.cpp
    src/cpu/banjo_hot_shard_1.cpp
    src/cpu/banjo_hot_shard_2.cpp
    src/cpu/banjo_hot_shard_3.cpp
    src/cpu/banjo_hot_shard_4.cpp
    src/cpu/banjo_hot_shard_5.cpp
    src/cpu/banjo_hot_shard_6.cpp
    src/cpu/banjo_hot_shard_7.cpp
    src/cpu/banjo_hot_shard_8.cpp
    src/cpu/banjo_hot_shard_9.cpp
    src/cpu/banjo_hot_shard_10.cpp
    src/cpu/banjo_hot_shard_11.cpp
    # Windows: logs fatal host exceptions the SDK does not report (illegal instruction, ...) with module + offset.
    src/sasrt_crash_log.cpp
    # Temporary hooks that log the callers of functions a boot crashed in.
    src/sasrt_debug_hooks.cpp
    # Stage 4: the native renderer (src/me, masseffect-nx's PM4-ring Vulkan renderer as adapted by banjo-nx and sa2-nx).
    # It replaces the emulated Xenos GPU with masseffect_renderer_native = true.
    src/me/me_native_system.cpp
    src/me/me_ring_wait.cpp
    src/me/me_renderdoc.cpp
    src/me/masseffect/masseffect_native_draws.cpp
    src/me/masseffect/masseffect_deferred_recording.cpp
    src/me/masseffect/masseffect_native_targets.cpp
    src/me/masseffect/masseffect_native_shaders.cpp
    src/me/masseffect/masseffect_native_textures_pool.cpp
    src/me/masseffect/masseffect_shader_library.cpp
    src/me/masseffect/me_masseffect_glue.cpp
    # The game's D3D addresses (draw-time shader load, Draw*) and the shader container dump (sasrt_dump_shaders).
    src/me/sasrt_me_hooks.cpp
    src/me/sasrt_d3d_census.cpp
    src/me/sasrt_api_draw.cpp
    src/me/sasrt_api_clear.cpp
)
# sasrt-nx (2026-11-09): the localized copies' sources (with a PGO profile they get the game code's inliner limits).
set(SASRT_HOT_SOURCES src/cpu/banjo_hot_guest.cpp src/cpu/banjo_hot_shard_0.cpp src/cpu/banjo_hot_shard_1.cpp src/cpu/banjo_hot_shard_2.cpp src/cpu/banjo_hot_shard_3.cpp src/cpu/banjo_hot_shard_4.cpp src/cpu/banjo_hot_shard_5.cpp src/cpu/banjo_hot_shard_6.cpp src/cpu/banjo_hot_shard_7.cpp src/cpu/banjo_hot_shard_8.cpp src/cpu/banjo_hot_shard_9.cpp src/cpu/banjo_hot_shard_10.cpp src/cpu/banjo_hot_shard_11.cpp)
if(NOT REXGLUE_PLATFORM_SWITCH)
    # Switch profiler counters the native renderer calls (no-ops on PC).
    list(APPEND SASRT_SOURCES src/me/me_pc_stubs.cpp)
else()
    # The ring thread's own CPU time on Horizon (its timer line and the in-run A/B).
    list(APPEND SASRT_SOURCES src/me/me_switch_cycles.cpp)
    # sasrt-nx (2026-11-09): PGO profile collection (SASRT_PGO=generate; empty otherwise). From rr6-nx / sa2-nx.
    list(APPEND SASRT_SOURCES src/sasrt_pgo.cpp)
    # sasrt-nx (2026-10-20): no Vulkan driver in the NRO unless REXGLUE_SWITCH_LINK_NVK (sdk/cmake/rexglue_switch.cmake):
    # the entry points the code still references, saying there is no driver.
    if(NOT REXGLUE_SWITCH_LINK_NVK)
        list(APPEND SASRT_SOURCES src/sasrt_switch_no_vulkan.cpp)
    endif()
endif()

# The codegen flavour (tools/codegen.ps1 -Flavor) names the build in the first "[enhancements]" log line.
set(SASRT_FLAVOR_FILE "${CMAKE_CURRENT_SOURCE_DIR}/generated/codegen_flavor.txt")
set(SASRT_BUILD_FLAVOR "unknown codegen")  # no codegen_flavor.txt: tools/post_codegen.py did not run
if(EXISTS "${SASRT_FLAVOR_FILE}")
    file(READ "${SASRT_FLAVOR_FILE}" SASRT_BUILD_FLAVOR)
    string(STRIP "${SASRT_BUILD_FLAVOR}" SASRT_BUILD_FLAVOR)
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${SASRT_FLAVOR_FILE}")
endif()
set_source_files_properties(src/sasrt_enhancements.cpp PROPERTIES
    COMPILE_DEFINITIONS "SASRT_BUILD_FLAVOR=\"${SASRT_BUILD_FLAVOR}\"")

if(WIN32)
    add_executable(sasrt WIN32 ${SASRT_SOURCES})
else()
    add_executable(sasrt ${SASRT_SOURCES})
endif()

# Port 193 (TFU-nx's): the build stamp header, rewritten on every build when its text changes (a custom target with no
# output runs every time; the script leaves the header alone when the commit is the same).
if(REXGLUE_PLATFORM_SWITCH)
    set(RENUT_BUILD_KIND "switch")
else()
    set(RENUT_BUILD_KIND "pc")
endif()
set(RENUT_BUILD_STAMP_DIR "${CMAKE_CURRENT_BINARY_DIR}/build_stamp")
add_custom_target(sasrt_build_stamp
    COMMAND "${CMAKE_COMMAND}" -E make_directory "${RENUT_BUILD_STAMP_DIR}"
    COMMAND "${CMAKE_COMMAND}" "-DOUT=${RENUT_BUILD_STAMP_DIR}/build_stamp.h" "-DROOT=${CMAKE_CURRENT_SOURCE_DIR}/.."
            "-DKIND=${RENUT_BUILD_KIND}" "-DNAME=${RENUT_GAME_NAME}" -P "${CMAKE_CURRENT_SOURCE_DIR}/cmake/build_stamp.cmake"
    BYPRODUCTS "${RENUT_BUILD_STAMP_DIR}/build_stamp.h"
    VERBATIM)
add_dependencies(sasrt sasrt_build_stamp)
target_include_directories(sasrt PRIVATE "${RENUT_BUILD_STAMP_DIR}")
set_source_files_properties(src/build_stamp.cpp PROPERTIES SKIP_PRECOMPILE_HEADERS ON)

# Link the SDK. Stage 1 draws with ReXGlue's Xenos GPU emulation; the native renderer replaces it later.
rexglue_setup_target(sasrt GPU_PLUGINS xenos)

# sasrt-nx (2026-10-20, banjo-nx's of 2026-10-17): Ryujinx starts NROs without argv[0]; the SDK then takes the NRO's
# usual place on the SD (sdk/src/core/filesystem_posix.cpp). A console's hbloader always passes the path.
if(REXGLUE_PLATFORM_SWITCH AND TARGET rexcore)
    target_compile_definitions(rexcore PRIVATE REX_SWITCH_FALLBACK_EXE="/switch/sasrt-nx/sasrt.nro")
endif()

# sasrt-nx (2026-10-19): Renut's Direct3D-level renderer as a second renderer, chosen at boot (sasrt_renderer = "renut";
# cmake/sasrt_renut_gpu.cmake, docs/deko3d-renderer.md): this game's Direct3D runs natively through plume (Vulkan on the
# PC, deko3d on the Switch), with no PM4 ring and no EDRAM emulation. OFF builds this port's own renderer only.
option(SASRT_RENUT_RENDERER "Build Renut's native renderer in (sasrt_renderer = renut)" ON)
if(SASRT_RENUT_RENDERER)
    include("${CMAKE_CURRENT_SOURCE_DIR}/cmake/sasrt_renut_gpu.cmake")
endif()

# SPIR-V initializers of the native renderer's EDRAM transfer / utility shaders (src/me/masseffect/shaders), compiled
# on the host with glslangValidator (tools/win/build_glslang.ps1 builds it from the SDK's glslang). The Switch build
# uses the same host tool: SPIR-V is platform independent.
set(SASRT_GLSLANG_VALIDATOR "${CMAKE_CURRENT_SOURCE_DIR}/../out/glslang/StandAlone/glslangValidator${CMAKE_EXECUTABLE_SUFFIX}"
    CACHE FILEPATH "Host glslangValidator")
set(SASRT_GENERATED_SHADER_DIR "${CMAKE_CURRENT_BINARY_DIR}/generated-shaders")
set(SASRT_EDRAM_SHADER_INCLUDES)
foreach(_shader sasrt_resolve_copy sasrt_resolve_copy_uint masseffect_edram_7e3_to_rgba8 masseffect_edram_rgba8_to_7e3 masseffect_edram_16f_to_16f me_resolve_exp_bias me_edram_depth_to_rgba8 me_edram_depth_to_16f me_edram_import me_edram_color_to_depth me_edram_depth_to_depth me_edram_depth_to_stencil me_edram_color_to_stencil me_edram_depth_to_depth_msaa2 me_edram_depth_msaa2_to_depth_1x me_edram_depth_to_stencil_msaa2 me_edram_depth_msaa2_to_stencil_1x me_edram_raw64_to_rgba8 me_edram_rgba8_to_raw64 me_edram_raw64_to_16f me_edram_16f_to_raw64 me_edram_raw64_to_raw64 me_edram_depth_to_raw64 me_edram_raw64_to_depth me_depth_resolve_guestspace me_depth_resolve_guestspace_msaa2 me_depth_resolve_words me_resolved_depth_words me_edram_stencil_to_buffer me_edram_stencil_msaa2_to_buffer me_edram_color_stencil_to_buffer me_edram_color_to_color me_edram_r64_to_r64)
    set(_extension comp)
    if(_shader STREQUAL "me_edram_import")
        set(_extension vert)
    elseif(_shader MATCHES "^sasrt_resolve_copy(_uint)?$")  # sasrt_gpu_resolve_draw
        set(_extension frag)
    elseif(_shader MATCHES "^me_edram_(color_to_depth|depth_to_depth|depth_to_stencil|color_to_stencil|depth_to_depth_msaa2|depth_msaa2_to_depth_1x|depth_to_stencil_msaa2|depth_msaa2_to_stencil_1x|raw64_to_depth|color_to_color|r64_to_r64)$")
        set(_extension frag)
    endif()
    set(_source "${CMAKE_CURRENT_SOURCE_DIR}/src/me/masseffect/shaders/${_shader}.${_extension}")
    set(_output "${SASRT_GENERATED_SHADER_DIR}/${_shader}.inc")
    set(_target_flags)
    if(_shader MATCHES "^me_edram_(stencil_to_buffer|color_stencil_to_buffer|stencil_msaa2_to_buffer|depth_to_depth_msaa2|depth_msaa2_to_depth_1x|depth_to_stencil_msaa2|depth_msaa2_to_stencil_1x)$" OR _shader STREQUAL "me_depth_resolve_guestspace_msaa2")
        set(_target_flags --target-env vulkan1.2)
        set(_output "${SASRT_GENERATED_SHADER_DIR}/${_shader}_generated.inc")
    endif()
    add_custom_command(OUTPUT "${_output}"
        COMMAND "${CMAKE_COMMAND}" -E make_directory "${SASRT_GENERATED_SHADER_DIR}"
        COMMAND "${SASRT_GLSLANG_VALIDATOR}" -V ${_target_flags} -x -o "${_output}" "${_source}"
        DEPENDS "${_source}" VERBATIM)
    list(APPEND SASRT_EDRAM_SHADER_INCLUDES "${_output}")
endforeach()
add_custom_target(sasrt_edram_shaders DEPENDS ${SASRT_EDRAM_SHADER_INCLUDES})
add_dependencies(sasrt sasrt_edram_shaders)
target_include_directories(sasrt PRIVATE
    "${SASRT_GENERATED_SHADER_DIR}"
    src
    src/me
    src/me/masseffect
    src/me/masseffect/shaders
    "${REXSDK_DIR}/src/core"
    # Precompiled SPIR-V of the SDK presenter (vulkan_spirv/guest_output_*): the renderer draws into its output.
    "${REXSDK_DIR}/src/ui/shaders")
# blur-nx (2026-11-18, the game menu's font option; base port 178): Dear ImGui's misc/fonts as byte arrays
# (game_menu_fonts.h). Their licences: THIRD_PARTY_NOTICES.md.
set(_blur_menu_fonts_dir "${REXSDK_DIR}/thirdparty/imgui/misc/fonts")
set(_blur_menu_fonts_text "// Made by app/CMakeLists.txt from ${_blur_menu_fonts_dir} (do not edit).\n#pragma once\n")
foreach(_pair "kMenuFontProggyTiny:ProggyTiny.ttf" "kMenuFontRoboto:Roboto-Medium.ttf" "kMenuFontKarla:Karla-Regular.ttf"
              "kMenuFontCousine:Cousine-Regular.ttf")
    string(REPLACE ":" ";" _parts "${_pair}")
    list(GET _parts 0 _var)
    list(GET _parts 1 _file)
    file(READ "${_blur_menu_fonts_dir}/${_file}" _hex HEX)
    string(REGEX REPLACE "([0-9a-f][0-9a-f])" "0x\\1," _hex "${_hex}")
    string(APPEND _blur_menu_fonts_text "alignas(4) static const unsigned char ${_var}[] = {${_hex}};\n")
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${_blur_menu_fonts_dir}/${_file}")
endforeach()
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/game_menu_fonts/game_menu_fonts.h" "${_blur_menu_fonts_text}")
target_include_directories(sasrt PRIVATE "${CMAKE_CURRENT_BINARY_DIR}/game_menu_fonts")

# CPU-only SDK sources the native renderer reuses (draw-extent estimation, shader microcode interpretation): the
# GPU plugin's private symbols cannot satisfy application-side use.
target_sources(sasrt PRIVATE
    "${REXSDK_DIR}/src/graphics/register_file.cpp"
    "${REXSDK_DIR}/src/graphics/format/ucode.cpp"
    "${REXSDK_DIR}/src/graphics/pipeline/shader/interpreter.cpp")

# The renderer includes xxhash.h and renderdoc_app.h directly; when the SDK is built from source they are private to
# its libraries.
foreach(_dep imgui xxhash renderdoc)  # imgui: the game menu (sasrt-nx 2026-11-19)
    if(TARGET ${_dep})
        target_include_directories(sasrt PRIVATE $<TARGET_PROPERTY:${_dep},INTERFACE_INCLUDE_DIRECTORIES>)
    endif()
endforeach()
# sasrt-nx (2026-11-19): src/cpu/sasrt_usm_ffmpeg.cpp calls FFmpeg's decoder itself (on the PC its own copy beside the
# runtime DLL's, which keeps XMA's).
if(TARGET libavcodec)
    target_link_libraries(sasrt PRIVATE libavcodec libavutil)
endif()
if(BANJO_GENERATED_NO_TRAPPING_MATH AND NOT BLUR_FPCR_ONE_MODE)
    message(WARNING "banjo: BANJO_GENERATED_NO_TRAPPING_MATH needs BLUR_FPCR_ONE_MODE (the flush-mode switches); left off")
endif()

# sasrt-nx (2026-11-21, the user: "please compress all the videos and audio"), from rr6-nx (2026-11-21, the user:
# the movies re-encoded to H.265, as culdcept-nx does): nxvideo (tools/switch/nxvideo,
# culdcept-nx's), the H.265 decoder on the Switch's NVDEC: devkitPro's switch-ffmpeg 7.1 (built with averne's nvtegra
# backend) linked with the shim into one object whose only global symbols are nxv_*, so FFmpeg 7.1's names never meet
# the SDK's FFmpeg (the XMA audio). Built when devkitPro's FFmpeg has nvtegra. Without it the .hevc movies are not shown.
if(REXGLUE_PLATFORM_SWITCH)
    option(SASRT_NXVIDEO "The H.265 movies' NVDEC decoder (tools/switch/nxvideo)" ON)
    set(_nxv_pl "${DEVKITPRO}/portlibs/switch")
    if(SASRT_NXVIDEO AND EXISTS "${_nxv_pl}/include/libavutil/hwcontext_nvtegra.h")
        set(_nxv_src "${CMAKE_CURRENT_SOURCE_DIR}/../tools/switch/nxvideo")
        set(_nxv_out "${CMAKE_CURRENT_BINARY_DIR}/nxvideo")
        file(MAKE_DIRECTORY "${_nxv_out}")
        set(_nxv_keep)
        foreach(_s nxv_open nxv_decode nxv_flush nxv_close nxv_is_hw nxv_version nxv_stats nxv_options)
            list(APPEND _nxv_keep "--keep-global-symbol=${_s}")
        endforeach()
        add_custom_command(OUTPUT "${_nxv_out}/nxvideo.o"
            COMMAND "${CMAKE_C_COMPILER}" -O2 -ffunction-sections -fdata-sections -march=armv8-a+crc+crypto
                    -mtune=cortex-a57 -mtp=soft -ftls-model=local-exec -fPIE -D__SWITCH__ -DNX -D_GNU_SOURCE
                    "-I${_nxv_pl}/include" "-I${DEVKITPRO}/libnx/include" -c "${_nxv_src}/nxvideo.c" -o "${_nxv_out}/shim.o"
            COMMAND "${CMAKE_LINKER}" -r -o "${_nxv_out}/full.o" "${_nxv_out}/shim.o"
                    --start-group "${_nxv_pl}/lib/libavcodec.a" "${_nxv_pl}/lib/libavutil.a" --end-group
            COMMAND "${CMAKE_OBJCOPY}" ${_nxv_keep} "${_nxv_out}/full.o" "${_nxv_out}/nxvideo.o"
            DEPENDS "${_nxv_src}/nxvideo.c" "${_nxv_src}/nxvideo.h"
            COMMENT "nxvideo: FFmpeg 7.1 with nvtegra in one object, only nxv_* global"
            VERBATIM)
        set_source_files_properties("${_nxv_out}/nxvideo.o" PROPERTIES EXTERNAL_OBJECT TRUE GENERATED TRUE)
        target_sources(sasrt PRIVATE "${_nxv_out}/nxvideo.o")
        target_include_directories(sasrt PRIVATE "${_nxv_src}")
        target_compile_definitions(sasrt PRIVATE SASRT_NXVIDEO=1)
        message(STATUS "nxvideo: H.265 / NVDEC movies (devkitPro's switch-ffmpeg with nvtegra)")
    endif()
endif()

# Settings template next to the executable, only when there is none yet (the copy there is the user's to edit).
if(NOT REXGLUE_PLATFORM_SWITCH)
    add_custom_command(TARGET sasrt POST_BUILD
        COMMAND "${CMAKE_COMMAND}" -DSRC=${CMAKE_CURRENT_SOURCE_DIR}/sasrt.toml -DDST=$<TARGET_FILE_DIR:sasrt>/sasrt.toml
                -P "${CMAKE_CURRENT_SOURCE_DIR}/cmake/copy_if_missing.cmake"
        VERBATIM)
endif()

# The SDK compiles itself with these (directory scope), but they do not reach the generated game code, which is
# built in this directory. GCC's default for GNU C++ is -ffp-contract=fast: it fuses separate PPC fmul/fadd into
# FMA and results drift from the Xbox 360. Clang (the PC build) too: strict aliasing is unsafe for recompiled code,
# and its default contraction fuses within an expression (banjo-nx's finding, 2026-10-06).
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    foreach(target sasrt sasrt_recomp)
        if(TARGET ${target})
            target_compile_options(${target} PRIVATE -ffp-contract=off -fno-strict-aliasing)
        endif()
    endforeach()
    # sqrt and friends without the errno check (a compare and a branch to the library after every fsqrt). Values are
    # unchanged: nothing reads errno. On the game code AND the app since 2026-10-13: the app holds the localized copies
    # and natives of the hottest game functions, and GCC refuses to inline between two float-using functions that
    # differ in -fmath-errno (sa2-nx's finding at its LTO link).
    option(SASRT_GAME_NO_MATH_ERRNO "-fno-math-errno on the recompiled game code and the app" ON)
    # -fno-trapping-math was on from 2026-10-07 and is OFF since 2026-10-13 (sa2-nx's audit): it lets the compiler run a
    # float operation earlier than the code does (out of a branch, out of a loop). The recompiled code changes the
    # host's flush mode in between (msr fpcr), which the compiler does not know a float operation depends on, so an
    # operation moved in front of a mode check could compute a denormal operand in the wrong mode. It bought at most
    # 0.5 % of one file in sa2-nx.
    option(SASRT_GAME_NO_TRAPPING_MATH "-fno-trapping-math on the recompiled game code (not exact, see the comment)" OFF)
    foreach(target sasrt_recomp sasrt)
        if(TARGET ${target})
            if(SASRT_GAME_NO_MATH_ERRNO)
                target_compile_options(${target} PRIVATE -fno-math-errno)
            endif()
        endif()
    endforeach()
    if(TARGET sasrt_recomp AND SASRT_GAME_NO_TRAPPING_MATH)
        target_compile_options(sasrt_recomp PRIVATE -fno-trapping-math)
    endif()
endif()

# sa2-nx's CPU rounds 2 and 3 of 2026-10-12 (docs/enhancements.md, "The CPU rounds ported from sa2-nx"): one switch
# back per post-codegen step (tools/post_codegen.py). OFF compiles the statements as they were before the step, on
# every platform, so a PC build can take one step out to find which of them a difference comes from.
option(SASRT_GEN_RO_CONSTANTS "Loads from the image's read-only data as constants" ON)
option(SASRT_GEN_FLOAT_LOADS "Single-precision loads straight into a float register" ON)
option(SASRT_GEN_LEAF_LOCALS "ctx registers of leaf functions with loops as locals" ON)
option(SASRT_GEN_LOOP_LOCALS "ctx registers of call-free loops as locals for the length of the loop" ON)
option(SASRT_GEN_COLD_TRAPS "The trap helper out of line and cold" ON)
option(SASRT_GEN_PROMOTED_CALLS "Guarded direct calls at the promoted indirect call sites" ON)
# sa2-nx's codegen ideas of 2026-10-14 (docs/enhancements.md, "The codegen ideas of 2026-10-14"), one switch each.
option(SASRT_GEN_VPERM1 "A vperm of one vector as a one-register lookup (tools/vperm_one_source.py)" ON)
option(SASRT_GEN_FP_SIGN_OPS "fneg / fabs / fnabs as float operations (tools/fp_sign_ops.py)" ON)
option(SASRT_GEN_LEAF_DEAD "Leaf write-backs no caller can read are skipped (tools/leaf_dead_stores.py)" ON)
# sasrt-nx (2026-11-08): the localized copies' merged vector stores (tools/localize_native.py merge_vector_stores: an
# stvlx/stvrx pair, or four stvewx of one vector, as one 16-byte store of the same bytes). OFF: the original stores.
option(SASRT_HOT_MERGED_STORES "Localized copies: merged unaligned vector stores (tools/localize_native.py)" ON)
# sasrt-nx (2026-11-10, machine-copy idea 27): the guard's logged forms of every localized copy. OFF (a shipping build
# that runs no guard): about two thirds of the copies' code is not made; every hook calls its copy directly.
option(SASRT_HOT_GUARD_FORMS "Localized copies: the guard's logged forms (banjo_hot_guard_*, sasrt_cpu_verify)" ON)
# sasrt-nx (2026-11-11, the user: "go ahead with the plan"): machine copies in place. ON: every copy's hook is a bare
# redirect, the generated function's symbol is the copy (inlinable, no state, no guard, no run-time key), the originals
# unreferenced (LTO drops them), and the list's `inplace_only` copies (the small ones) compiled too. Implies no guard
# forms. OFF: the hooked copies (keys, guard, in-run A/B 70).
option(SASRT_HOT_IN_PLACE "Localized copies in place of the generated functions (no hooks, no guard)" OFF)
if(SASRT_HOT_IN_PLACE)
    target_compile_definitions(sasrt PRIVATE BANJO_HOT_IN_PLACE=1 BANJO_HOT_GUARD_FORMS=0)
elseif(NOT SASRT_HOT_GUARD_FORMS)
    target_compile_definitions(sasrt PRIVATE BANJO_HOT_GUARD_FORMS=0)
endif()
# sasrt-nx (2026-11-10, machine-copy idea 58): tools/localize_native.py puts the bulk copies with fewer than 3 console
# samples in shards 6-11; with this option those shards are compiled for size (-Os), the hot ones as before.
# sasrt-nx (2026-11-11, the batch's run bt1): OFF. With -Os GCC kept the small helpers out of line in the cold shards
# (23,987 calls from 699 of their 731 copies: CRRegister::compare, the flush-mode switches, the conversions), which
# showed on the game thread (the compares 0.011 a frame there alone), and -Os overrides the profile: with PGO the
# compiler already optimises for size the blocks and functions the profile finds cold.
option(SASRT_HOT_COLD_SHARDS "Localized copies: the cold bulk shards (6-11) compiled for size" OFF)
# sasrt-nx (2026-11-11, machine-copy idea 47): the link register's dead moves in the localized copies only. Every non-leaf
# guest function reads ctx.lr (mflr), saves it at -8(r1), loads it back and writes ctx.lr (mtlr): with C++ returns the
# value is never used (tools/frame_traffic.py marks only functions where the link register is not data). The shards are
# compiled with REX_LR_MOVES_ELIDE (frame_traffic.py's opt-in switch: REX_LR_READ gives 0, the save and REX_LR_WRITE are
# nothing); the generated tree keeps them. What it changes for the guest: the dead word at -8 of a copy's frame keeps its
# old content (sa2-nx: the link-register half of the three elisions passed its frame-exact capture; the non-volatile
# saves, which did not, stay). The guard compares only what its logged forms wrote, and both forms of a copy elide.
# (The 23 copies of app/src/cpu/hot/localized.txt, compiled in banjo_hot_guest.cpp, keep them.)
# sasrt-nx (2026-11-13, base port 84 NOT taken here): the base turned this OFF by default (the user's call there,
# 2026-11-11) after vivapinata-nx's guard found 8 differences from it (the save elided in one of a copy's forms and not
# the other: forms built in different translation units, only one with the define), "ON in a game that has checked its
# copies with it". sasrt-nx's own idea 47 keeps its ON default (docs/hand-and-machine-optimising-guide.md: when in
# doubt, build with -DSASRT_HOT_LR_ELIDE=OFF; a guard run with it ON should show 0 differences).
option(SASRT_HOT_LR_ELIDE "The bulk copies (shards 0-11): the link register's dead moves left out (REX_LR_MOVES_ELIDE)" ON)
if(SASRT_HOT_COLD_SHARDS)
    set_source_files_properties(
        src/cpu/banjo_hot_shard_6.cpp src/cpu/banjo_hot_shard_7.cpp src/cpu/banjo_hot_shard_8.cpp
        src/cpu/banjo_hot_shard_9.cpp src/cpu/banjo_hot_shard_10.cpp src/cpu/banjo_hot_shard_11.cpp
        PROPERTIES COMPILE_OPTIONS "-Os")
endif()
# sasrt-nx (2026-11-11, machine-copy batch 2 (2026-11-11), idea 52): the copies' pointer-chase prefetches.
option(SASRT_HOT_PREFETCH "Localized copies: a prefetch after a loop's next-pointer load (REX_PREFETCH_GUEST)" ON)
if(NOT SASRT_HOT_PREFETCH)
    target_compile_definitions(sasrt PRIVATE SASRT_HOT_PREFETCH_OFF)
endif()
# Idea 39: the bulk copies mark store cards per run of stores to a page (app/src/cpu/banjo_hot_prelude.h); OFF: at every
# store, as the tree does.
option(SASRT_HOT_CARD_RUNS "The bulk copies (shards 0-11): store cards marked per run of stores to a page" ON)
if(SASRT_HOT_CARD_RUNS)
    foreach(_shard RANGE 0 11)
        set_property(SOURCE src/cpu/banjo_hot_shard_${_shard}.cpp APPEND PROPERTY COMPILE_DEFINITIONS SASRT_HOT_CARD_RUNS)
    endforeach()
endif()
if(SASRT_HOT_LR_ELIDE)
    foreach(_shard RANGE 0 11)
        set_property(SOURCE src/cpu/banjo_hot_shard_${_shard}.cpp APPEND PROPERTY COMPILE_DEFINITIONS REX_LR_MOVES_ELIDE)
    endforeach()
endif()
if(NOT SASRT_HOT_MERGED_STORES)
    target_compile_definitions(sasrt PRIVATE SASRT_HOT_MERGED_STORES_OFF)
endif()
# The PC test of SASRT_GEN_LEAF_DEAD: a skipped register gets a poison value instead (0xDEADBEEF..., a signalling NaN),
# so a reader the analysis missed breaks the game visibly. Never for a build that ships.
option(SASRT_GEN_LEAF_DEAD_POISON "PC test: poison the skipped leaf write-backs" OFF)
option(SASRT_GEN_SINGLE_FLOATS "Single-precision operations with single inputs in float (tools/single_floats.py)" ON)
option(SASRT_GEN_INLINE_MEMCALLS "memcpy / memset of a constant size up to 64 bytes inline (tools/inline_memcalls.py)" ON)
option(SASRT_GEN_VEC_UNALIGNED "stvlx / stvrx as a few stores instead of byte loops (tools/vec_unaligned_stores.py)" ON)
# banjo-nx's codegen rounds of 2026-10-15 to 2026-10-19, ported 2026-10-19 (docs/enhancements.md, "banjo-nx's codegen
# rounds"): one switch back each. The generator options (rotate_word_shifts, fp_copy_forwarding, dcbt_prefetch) are in
# app/perf_overrides.toml.
option(SASRT_GEN_NARROW_LOOP_BARRIER "Loop barriers clobber the guest window only (OFF: all memory)" ON)
option(SASRT_GEN_DCBT_PREFETCH "The dcbt / dcbtst hints as host prefetches (generator dcbt_prefetch; OFF: nothing)" ON)
option(SASRT_GEN_VECTOR_LOCALS_BY_VALUE "Vector registers of the loop and leaf locals as values, not ctx references" ON)
option(SASRT_GEN_RO_CFG "Read-only constants followed over the control-flow graph (tools/ro_constants_cfg.py)" ON)
option(SASRT_GEN_DEAD_DEFS "Guest register writes nothing reads are left out (tools/dead_ctx_defs.py)" ON)
# The PC test of SASRT_GEN_DEAD_DEFS: a left-out register gets 0xDEADBEEF... instead, so a reader the analysis missed
# breaks the game visibly. Never for a build that ships.
option(SASRT_GEN_DEAD_DEFS_POISON "PC test: poison the left-out register writes" OFF)
option(SASRT_GEN_FLUSH_HOIST "Loop-header flush-mode checks in front of the loop (tools/flush_hoist.py)" ON)
option(SASRT_GEN_SWITCH_THREAD "The bitstream decoder's jump table as threaded computed gotos (tools/switch_goto.py)" ON)
option(SASRT_GEN_LR_WRITE_SAME "Link-register write-backs proven redundant compile to nothing (tools/lr_preserve.py)" ON)
option(SASRT_GEN_R1_LOCAL "Guest r1 as a local mirror in the chosen functions (tools/r1_local.py)" ON)
option(SASRT_GEN_VSEL_NEON "VMX vsel as one NEON bit select (tools/vsel_neon.py)" ON)
option(SASRT_GEN_INLINE_LEAVES "Inline copies of the tiny leaf functions each file calls in another (tools/inline_leaves.py)" ON)
set(_sasrt_round2_definitions "")
if(NOT SASRT_GEN_NARROW_LOOP_BARRIER)
    list(APPEND _sasrt_round2_definitions REX_LOOP_BARRIER_FULL)
endif()
if(NOT SASRT_GEN_DCBT_PREFETCH)
    list(APPEND _sasrt_round2_definitions "REX_PREFETCH(x,write)=")
endif()
if(SASRT_GEN_VECTOR_LOCALS_BY_VALUE)
    list(APPEND _sasrt_round2_definitions REX_VECTOR_LOCALS_BY_VALUE)
endif()
if(NOT SASRT_GEN_RO_CFG)
    list(APPEND _sasrt_round2_definitions REX_RO_CFG_OFF)
endif()
if(NOT SASRT_GEN_DEAD_DEFS)
    list(APPEND _sasrt_round2_definitions REX_DEAD_DEFS_KEEP)
elseif(SASRT_GEN_DEAD_DEFS_POISON)
    if(REXGLUE_PLATFORM_SWITCH)
        message(FATAL_ERROR "SASRT_GEN_DEAD_DEFS_POISON is a PC test; it must not be in a Switch build")
    endif()
    list(APPEND _sasrt_round2_definitions REX_DEAD_DEFS_POISON)
endif()
if(NOT SASRT_GEN_FLUSH_HOIST)
    list(APPEND _sasrt_round2_definitions REX_FLUSH_HOIST_OFF)
endif()
if(NOT SASRT_GEN_SWITCH_THREAD)
    list(APPEND _sasrt_round2_definitions REX_SWITCH_THREAD_OFF)
endif()
if(NOT SASRT_GEN_LR_WRITE_SAME)
    list(APPEND _sasrt_round2_definitions REX_LR_WRITE_SAME_OFF)
endif()
if(NOT SASRT_GEN_R1_LOCAL)
    list(APPEND _sasrt_round2_definitions REX_R1_LOCAL_OFF)
endif()
if(NOT SASRT_GEN_VSEL_NEON)
    list(APPEND _sasrt_round2_definitions REX_VSEL_OFF)
endif()
if(NOT SASRT_GEN_INLINE_LEAVES)
    list(APPEND _sasrt_round2_definitions REX_INLINE_LEAVES_OFF)
endif()
# The PC build checks the r1 mirror after every call it keeps it across and every link-register write-back proven
# redundant (the '[verify] generated-code self-checks' line of src/sasrt_codegen_checks.cpp).
if(NOT REXGLUE_PLATFORM_SWITCH)
    list(APPEND _sasrt_round2_definitions REX_R1_CHECK REX_LR_WRITE_SAME_CHECK)
endif()
if(NOT SASRT_GEN_VEC_UNALIGNED)
    list(APPEND _sasrt_round2_definitions REX_VEC_UNALIGNED_LOOPS)
endif()
if(NOT SASRT_GEN_INLINE_MEMCALLS)
    list(APPEND _sasrt_round2_definitions REX_INLINE_MEMCALLS_OFF)
endif()
if(NOT SASRT_GEN_SINGLE_FLOATS)
    list(APPEND _sasrt_round2_definitions REX_SINGLE_FLOATS_OFF)
endif()
if(NOT SASRT_GEN_LEAF_DEAD)
    list(APPEND _sasrt_round2_definitions REX_LEAF_DEAD_KEEP)
elseif(SASRT_GEN_LEAF_DEAD_POISON)
    if(REXGLUE_PLATFORM_SWITCH)
        message(FATAL_ERROR "SASRT_GEN_LEAF_DEAD_POISON is a PC test; it must not be in a Switch build")
    endif()
    list(APPEND _sasrt_round2_definitions REX_LEAF_DEAD_POISON)
endif()
if(NOT SASRT_GEN_VPERM1)
    list(APPEND _sasrt_round2_definitions REX_VPERM1_OFF)
endif()
if(NOT SASRT_GEN_FP_SIGN_OPS)
    list(APPEND _sasrt_round2_definitions REX_FP_SIGN_INTEGER)
endif()
if(NOT SASRT_GEN_RO_CONSTANTS)
    list(APPEND _sasrt_round2_definitions REX_RO_CONSTANTS_OFF)
endif()
if(NOT SASRT_GEN_FLOAT_LOADS)
    list(APPEND _sasrt_round2_definitions REX_FLOAT_LOADS_INTEGER)
endif()
if(NOT SASRT_GEN_LOOP_LOCALS)
    list(APPEND _sasrt_round2_definitions REX_LOOP_LOCALS_OFF)
endif()
if(NOT SASRT_GEN_LEAF_LOCALS)
    list(APPEND _sasrt_round2_definitions REX_LEAF_LOCALS_OFF)
endif()
if(NOT SASRT_GEN_COLD_TRAPS)
    list(APPEND _sasrt_round2_definitions "REX_TRAP_ATTR=")
endif()
if(NOT SASRT_GEN_PROMOTED_CALLS)
    list(APPEND _sasrt_round2_definitions REX_PROMOTED_CALLS_OFF)
endif()
# sasrt-nx (2026-11-12, idea 2): the hooked build (the guard's, Ryujinx / PC only) and the PC check each forwarded stack
# load against the real one (tools/stack_forward.py, REX_STACK_FWD_VERIFY): the guard compares copies with the original
# statements, which forward the same way, so it cannot see a wrong forward. The in-place console builds forward only.
if(NOT SASRT_HOT_IN_PLACE)
    list(APPEND _sasrt_round2_definitions REX_STACK_FWD_VERIFY)
endif()
# The game code and the app (whose localized copies are the same generated statements).
foreach(target sasrt_recomp sasrt)
    if(TARGET ${target} AND _sasrt_round2_definitions)
        target_compile_definitions(${target} PRIVATE ${_sasrt_round2_definitions})
    endif()
endforeach()
# PC diagnostic: the game code and the app count the executions of the any-mode float helpers (rex/ppc/diet_ops.h,
# REX_DIET_CENSUS_ON) in counters the app defines (src/sasrt_enhancements.cpp), for the '[census]' lines of
# sasrt_diag_runtime_census. Never the Switch build.
if(NOT REXGLUE_PLATFORM_SWITCH)
    foreach(target sasrt sasrt_recomp)
        if(TARGET ${target})
            target_compile_definitions(${target} PRIVATE REX_DIET_CENSUS_ON)
        endif()
    endforeach()
endif()

if(REXGLUE_PLATFORM_SWITCH)
    # The generated function registration is one function of 135,310 SetFunction calls (7 MB), run once at start.
    # devkitA64's GCC 16 at -O3 did not finish it in 30 minutes (4 GB, 1,737 s of CPU, 2026-10-06; sa2-nx's 1.6 MB one
    # took 927 s): it is compiled without optimisation.
    if(TARGET sasrt_recomp)
        set_source_files_properties("${CMAKE_CURRENT_SOURCE_DIR}/generated/default/sasrt_register.cpp"
            TARGET_DIRECTORY sasrt_recomp PROPERTIES COMPILE_OPTIONS "-O0;-fno-lto")
    endif()
    # Switch compiler optimisations (2026-10-07, sa2-nx's set, its user's choice there: UnleashedRecomp-NX's without
    # PGO, at -O3):
    #   - LTO (nfsmw-nx / UnleashedRecomp-NX): the recompiled game (sasrt_recomp) and the app (renderer, natives) are
    #     compiled to GIMPLE (-flto -fno-fat-lto-objects) and optimised as one program at the link (-flto=N
    #     -flto-partition=balanced: N parallel LTRANS jobs, kept low for the build machine's memory). Calls between
    #     unhooked game functions are direct (tools/direct_calls.py, and since non_argument_as_local also the 127,349
    #     inlined jump-thunk calls), so small game functions inline across files. The SDK libraries stay out, and so
    #     does the registration file above (-O0, -fno-lto).
    #   - -fipa-pta (UnleashedRecomp-NX): interprocedural points-to analysis at the LTO link.
    #   - The link repeats -ffp-contract=off and -fno-strict-aliasing (the LTRANS stage must not fuse what the compile
    #     stage kept apart), and xxHash is built with XXH_FORCE_MEMORY_ACCESS=0: nfsmw-nx's LTO+PGO builds hit
    #     xxHash's default (a strict-aliasing violation) once it was inlined into a cache-key function (garbage keys).
    #   - Hot functions first in .text (nfsmw-nx's orden_funciones.ld): app/hot_functions.ld (tools/hot_order.py). It
    #     starts with KEEP(*(.crt0)): the start-up code must stay at address 0 (tools/check_switch_build.py checks it).
    #   - The user's rule of 2026-10-19: LTO for final builds only. OFF by default; tools\win\build_switch.ps1 -Final
    #     (and build_switch_package.ps1 -Final) turns it on. Without it the game files keep their cross-file calls,
    #     except the tiny leaves tools/inline_leaves.py copies into each calling file.
    option(SASRT_SWITCH_LTO "Link-time optimisation of the game code and the app (Switch; final builds only)" OFF)
    set(SASRT_SWITCH_LTO_JOBS "3" CACHE STRING "Parallel LTRANS jobs of the Switch LTO link (run through make)")
    option(SASRT_SWITCH_IPA_PTA "-fipa-pta at the Switch LTO link" ON)
    option(SASRT_SWITCH_HOT_ORDER "Hot functions first in .text (app/hot_functions.ld)" ON)
    #   - No frame pointer in the game code (2026-10-12): AArch64 GCC keeps the x29 frame chain in every non-leaf
    #     function by default (stp x29, x30 / mov x29, sp; 54,224 recompiled functions set it up), which costs the
    #     set-up instruction and, more, one of the callee-saved registers the recompiled code is short of. Without it:
    #     -1.4 % instructions, -1.8 % loads and -1.7 % stores in the game code (one file, same flags otherwise). The
    #     SDK and the app keep theirs. The console profiler's pc samples are unaffected; its caller chains
    #     (switch_perf.cpp walks x29, bounds-checked) end where they reach a game function.
    #   - The flush-mode checks the control flow fixes compile to nothing here (tools/flush_mode_flow.py);
    #     REX_FLUSH_FLOW_OFF (SASRT_SWITCH_FLUSH_FLOW=OFF) puts the original checks back.
    option(SASRT_SWITCH_OMIT_FRAME_POINTER "Game code without the x29 frame chain (Switch)" ON)
    option(SASRT_SWITCH_FLUSH_FLOW "Flush-mode checks proven by control flow compile to nothing (Switch)" ON)
    if(TARGET sasrt_recomp)
        if(SASRT_SWITCH_OMIT_FRAME_POINTER)
            target_compile_options(sasrt_recomp PRIVATE -fomit-frame-pointer)
            # sasrt-nx (2026-11-12, docs/cpu-moonshots-20-1112.md, the audit's first pick): the localized copies too.
            # They are game code compiled in the app target, which keeps x29: 885 of the 1,074 copies still set up the
            # frame chain (and lose a callee-saved register to it). Profiler caller chains end at a copy, as they do at
            # a generated function.
            if(SASRT_HOT_SOURCES)
                # set_property(SOURCE ${SASRT_HOT_SOURCES} APPEND PROPERTY COMPILE_OPTIONS -fomit-frame-pointer)
                # sasrt-nx (2026-11-13): off again: cycle C flat on process CPU, Main +1.6 % (docs/handoff/batch_cc2/README.md)
            endif()
        endif()
        if(NOT SASRT_SWITCH_FLUSH_FLOW)
            target_compile_definitions(sasrt_recomp PRIVATE REX_FLUSH_FLOW_OFF)
        endif()
    endif()
    if(NOT SASRT_SWITCH_FLUSH_FLOW)
        target_compile_definitions(sasrt PRIVATE REX_FLUSH_FLOW_OFF)
    endif()
    target_compile_definitions(sasrt PRIVATE XXH_FORCE_MEMORY_ACCESS=0)
    # sasrt-nx (2026-11-09, the user: "PGO + LTO, the SDK as well, not only the game code"; rr6-nx's and renut-ultimate's
    # set, from banjo-nx and sa2-nx; docs/pgo-lto.md): the optimised targets are the recompiled game (sasrt_recomp), the
    # app (sasrt: the natives and the localized copies), Renut's renderer (sasrt_renut_gpu, its objects) and plume, and
    # (SASRT_SWITCH_SDK_OPT, renut-ultimate 2026-11-07) the SDK runtime (kernel calls, threads, the audio driver) and
    # FFmpeg (XMA decoding), their C and C++ only. They were out only because every build folder shared the SDK's
    # libraries (REXGLUE_OUTPUT_IN_BUILD above). Before: the game code and the app alone.
    set(_sasrt_opt_targets sasrt_recomp sasrt sasrt_renut_gpu plume)
    option(SASRT_SWITCH_SDK_OPT "The SDK runtime and FFmpeg in the Switch LTO and PGO (renut-ultimate)" ON)
    set(_sasrt_sdk_opt_targets)
    if(SASRT_SWITCH_SDK_OPT AND REXGLUE_OUTPUT_IN_BUILD)
        set(_sasrt_sdk_opt_targets rexruntime libavcodec libavutil)
        # sasrt-nx (2026-11-11, batch B1; Blur's finding): the SDK's OBJECT libraries are compiled with their own options,
        # so they had no LTO and no PGO (rexaudio's XMA context, the kernel's core, the file system, input, the UI and
        # the profiler). In now; the two files that define --wrap functions stay out of LTO (the linker must see their
        # __wrap_ symbols as ordinary definitions).
        option(SASRT_SWITCH_SDK_OBJECT_OPT "The SDK's OBJECT libraries in the Switch LTO and PGO too" ON)
        if(SASRT_SWITCH_SDK_OBJECT_OPT)
            list(APPEND _sasrt_sdk_opt_targets rexaudio rexcore rexfilesystem rexinput rexui)
            # and the two whose top-level assembly names symbols (the exception handler's g_rex_exc_*, the fiber
            # trampoline): LTO cannot see those references and dropped the symbols (batch B's first link)
            set(_sasrt_wrap_sources
                "${CMAKE_CURRENT_SOURCE_DIR}/../sdk/src/core/threading_switch.cpp"
                "${CMAKE_CURRENT_SOURCE_DIR}/../sdk/src/ui/switch_perf.cpp"
                "${CMAKE_CURRENT_SOURCE_DIR}/../sdk/src/core/exception_handler_switch.cpp"
                "${CMAKE_CURRENT_SOURCE_DIR}/../sdk/src/core/fiber_switch.cpp")
        endif()
    endif()
    if(SASRT_SWITCH_LTO)
        set(_sasrt_lto_compile -flto -fno-fat-lto-objects)
        set(_sasrt_lto_link -flto=${SASRT_SWITCH_LTO_JOBS} -flto-partition=balanced -ffp-contract=off
            -fno-strict-aliasing)
        if(SASRT_SWITCH_IPA_PTA)
            list(APPEND _sasrt_lto_compile -fipa-pta)
            list(APPEND _sasrt_lto_link -fipa-pta)
        endif()
        foreach(target ${_sasrt_opt_targets})
            if(TARGET ${target})
                target_compile_options(${target} PRIVATE ${_sasrt_lto_compile})
                target_compile_definitions(${target} PRIVATE XXH_FORCE_MEMORY_ACCESS=0)
            endif()
        endforeach()
        foreach(target ${_sasrt_sdk_opt_targets})
            if(TARGET ${target})
                target_compile_options(${target} PRIVATE "$<$<COMPILE_LANGUAGE:C,CXX>:${_sasrt_lto_compile}>")
                target_compile_definitions(${target} PRIVATE XXH_FORCE_MEMORY_ACCESS=0)
            endif()
        endforeach()
        target_link_options(sasrt PRIVATE ${_sasrt_lto_link})
        # sasrt-nx (2026-11-11, batch B1): the --wrap definitions out of LTO
        if(_sasrt_wrap_sources)
            set_property(SOURCE ${_sasrt_wrap_sources} TARGET_DIRECTORY rexcore rexui APPEND PROPERTY COMPILE_OPTIONS -fno-lto)
        endif()
        message(STATUS "sasrt: Switch LTO on (${SASRT_SWITCH_LTO_JOBS} LTRANS jobs, -fipa-pta ${SASRT_SWITCH_IPA_PTA}; "
                       "targets ${_sasrt_opt_targets} ${_sasrt_sdk_opt_targets})")
    endif()
    # sasrt-nx (2026-11-09): profile-guided optimisation (rr6-nx's BANJO_PGO, from sa2-nx):
    #   - SASRT_PGO=generate: an instrumented NRO that streams its branch counts to pgo/ next to the NRO
    #     (src/sasrt_pgo.cpp; registered in a section, not by constructors: libgcov's exit-time files do not fit the
    #     Switch). Value profiling is off: its shared lists are not safe without atomic updates.
    #   - SASRT_PGO=use: the counts merged on the PC (tools/pgo_merge.py) from SASRT_PGO_DIR (pgo/ at the root): one
    #     .gcda per object, named by the object's path in the build folder with # for each separator
    #     (-fprofile-prefix-path), so the instrumented and the optimised builds may use different build folders. Code
    #     the sessions did not run is compiled as without a profile (-fprofile-partial-training); functions changed
    #     since keep no profile (-Wno-coverage-mismatch). GCC instruments before its interprocedural inliner, so the
    #     instrumented build needs no LTO: only the sources and the compile options must match.
    #   - With a profile, the game code's inliner limits (sa2-nx's measurements): max-inline-insns-auto 64 and
    #     inline-unit-growth 12.
    set(SASRT_SWITCH_INLINE_AUTO "64" CACHE STRING "max-inline-insns-auto of the game code with a profile (empty: GCC's)")
    set(SASRT_SWITCH_INLINE_UNIT_GROWTH "12" CACHE STRING "inline-unit-growth of the game code with a profile (empty: GCC's)")
    set(SASRT_PGO "" CACHE STRING "Profile-guided optimisation of the Switch build: empty, generate or use")
    set_property(CACHE SASRT_PGO PROPERTY STRINGS "" generate use)
    set(SASRT_PGO_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../pgo" CACHE PATH "Folder of the PGO profile (.gcda files)")
    get_filename_component(_sasrt_pgo_dir "${SASRT_PGO_DIR}" ABSOLUTE)
    file(TO_NATIVE_PATH "${_sasrt_pgo_dir}" _sasrt_pgo_dir)
    file(TO_NATIVE_PATH "${CMAKE_BINARY_DIR}" _sasrt_pgo_prefix)
    if(SASRT_PGO STREQUAL "generate")
        set(_sasrt_pgo "-fprofile-generate=${_sasrt_pgo_dir}" "-fprofile-prefix-path=${_sasrt_pgo_prefix}"
                       -fno-profile-values -fprofile-update=single -fprofile-info-section=gcov_info)
        target_compile_definitions(sasrt PRIVATE SASRT_PGO_GENERATE=1)
    elseif(SASRT_PGO STREQUAL "use")
        if(NOT EXISTS "${SASRT_PGO_DIR}")
            message(FATAL_ERROR "SASRT_PGO=use: no profile in ${SASRT_PGO_DIR}")
        endif()
        # -fprofile-correction: counts taken without atomic updates while several threads ran the same code.
        set(_sasrt_pgo "-fprofile-use=${_sasrt_pgo_dir}" "-fprofile-prefix-path=${_sasrt_pgo_prefix}"
                       -fprofile-correction -fno-profile-values -fprofile-partial-training -Wno-missing-profile
                       -Wno-coverage-mismatch)
        set(_sasrt_inline_options "")
        if(SASRT_SWITCH_INLINE_AUTO)
            list(APPEND _sasrt_inline_options --param=max-inline-insns-auto=${SASRT_SWITCH_INLINE_AUTO})
        endif()
        if(SASRT_SWITCH_INLINE_UNIT_GROWTH)
            list(APPEND _sasrt_inline_options --param=inline-unit-growth=${SASRT_SWITCH_INLINE_UNIT_GROWTH})
        endif()
        if(_sasrt_inline_options AND TARGET sasrt_recomp)
            target_compile_options(sasrt_recomp PRIVATE ${_sasrt_inline_options})
            set_property(SOURCE ${SASRT_HOT_SOURCES} TARGET_DIRECTORY sasrt APPEND PROPERTY COMPILE_OPTIONS
                         ${_sasrt_inline_options})
        endif()
    elseif(SASRT_PGO)
        message(FATAL_ERROR "SASRT_PGO must be empty, generate or use (got ${SASRT_PGO})")
    endif()
    if(SASRT_PGO)
        foreach(target ${_sasrt_opt_targets})
            if(TARGET ${target})
                target_compile_options(${target} PRIVATE ${_sasrt_pgo})
            endif()
        endforeach()
        foreach(target ${_sasrt_sdk_opt_targets})
            if(TARGET ${target})
                target_compile_options(${target} PRIVATE "$<$<COMPILE_LANGUAGE:C,CXX>:${_sasrt_pgo}>")
            endif()
        endforeach()
        target_link_options(sasrt PRIVATE ${_sasrt_pgo})
        message(STATUS "sasrt: PGO ${SASRT_PGO} (${SASRT_PGO_DIR})")
    endif()
    if(SASRT_SWITCH_HOT_ORDER AND EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/hot_functions.ld")
        target_link_options(sasrt PRIVATE "-Wl,--section-ordering-file,${CMAKE_CURRENT_SOURCE_DIR}/hot_functions.ld")
        set_property(TARGET sasrt APPEND PROPERTY LINK_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/hot_functions.ld")
    endif()
    # Link map: which function each sampled pc of the console profile belongs to (tools/switch_hot_functions.py;
    # futari-nx's profiler, docs/switch-testing.md).
    target_link_options(sasrt PRIVATE "LINKER:-Map=${CMAKE_BINARY_DIR}/sasrt.map")
    # 2026-11-22, the user: "please make the version 1.0.0 and this image the icon ... make the author
    # ChanseyIsTheBest". A plain variable (a cache entry before: an existing build tree kept its 0.1.0); icon.jpg is the
    # user's image (Downloads, sonic-and-all-stars-racing-transformed-button), 256x256 JPEG as hbmenu takes it.
    set(SASRT_VERSION "1.0.0")
    rexglue_switch_add_nro(sasrt
        NAME "Sonic & All-Stars Racing Transformed"  # 2026-11-22, the user; the NACP is made without a shell
        AUTHOR "ChanseyIsTheBest"
        VERSION "${SASRT_VERSION}"
        ICON "${CMAKE_CURRENT_SOURCE_DIR}/icon.jpg")
endif()

if(REXGLUE_PLATFORM_SWITCH AND NOT BANJO_SWITCH_DIAG_CENSUS AND TARGET sasrt_renut_gpu)  # base port 236 (banjo-nx, 2026-11-20), see the option above
    target_compile_definitions(sasrt_renut_gpu PRIVATE RENUT_DIAG_CENSUS_OFF)
    target_compile_definitions(sasrt PRIVATE RENUT_DIAG_CENSUS_OFF)
endif()

if(REXGLUE_PLATFORM_SWITCH AND BANJO_SWITCH_RENUT_DEBUG_INFO AND TARGET sasrt_renut_gpu)  # base port 239
    target_compile_options(sasrt_renut_gpu PRIVATE -g)
    target_compile_options(plume PRIVATE -g)
    target_link_options(sasrt PRIVATE -g)  # LTO: the link writes the late debug info of the units compiled with -g
endif()
