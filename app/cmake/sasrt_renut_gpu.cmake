# sasrt-nx (2026-10-20, from sa2-nx's cmake/sa2_renut_gpu.cmake, retargeted by tools/renut_from_sa2.py): Renut's Direct3D-level renderer (github.com/masterspike52/reNut, as banjo-nx carries it in
# src/renut_engine/gpu, retargeted to SA2's Direct3D: docs/renut-renderer.md), chosen at boot with
# sasrt_renderer = "renut" (src/renut_engine/gpu/banjo_renut_select.h). From banjo-nx's cmake/banjo_renut_gpu.cmake: Renut's
# gpu.cmake as banjo-nx uses it, with its dependencies where it looks for them: thirdparty/plume (with banjo-nx's deko3d
# back end), thirdparty/reblue-XenosRecomp (the translator, DXC, zstd, smol-v, xxHash), thirdparty/imgui,
# cmake/collect_captured_shaders.cmake.
#
# An OBJECT library, not a static one: its hooks replace the generated code's weak sub_X definitions, and a static
# archive's members are only pulled in for undefined symbols, so the hooks would silently not be linked.

# The shader containers its shader cache is built from: the game's shader containers (out/shaders/in: this port's
# draw-time and memory-scan dumps, sasrt_dump_shaders). A normal variable, so it shadows gpu.cmake's cache entry.
set(RENUT_SHADER_DUMP_DIR "${CMAKE_SOURCE_DIR}/../out/renut_shader_dump")
set(RENUT_ASSETS_DIR "${CMAKE_SOURCE_DIR}/assets" CACHE PATH "Game assets (default.xex and Bundle/)")

# Renut's XenosRecomp is built as an ExternalProject (gpu.cmake): it gets this build's whole host toolchain, not only
# the compiler paths (tools/renut_gpu_import.py adds the variable to gpu.cmake). On the PC, clang for the MSVC ABI.
set(BANJO_RENUT_XENOS_RECOMP_ARGS "")
foreach(_banjo_var CMAKE_C_COMPILER_TARGET CMAKE_CXX_COMPILER_TARGET CMAKE_LINKER_TYPE CMAKE_C_FLAGS CMAKE_CXX_FLAGS
                   CMAKE_AR CMAKE_RC_COMPILER CMAKE_MT)
    if(DEFINED ${_banjo_var} AND NOT "${${_banjo_var}}" STREQUAL "")
        list(APPEND BANJO_RENUT_XENOS_RECOMP_ARGS "-D${_banjo_var}=${${_banjo_var}}")
    endif()
endforeach()

# Renut's SDK exports o1heap as rex::o1heap; banjo-nx's SDK fork names it o1heap.
if(TARGET o1heap AND NOT TARGET rex::o1heap)
    add_library(rex::o1heap ALIAS o1heap)
endif()

