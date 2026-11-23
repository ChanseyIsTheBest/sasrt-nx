ROOT = r'D:/sonic transformed/sasrt-nx/app/src/renut_engine/gpu/'


def edit(path, old, new):
    p = ROOT + path
    s = open(p, encoding='utf-8').read()
    assert s.count(old) == 1, (path, old[:80])
    s = s.replace(old, new)
    open(p, 'w', encoding='utf-8').write(s)


# host_batch: the census and verify switches in the latched block, read inline.
edit('host_batch.h', '''struct Switches {
  bool on[kItemCount] = {};
};''', '''struct Switches {
  bool on[kItemCount] = {};
  // sasrt-nx (2026-11-20, the second render-thread round's #9): blur_renut_diag_batch_census and
  // blur_renut_host_batch_verify latched here, read inline (out-of-line functions with a thread-safe static each, read
  // several times a draw).
  bool census = false, verify = false;
};''')
edit('host_batch.h', '''bool CensusOn();
// blur_renut_host_batch_verify (off): #3, #13 and #32 checked against the old way, differences logged.
bool VerifyOn();''', '''[[gnu::always_inline]] inline bool CensusOn() {
  if (!g_ready.load(std::memory_order_relaxed)) [[unlikely]]
    LatchSwitches();
  return g_switches.census;
}
// blur_renut_host_batch_verify (off): #3, #13 and #32 checked against the old way, differences logged.
[[gnu::always_inline]] inline bool VerifyOn() {
  if (!g_ready.load(std::memory_order_relaxed)) [[unlikely]]
    LatchSwitches();
  return g_switches.verify;
}''')
edit('banjo_renut_tuning.cpp', '''  s.on[kMeshGenWhole] = REXCVAR_GET(blur_renut_mesh_gen_whole_only);
  g_switches = s;''', '''  s.on[kMeshGenWhole] = REXCVAR_GET(blur_renut_mesh_gen_whole_only);
  s.census = REXCVAR_GET(blur_renut_diag_batch_census);  // sasrt-nx (2026-11-20)
  s.verify = REXCVAR_GET(blur_renut_host_batch_verify);
  g_switches = s;''')
edit('banjo_renut_tuning.cpp', '''bool CensusOn() {
  static const bool on = REXCVAR_GET(blur_renut_diag_batch_census);
  return on;
}
bool VerifyOn() {
  static const bool on = REXCVAR_GET(blur_renut_host_batch_verify);
  return on;
}
''', '')
# stage census: On() latched inline.
edit('stage_census.h', '''bool On();  // blur_renut_diag_stage_census (banjo_renut_tuning.cpp), read once
''', '''// blur_renut_diag_stage_census (banjo_renut_tuning.cpp), read once. sasrt-nx (2026-11-20, the second render-thread
// round's #9): latched and read inline (an out-of-line call with a thread-safe static at each Scope, several a draw).
extern bool g_on;
extern std::atomic<bool> g_on_ready;
[[gnu::cold, gnu::noinline]] void LatchOn();
[[gnu::always_inline]] inline bool On() {
  if (!g_on_ready.load(std::memory_order_relaxed)) [[unlikely]]
    LatchOn();
  return g_on;
}
''')
edit('banjo_renut_tuning.cpp', '''bool On() {
  static const bool on = REXCVAR_GET(blur_renut_diag_stage_census);
  return on;
}
std::string Report(double seconds) {''', '''bool g_on = false;
std::atomic<bool> g_on_ready{false};
void LatchOn() {
  g_on = REXCVAR_GET(blur_renut_diag_stage_census);
  g_on_ready.store(true, std::memory_order_release);
}
std::string Report(double seconds) {''')
print('ok')
