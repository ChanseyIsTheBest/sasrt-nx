ROOT = r'D:/sonic transformed/sasrt-nx/app/src/renut_engine/gpu/'


def edit(path, old, new, count=1):
    p = ROOT + path
    s = open(p, encoding='utf-8').read()
    assert s.count(old) == count, (path, s.count(old), old[:80])
    s = s.replace(old, new)
    open(p, 'w', encoding='utf-8').write(s)


edit('render/textures.cpp', '''std::unordered_map<u32, HostTexture *> g_resolve_targets;''', '''std::unordered_map<u32, HostTexture *> g_resolve_targets;
// sasrt-nx (2026-11-20, the menus' flash; the user: "can you fix the ocean flash in the menus"): the resolve destinations
// a page's entry held before the current one (two at most, newest first). SASRT's menu resolves an RGBA8 1152x544 image
// and an FP16 one of the same size into the same memory (headers B5640DA8 and B5640C28, page 07845); with the RGBA8 one
// the page's entry, the FP16 read found another format, ResolvedAlias said no, and the texture was made from guest
// memory, which the GPU never wrote: a frame of garbage once a run, ~frame 900 ("[flash] ... made from guest memory over
// resolve destination B5640DA8" in every log). The read now takes the earlier destination of its own description.
REXCVAR_DEFINE_BOOL(sasrt_resolve_alias_previous, true, "SASRT/Graphics",
                    "A texture read of memory a resolve wrote, in another format than the page's latest resolve, takes "
                    "an earlier resolve destination of that page with its own description (format, size, memory) instead "
                    "of a texture made from guest memory the GPU never wrote (the menus' one-frame flash, 2026-11-20)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
std::unordered_map<u32, std::array<HostTexture *, 2>> g_resolve_targets_previous;''')

# the retire: out of the previous lists too
edit('render/textures.cpp', '''  if (t.render_target)
    std::erase_if(g_resolve_targets, [&t](const auto &entry) { return entry.second == &t; });
}''', '''  if (t.render_target) {
    std::erase_if(g_resolve_targets, [&t](const auto &entry) { return entry.second == &t; });
    for (auto it = g_resolve_targets_previous.begin(); it != g_resolve_targets_previous.end();) {  // sasrt-nx (2026-11-20)
      auto &p = it->second;
      if (p[1] == &t)
        p[1] = nullptr;
      if (p[0] == &t) {
        p[0] = p[1];
        p[1] = nullptr;
      }
      it = p[0] ? std::next(it) : g_resolve_targets_previous.erase(it);
    }
  }
}''')

# the page's entry replaced: the old one kept
edit('render/textures.cpp', '''  HostTexture *&entry = g_resolve_targets[fetch.BasePage()];
  if (entry != slot.get()) {
    entry = slot.get();''', '''  HostTexture *&entry = g_resolve_targets[fetch.BasePage()];
  if (entry != slot.get()) {
    static const bool keep_previous = REXCVAR_GET(sasrt_resolve_alias_previous);
    if (keep_previous && entry) {  // sasrt-nx (2026-11-20, the menus' flash)
      auto &p = g_resolve_targets_previous[fetch.BasePage()];
      if (p[0] != entry) {
        p[1] = p[0] == slot.get() ? p[1] : p[0];
        p[0] = entry;
      }
      if (p[1] == slot.get() || p[1] == p[0])
        p[1] = nullptr;
    }
    entry = slot.get();''')

# the read: an earlier destination of its own description
edit('render/textures.cpp', '''    if (half && (twins(a, b) || twins(b, a)) && ((resolved->desc[1] ^ desc[1]) & ~kFormatBits) == 0 &&
        resolved->desc[2] == desc[2] && ((resolved->desc[5] ^ desc[5]) & kDimensionMask) == 0) {
      static uint32_t logged = 0;
      if (logged++ < 8)
        RGPU_INFO("[renut] texture {:08X} (format {}) reads resolve destination {:08X} ({}x{} format {}) through its "
                  "texture (blur_renut_expand_alias)", texture_va, b, resolved->guest_va, resolved->width,
                  resolved->height, a);
      return resolved;
    }
  }
  return nullptr;
}''', '''    if (half && (twins(a, b) || twins(b, a)) && ((resolved->desc[1] ^ desc[1]) & ~kFormatBits) == 0 &&
        resolved->desc[2] == desc[2] && ((resolved->desc[5] ^ desc[5]) & kDimensionMask) == 0) {
      static uint32_t logged = 0;
      if (logged++ < 8)
        RGPU_INFO("[renut] texture {:08X} (format {}) reads resolve destination {:08X} ({}x{} format {}) through its "
                  "texture (blur_renut_expand_alias)", texture_va, b, resolved->guest_va, resolved->width,
                  resolved->height, a);
      return resolved;
    }
  }
  // sasrt-nx (2026-11-20, sasrt_resolve_alias_previous: the menus' flash): an earlier destination of this page with the
  // read's own description (the same memory, format, size and dimension), whose image holds that resolve's content.
  if (!g_resolve_targets_previous.empty()) {
    auto p = g_resolve_targets_previous.find(fetch.BasePage());
    if (p != g_resolve_targets_previous.end()) {
      for (HostTexture *earlier : p->second) {
        if (earlier && earlier->texture && earlier->guest_va != texture_va && SameData(earlier->desc, desc)) {
          static uint32_t logged = 0;
          if (logged++ < 16)
            RGPU_INFO("[sasrt] texture {:08X} (format {}) reads the earlier resolve destination {:08X} ({}x{}) of its "
                      "page, not the latest {:08X} (format {}) (sasrt_resolve_alias_previous)", texture_va,
                      u32(fetch.Format()), earlier->guest_va, earlier->width, earlier->height, resolved->guest_va,
                      u32(resolved->guest_format));
          return earlier;
        }
      }
    }
  }
  return nullptr;
}''')
print('ok')