# The Switch build is a cross build on a Windows host: Renut's XenosRecomp (a host tool) cannot be built with the
# console's compiler. Its shader cache comes from a PC build of the same tree (tools/renut_switch_shader_cache.py
# writes a copy without the DXIL arrays, which only Windows reads).
if(REXGLUE_PLATFORM_SWITCH)
    # plume's Switch backend (UnleashedRecomp-NX's patches, thirdparty/plume): VK_NN_vi_surface on libnx's window and
    # Mesa's static NVK, the same driver the SDK links (REXGLUE_SWITCH_NVK_SDK).
    set(PLUME_PLATFORM_SWITCH ON CACHE BOOL "" FORCE)
    set(PLUME_SWITCH_DEVKITPRO "${DEVKITPRO}" CACHE PATH "" FORCE)
    set(PLUME_SWITCH_NVK_ROOT "${REXGLUE_SWITCH_NVK_SDK}" CACHE PATH "" FORCE)
    set(PLUME_SWITCH_NVK_LIBRARY "${REXGLUE_SWITCH_NVK_SDK}/lib/libvulkan.a" CACHE FILEPATH "" FORCE)
    # banjo-nx (2026-10-17): plume's deko3d back end (renut_gpu_backend = "deko3d", docs/deko3d-renderer.md) and the
    # uam it compiles shader variants with on the console.
    set(PLUME_SWITCH_UAM_DIR "${CMAKE_SOURCE_DIR}/thirdparty/uam" CACHE PATH "" FORCE)
    set(PLUME_DEKO3D ON CACHE BOOL "deko3d back end (Switch)" FORCE)
    # The host shaders' deko3d blobs (gpu.cmake renut_host_shader) need the PC tools tools/deko3d_build_tools.sh builds.
    set(BANJO_DEKO3D_HOST_SHADERS ON)
    set(BANJO_DEKO3D_SPIRV_CROSS "${CMAKE_SOURCE_DIR}/../out/deko3d_tools/spirv-cross-build/spirv-cross.exe" CACHE FILEPATH
        "SPIRV-Cross for the deko3d host shaders (tools/deko3d_build_tools.sh)")
    set(BANJO_DEKO3D_UAM "${CMAKE_SOURCE_DIR}/../out/deko3d_tools/uam-build/uam.exe" CACHE FILEPATH
        "uam (thirdparty/uam built for the PC) for the deko3d host shaders (tools/deko3d_build_tools.sh)")
    foreach(_banjo_tool BANJO_DEKO3D_SPIRV_CROSS BANJO_DEKO3D_UAM)
        if(NOT EXISTS "${${_banjo_tool}}")
            message(FATAL_ERROR "No ${${_banjo_tool}}: run tools/deko3d_build_tools.sh first")
        endif()
    endforeach()
    # sasrt-nx (2026-11-22, the user: the web installer makes the shaders in the browser; the base's option, from
    # katamari-nx / futari-nx): the release build (tools/renut_release_shaders.py, app/out/renut_switch_release): no
    # translated game shader in the NRO but the ones the game makes at runtime (its --only), the shader table without
    # SPIR-V; the others come from deko3d_glsl.bin beside the NRO, which sasrt-nx-installer makes from the player's
    # files. OFF (the everyday build): every translated shader built in (app/out/renut_switch).
    option(BANJO_RENUT_RELEASE_SHADERS "Switch: no translated game shader in the NRO (deko3d_glsl.bin beside it)" OFF)
    if(BANJO_RENUT_RELEASE_SHADERS)
        set(_sasrt_renut_shaders "${CMAKE_SOURCE_DIR}/out/renut_switch_release")
    else()
        set(_sasrt_renut_shaders "${CMAKE_SOURCE_DIR}/out/renut_switch")
    endif()
    # The game shaders' GLSL for deko3d (tools/deko3d_shader_package.py), embedded next to the SPIR-V cache.
    set(BANJO_DEKO3D_GLSL_CPP "${_sasrt_renut_shaders}/deko3d_glsl_switch.cpp" CACHE FILEPATH
        "The deko3d GLSL package's source (tools/deko3d_shader_package.py)" FORCE)
    set(BANJO_RENUT_SHADER_CACHE_CPP "${_sasrt_renut_shaders}/shader_cache_switch.cpp" CACHE FILEPATH
        "Renut's shader cache for the Switch build (from a PC build: tools/renut_switch_shader_cache.py)" FORCE)
    function(banjo_renut_shader_cache_override TARGET)
        if(NOT EXISTS "${BANJO_RENUT_SHADER_CACHE_CPP}")
            message(FATAL_ERROR "No ${BANJO_RENUT_SHADER_CACHE_CPP}: build the PC tree first, then run "
                                "tools/renut_switch_shader_cache.py (Renut's XenosRecomp runs on the host)")
        endif()
        target_sources(${TARGET} PRIVATE "${BANJO_RENUT_SHADER_CACHE_CPP}")
        set_source_files_properties("${BANJO_RENUT_SHADER_CACHE_CPP}" PROPERTIES SKIP_PRECOMPILE_HEADERS ON)
    endfunction()
endif()

# sa2-nx: the shader steps run Python (the early alpha pass, and the host shaders' deko3d blobs on the Switch build):
# found here too, as the Switch configure has no generator target that would find it first.
if(NOT Python3_EXECUTABLE)
    find_package(Python3 COMPONENTS Interpreter REQUIRED)
endif()
if(NOT PYTHON_EXECUTABLE)
    set(PYTHON_EXECUTABLE "${Python3_EXECUTABLE}")
endif()

# sasrt-nx (2026-10-20): no early alpha pass (banjo_gpu_early_alpha) for now: Renut's XenosRecomp fails fast in its
# first (HLSL dump only) run over this game's 2,031 shaders, while the plain run translates every one. An optimisation
# only: the shaders are the same without it.
set(BANJO_RENUT_EARLY_ALPHA OFF CACHE BOOL "Early alpha copies in Renut's pixel shaders (tools/renut_early_alpha.py)" FORCE)
include("${CMAKE_SOURCE_DIR}/src/renut_engine/gpu/gpu.cmake")

