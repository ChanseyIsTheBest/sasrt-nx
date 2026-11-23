ROOT = r'D:/sonic transformed/sasrt-nx/app/src/renut_engine/gpu/'


def edit(path, old, new, count=1):
    p = ROOT + path
    s = open(p, encoding='utf-8').read()
    assert s.count(old) == count, (path, s.count(old), old[:80])
    s = s.replace(old, new)
    open(p, 'w', encoding='utf-8').write(s)


# 1. the memo's generation and whether this draw's answers are the memo's
edit('render/draw.cpp', '''SasrtSpecMemo g_spec_memo;
[[gnu::always_inline]] inline void SasrtSpecAnswersOf(''', '''SasrtSpecMemo g_spec_memo;
// sasrt-nx (2026-11-20, sasrt_rt4_spec_key_skip; the third table's #27): the memo's answers' generation (one more at each
// store) and whether the last call's answers are the memo's (a hit).
uint64_t g_spec_memo_gen = 1;
bool g_spec_memo_hit = false, g_spec_memo_stored = false;
// A count of every pipeline key written where the fast path keeps a pointer to one (the cache's entries, FastState::key).
uint64_t g_sasrt_key_writes = 0;
[[gnu::always_inline]] inline void SasrtSpecAnswersOf(''')
edit('render/draw.cpp', '''  SasrtSpecMemo &m = g_spec_memo;
  if (memo && m.valid && (g_sc_dirty_seen | g_sc_dirty) == 0 && m.vs == &vs && m.vs_entry == vs.entry &&''',
     '''  SasrtSpecMemo &m = g_spec_memo;
  g_spec_memo_hit = g_spec_memo_stored = false;
  if (memo && m.valid && (g_sc_dirty_seen | g_sc_dirty) == 0 && m.vs == &vs && m.vs_entry == vs.entry &&''')
edit('render/draw.cpp', '''          out.fetch = fetch;
          out.plain = plain;
          out.clip = clip;
          out.words = words;
          m.a = out;
        }
      }
      return;''', '''          out.fetch = fetch;
          out.plain = plain;
          out.clip = clip;
          out.words = words;
          m.a = out;
          ++g_spec_memo_gen;
        }
      }
      g_spec_memo_hit = true;
      return;''')
edit('render/draw.cpp', '''  if (memo) {
    m.valid = true;
    m.per_instance = per_instance;''', '''  if (memo) {
    ++g_spec_memo_gen;
    g_spec_memo_stored = true;
    m.valid = true;
    m.per_instance = per_instance;''')

# 2. FastState: the key last checked against the memo's answers
edit('render/draw.cpp', '''  const PipelineKey *kp = nullptr;''', '''  const PipelineKey *kp = nullptr;
  // sasrt-nx (2026-11-20, sasrt_rt4_spec_key_skip): kp as last checked against the spec memo's answers of generation
  // spec_ok_gen, with g_sasrt_key_writes then.
  const PipelineKey *spec_ok_kp = nullptr;
  uint64_t spec_ok_gen = 0, spec_ok_writes = 0;''')

# 3. the key's writes counted
edit('render/draw.cpp', '''        c.key = MakeKey(device, vs, ps, declaration, targets, call.primitive, geometry.per_instance, sc.booleans,''',
     '''        ++g_sasrt_key_writes;  // sasrt-nx (2026-11-20, sasrt_rt4_spec_key_skip)
        c.key = MakeKey(device, vs, ps, declaration, targets, call.primitive, geometry.per_instance, sc.booleans,''')
edit('render/draw.cpp', '''      f.key = key;
      f.kp = &f.key;
      f.kp_hot = KeyHot::Of(key);
      f.blend_used = true;
      f.pipeline = made;''', '''      ++g_sasrt_key_writes;  // sasrt-nx (2026-11-20, sasrt_rt4_spec_key_skip)
      f.key = key;
      f.kp = &f.key;
      f.kp_hot = KeyHot::Of(key);
      f.blend_used = true;
      f.pipeline = made;''')
edit('render/draw.cpp', '''  (void)fetches;
  f.key = key;
  f.kp = &f.key;  // banjo-nx (2026-10-27)''', '''  (void)fetches;
  ++g_sasrt_key_writes;  // sasrt-nx (2026-11-20, sasrt_rt4_spec_key_skip)
  f.key = key;
  f.kp = &f.key;  // banjo-nx (2026-10-27)''')

