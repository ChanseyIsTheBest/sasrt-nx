# rexaudio - Audio subsystem library
# Audio processing and XMA decoding for Xbox 360 emulation

add_library(rexaudio OBJECT
    
    audio_driver.cpp
    audio_system.cpp
    downmix.cpp
    xma_context.cpp
    xma_decoder.cpp
    xma_register_file.cpp
    xmo_opus.cpp  # culdcept-nx (2026-11-20): Opus for NAME.xmo frames
    # NOP backend (always available)
    nop/nop_audio_system.cpp
)
add_library(rex::audio ALIAS rexaudio)
if(REXGLUE_PLATFORM_SWITCH)
    # libnx audout backend
    target_sources(rexaudio PRIVATE switch/switch_audio_system.cpp)
else()
    # SDL backend
    target_sources(rexaudio PRIVATE sdl/sdl_audio_system.cpp sdl/sdl_audio_driver.cpp)
endif()

rex_target_pch(rexaudio
    <mutex>
    <rex/math.h>
    <rex/string.h>
    <rex/memory.h>
    <rex/filesystem.h>
    <rex/thread.h>
    <rex/thread/mutex.h>
    <rex/ppc/context.h>
    <rex/system/kernel_state.h>
    <rex/system/xthread.h>
)

target_include_directories(rexaudio PUBLIC
    $<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>
)

target_link_libraries(rexaudio
    PUBLIC rexcore
    PRIVATE libavcodec libavutil
)
if(NOT REXGLUE_PLATFORM_SWITCH)
    target_link_libraries(rexaudio PUBLIC SDL3::SDL3)
endif()

# culdcept-nx (2026-11-20): xmo_opus.cpp's libopus (BSD-3): devkitPro's portlibs build on the Switch (a PC loads one at
# run time).
if(REXGLUE_PLATFORM_SWITCH)
    set(_rex_opus_pl "$ENV{DEVKITPRO}/portlibs/switch")
    if(DEFINED DEVKITPRO)
        set(_rex_opus_pl "${DEVKITPRO}/portlibs/switch")
    endif()
    if(NOT EXISTS "${_rex_opus_pl}/lib/libopus.a")
        message(FATAL_ERROR "libopus not found in ${_rex_opus_pl} (devkitPro's switch-libopus)")
    endif()
    target_include_directories(rexaudio PRIVATE "${_rex_opus_pl}/include/opus")
    target_link_libraries(rexaudio PUBLIC "${_rex_opus_pl}/lib/libopus.a")
endif()