add_library(sasrt_renut_gpu OBJECT
    "${CMAKE_SOURCE_DIR}/src/renut_engine/gpu/banjo_renut_select.cpp"
    "${CMAKE_SOURCE_DIR}/src/renut_engine/gpu/banjo_renut_tuning.cpp"
    "${CMAKE_SOURCE_DIR}/src/renut_engine/gpu/banjo_renut_checks.cpp"
    "${CMAKE_SOURCE_DIR}/src/renut_engine/gpu/banjo_renut_record.cpp"
    # sasrt-nx (2026-11-08, the move to D:/renut-ultimate): the base's ported fixes' switches (renut-ultimate's ultimate.cpp).
    "${CMAKE_SOURCE_DIR}/src/renut_engine/gpu/ultimate.cpp"
    "${CMAKE_SOURCE_DIR}/src/renut_engine/gpu/sasrt_gpu_round.cpp"  # sasrt-nx (2026-11-08): the GPU round
    # banjo-nx (2026-10-19, latency batch 3): the display's refresh for the frame limiter (it reads the presents' fences)
    "${CMAKE_SOURCE_DIR}/src/renut_engine/display_sync.cpp"
    "${CMAKE_SOURCE_DIR}/src/renut_engine/perf/frame_stats.cpp"
    # sa2-nx: banjo-nx's SDK and generated-code pieces the renderer uses (the frame latency probe from futari-nx, the
    # store cards switched off), app-side here.
    "${CMAKE_SOURCE_DIR}/src/renut_engine/sasrt_compat/frame_latency.cpp"
    "${CMAKE_SOURCE_DIR}/src/renut_engine/sasrt_compat/sasrt_compat.cpp"
    "${CMAKE_SOURCE_DIR}/src/renut_engine/sasrt_compat/sasrt_store_cards.cpp"  # sasrt-nx (2026-10-20)
    # sasrt-nx: this game's Renut hooks beyond sa2-nx's (recorded command buffers, predicated tiling).
    "${CMAKE_SOURCE_DIR}/src/renut_engine/sasrt_renut_hooks.cpp"
    # sasrt-nx (2026-11-08, sasrt_renut_diag_trace): the frame's thread timeline (the far-cascade flicker).
    "${CMAKE_SOURCE_DIR}/src/renut_engine/sasrt_trace.cpp"
    # sa2-nx's frame pacing at the game's presentation interval (no vblank with no ring).
    "${CMAKE_SOURCE_DIR}/src/renut_engine/gpu/sasrt_renut_pacing.cpp")
target_include_directories(sasrt_renut_gpu PRIVATE
    "${CMAKE_SOURCE_DIR}"
    "${CMAKE_SOURCE_DIR}/src"
    # sa2-nx: banjo-nx's headers the renderer's tuning includes, answered by SA2's (cpu/banjo_enhancements.h, ...).
    "${CMAKE_SOURCE_DIR}/src/renut_engine/sasrt_compat"
    "${REXGLUE_ENTRYPOINT_INCLUDE_DIR}"
    # banjo_renut_tuning.cpp: the Switch thread helpers (threading_switch.h, through src/me/me_platform_compat.h).
    "${REXSDK_DIR}/src/core")
target_link_libraries(sasrt_renut_gpu PRIVATE rex::runtime)
if(REXGLUE_PLATFORM_SWITCH)
    # banjo-nx (2026-10-17): the deko3d back end's glue and the game shaders' GLSL package (docs/deko3d-renderer.md).
    target_sources(sasrt_renut_gpu PRIVATE "${CMAKE_SOURCE_DIR}/src/renut_engine/gpu/banjo_renut_deko3d.cpp")
    if(EXISTS "${BANJO_DEKO3D_GLSL_CPP}")
        target_sources(sasrt_renut_gpu PRIVATE "${BANJO_DEKO3D_GLSL_CPP}")
        set_source_files_properties("${BANJO_DEKO3D_GLSL_CPP}" PROPERTIES SKIP_PRECOMPILE_HEADERS ON)
    elseif(BANJO_RENUT_RELEASE_SHADERS)
        message(STATUS "sasrt: no GLSL package in the NRO (BANJO_RENUT_RELEASE_SHADERS): deko3d_glsl.bin beside it")
    else()
        message(WARNING "No ${BANJO_DEKO3D_GLSL_CPP}: renut_gpu_backend = deko3d will have no game shaders "
                        "(tools/deko3d_shader_package.py)")
    endif()
