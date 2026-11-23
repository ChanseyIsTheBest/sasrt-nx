ROOT = r'D:/sonic transformed/sasrt-nx/app/'
p = ROOT + 'src/renut_engine/gpu/banjo_renut_tuning.cpp'
s = open(p, encoding='utf-8').read()
old = '''const std::vector<int> &AbTargets() {
  static const std::vector<int> list = [] {
    std::vector<int> v;'''
new = '''const std::vector<int> &AbTargets() {
  // sasrt-nx (2026-11-20, the third render-thread round's #33): built under std::call_once, as this file is compiled
  // without thread-safe statics (its ~35 switch accessors' guards, a load-acquire each at every call).
  static std::once_flag once;
  static std::vector<int> list;
  std::call_once(once, [] { list = [] {
    std::vector<int> v;'''
assert s.count(old) == 1
s = s.replace(old, new)
old = '''        n = 0;
        digit = false;
      }
    }
    return v;
  }();
  return list;
}
// The target the A/B switches now (requires g_stats.mutex).'''
new = '''        n = 0;
        digit = false;
      }
    }
    return v;
  }(); });
  return list;
}
// The target the A/B switches now (requires g_stats.mutex).'''
assert s.count(old) == 1
s = s.replace(old, new)
if '#include <mutex>' not in s:
    i = s.index('#include <')
    s = s[:i] + '#include <mutex>  // sasrt-nx (2026-11-20): std::call_once\n' + s[i:]
open(p, 'w', encoding='utf-8').write(s)

p = ROOT + 'cmake/sasrt_renut_gpu.cmake'
s = open(p, encoding='utf-8').read()
old = '''        "${CMAKE_SOURCE_DIR}/src/renut_engine/gpu/backend/render_thread.cpp"
        TARGET_DIRECTORY sasrt_renut_gpu APPEND PROPERTY COMPILE_OPTIONS "-fno-threadsafe-statics")'''
new = '''        "${CMAKE_SOURCE_DIR}/src/renut_engine/gpu/backend/render_thread.cpp"
        # sasrt-nx (2026-11-20, the third render-thread round's #33): the tuning switches' ~35 out-of-line accessors
        # (DepthHandOverSampledOn and its kind: 0.3 % of the render thread); its one non-trivial static, the A/B list,
        # under std::call_once.
        "${CMAKE_SOURCE_DIR}/src/renut_engine/gpu/banjo_renut_tuning.cpp"
        TARGET_DIRECTORY sasrt_renut_gpu APPEND PROPERTY COMPILE_OPTIONS "-fno-threadsafe-statics")'''
assert s.count(old) == 1
s = s.replace(old, new)
open(p, 'w', encoding='utf-8').write(s)
print('ok')
