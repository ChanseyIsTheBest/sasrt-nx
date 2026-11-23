p = r'D:/sonic transformed/sasrt-nx/app/cmake/sasrt_renut_gpu.cmake'
s = open(p, encoding='utf-8').read()
old = '''if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
    set_property(SOURCE
        "${CMAKE_SOURCE_DIR}/src/renut_engine/gpu/render/draw.cpp"
        "${CMAKE_SOURCE_DIR}/src/renut_engine/gpu/guest/command_buffers.cpp"
        TARGET_DIRECTORY sasrt_renut_gpu APPEND PROPERTY COMPILE_OPTIONS "-fno-threadsafe-statics")
endif()'''
new = '''# sasrt-nx (2026-11-20, the second render-thread round's #10): ultimate.cpp (the switches' accessors the draw path calls
# out of line, about 40 of them, each a function static) and backend/render_thread.cpp (the ring's switches) too. Every
# function static in both is a plain value read from a key: a thread that races another to the first read computes the
# same value.
if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
    set_property(SOURCE
        "${CMAKE_SOURCE_DIR}/src/renut_engine/gpu/render/draw.cpp"
        "${CMAKE_SOURCE_DIR}/src/renut_engine/gpu/guest/command_buffers.cpp"
        "${CMAKE_SOURCE_DIR}/src/renut_engine/gpu/ultimate.cpp"
        "${CMAKE_SOURCE_DIR}/src/renut_engine/gpu/backend/render_thread.cpp"
        TARGET_DIRECTORY sasrt_renut_gpu APPEND PROPERTY COMPILE_OPTIONS "-fno-threadsafe-statics")
endif()'''
assert s.count(old) == 1
s = s.replace(old, new)
open(p, 'w', encoding='utf-8').write(s)
print('ok')