endif()
if(COMMAND rexglue_apply_target_settings)
    rexglue_apply_target_settings(sasrt_renut_gpu)
endif()
renut_gpu_setup(sasrt_renut_gpu)
# banjo-nx (2026-10-23, render-thread round; taken 2026-10-29): the draw path's function-local statics (cvars read once:
# about 15 a draw, StoreCards / PhysicalOf at every page check) without the thread-safe guard, whose fast path is a
# load-acquire (LDARB) that holds back every later load on the A57. Sound here: these files run on the render thread; the
# one other caller (the content verifier thread's hashes) reaches only statics that every thread initialises to the
# same pointer.
# sasrt-nx (2026-11-20, the second render-thread round's #10): ultimate.cpp (the switches' accessors the draw path calls
# out of line, about 40 of them, each a function static) and backend/render_thread.cpp (the ring's switches) too. Every
# function static in both is a plain value read from a key: a thread that races another to the first read computes the
# same value.
if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
    set_property(SOURCE
        "${CMAKE_SOURCE_DIR}/src/renut_engine/gpu/render/draw.cpp"
        "${CMAKE_SOURCE_DIR}/src/renut_engine/gpu/guest/command_buffers.cpp"
        "${CMAKE_SOURCE_DIR}/src/renut_engine/gpu/ultimate.cpp"
        "${CMAKE_SOURCE_DIR}/src/renut_engine/gpu/backend/render_thread.cpp"
        # sasrt-nx (2026-11-20, the third render-thread round's #33): the tuning switches' ~35 out-of-line accessors
        # (DepthHandOverSampledOn and its kind: 0.3 % of the render thread); its one non-trivial static, the A/B list,
        # under std::call_once.
        "${CMAKE_SOURCE_DIR}/src/renut_engine/gpu/banjo_renut_tuning.cpp"
        TARGET_DIRECTORY sasrt_renut_gpu APPEND PROPERTY COMPILE_OPTIONS "-fno-threadsafe-statics")
endif()
# banjo-nx (2026-10-28; taken 2026-10-29): SASRT_SWITCH_RENDERER_LINES gives Renut's hot render-thread files line tables
# (-g1), so a console profile's samples name source lines. Debug info only: the generated code is the same.
option(SASRT_SWITCH_RENDERER_LINES "Line tables for Renut's hot render-thread files (Switch)" OFF)
if(REXGLUE_PLATFORM_SWITCH AND SASRT_SWITCH_RENDERER_LINES)
    set_property(SOURCE
        "${CMAKE_SOURCE_DIR}/src/renut_engine/gpu/render/draw.cpp"
        "${CMAKE_SOURCE_DIR}/src/renut_engine/gpu/render/textures.cpp"
        "${CMAKE_SOURCE_DIR}/src/renut_engine/gpu/render/surfaces.cpp"
        "${CMAKE_SOURCE_DIR}/src/renut_engine/gpu/guest/command_buffers.cpp"
        "${CMAKE_SOURCE_DIR}/src/renut_engine/gpu/backend/queued.cpp"  # sasrt-nx (2026-11-09, render-thread round)
        TARGET_DIRECTORY sasrt_renut_gpu APPEND PROPERTY COMPILE_OPTIONS "-g1")
    # sasrt-nx (2026-11-20): with LTO the code is made at the link, which writes the line tables only when it has -g
    # itself (the compile's -g1 alone gave the hot functions no lines). Debug info only: the code is the same.
    if(SASRT_SWITCH_LTO)
        target_link_options(sasrt PRIVATE -g1)
    endif()
endif()
target_compile_definitions(sasrt_renut_gpu PRIVATE SASRT_RENUT_RENDERER=1)
# The game's hooks into it (src/me, src/cpu: renut_engine/sasrt_renut_yield.h) and the app's wiring (sasrt_app.h).
target_link_libraries(sasrt PRIVATE sasrt_renut_gpu)
target_compile_definitions(sasrt PRIVATE SASRT_RENUT_RENDERER=1)