# 4. the check: the spec fields of the kept key compared only when not known to match
edit('render/draw.cpp', '''  const bool key_inputs = f.key_rs_epoch != f.rs_epoch || !f.pipeline || !f.kp || depth_only != f.depth_only ||
                          std::memcmp(f.kp->sasrt_words, spec_words.w, sizeof(spec_words.w)) != 0 ||  // sasrt-nx
                          misc != f.key_misc || f.prebuild_epoch != prebuild_epoch ||
                          f.kp->fetch_pad != (f.kp->pixel_shader ? plain_fetches : 0u) ||
                          (f.kp->reserved & 8u) != clip_bit ||  // sasrt-nx (2026-11-08, sasrt_gpu_clip_spec)
                          ((shaders_changed || (fields & kFieldDecl)) &&
                           (vs->entry != f.kp->vertex_shader || ps_entry != f.kp->pixel_shader ||
                            declaration->layout_hash != f.kp->layout_hash || ab_off == 41)) ||  // A/B 41: as before
                          FetchSpecDiffers(*f.kp, fetch_spec);  // banjo_gpu_fetch_spec; vivapinata-nx (2026-11-12): every draw''',
     '''  // sasrt-nx (2026-11-20, sasrt_rt4_spec_key_skip; the third table's #27): the spec answers are the memo's of the
  // generation the kept key was last checked against, and no key was written since: its spec fields match them still.
  const bool spec_known = g_spec_memo_hit && f.kp && f.kp == f.spec_ok_kp && f.spec_ok_gen == g_spec_memo_gen &&
                          f.spec_ok_writes == g_sasrt_key_writes &&
                          sasrt::gpu_round::On(sasrt::gpu_round::kRt4SpecKeySkip);
  const bool key_inputs = f.key_rs_epoch != f.rs_epoch || !f.pipeline || !f.kp || depth_only != f.depth_only ||
                          misc != f.key_misc || f.prebuild_epoch != prebuild_epoch ||
                          (!spec_known &&
                           (std::memcmp(f.kp->sasrt_words, spec_words.w, sizeof(spec_words.w)) != 0 ||  // sasrt-nx
                            f.kp->fetch_pad != (f.kp->pixel_shader ? plain_fetches : 0u) ||
                            (f.kp->reserved & 8u) != clip_bit ||  // sasrt-nx (2026-11-08, sasrt_gpu_clip_spec)
                            FetchSpecDiffers(*f.kp, fetch_spec))) ||  // banjo_gpu_fetch_spec; vivapinata-nx: every draw
                          ((shaders_changed || (fields & kFieldDecl)) &&
                           (vs->entry != f.kp->vertex_shader || ps_entry != f.kp->pixel_shader ||
                            declaration->layout_hash != f.kp->layout_hash || ab_off == 41));  // A/B 41: as before
  if (spec_known)
    sasrt::gpu_round::Count(sasrt::gpu_round::kRt4SpecKeySkip);''')

# 5. after the key (and its verify): the kept key matches this draw's answers
edit('render/draw.cpp', '''  plume::RenderPipeline *pipeline = f.pipeline;
  if (!pipeline)
    return -1;
#if defined(PLUME_DEKO3D)
  // banjo-nx (2026-10-27, deko3d recording): a pipeline to bind: its draw-time lines, while the targets, the refresh''',
     '''  // sasrt-nx (2026-11-20, sasrt_rt4_spec_key_skip): the kept key now matches this draw's spec answers (compared, or
  // found or made with them); known for the next draw when they are the memo's.
  if (g_spec_memo_hit || g_spec_memo_stored) {
    f.spec_ok_kp = f.kp;
    f.spec_ok_gen = g_spec_memo_gen;
    f.spec_ok_writes = g_sasrt_key_writes;
  } else {
    f.spec_ok_kp = nullptr;
  }
  plume::RenderPipeline *pipeline = f.pipeline;
  if (!pipeline)
    return -1;
#if defined(PLUME_DEKO3D)
  // banjo-nx (2026-10-27, deko3d recording): a pipeline to bind: its draw-time lines, while the targets, the refresh''')
print('ok')
