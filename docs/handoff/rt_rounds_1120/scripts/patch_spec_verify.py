p = r'D:/sonic transformed/sasrt-nx/app/src/renut_engine/gpu/render/draw.cpp'
s = open(p, encoding='utf-8').read()
old = '''    if (same) {
      out = m.a;
      sasrt::gpu_round::Count(sasrt::gpu_round::kRt2SpecMemo);
      return;
    }
  }'''
new = '''    if (same) {
      out = m.a;
      sasrt::gpu_round::Count(sasrt::gpu_round::kRt2SpecMemo);
      // banjo_renut_fast_draw_verify: the kept answers against fresh ones (the pipeline check below uses these).
      static const bool verify = REXCVAR_GET(banjo_renut_fast_draw_verify);
      if (verify) [[unlikely]] {
        const FetchSpec fetch = FetchSpecWords(sc, vs, per_instance, ab_off);
        const u32 plain = SasrtPlainFetchMask(sc, ps_entry, vs.entry);
        const u32 clip = SasrtClipBit(sc);
        const SasrtSpecWords words = SasrtSpecWordsOf(sc, vs.entry, ps_entry, &vsc, &targets);
        if (std::memcmp(&fetch, &out.fetch, sizeof(fetch)) != 0 || plain != out.plain || clip != out.clip ||
            std::memcmp(&words, &out.words, sizeof(words)) != 0) {
          static uint32_t logged = 0;
          if (logged++ < 16)
            RGPU_WARN("sasrt_rt2_spec_memo (banjo_renut_fast_draw_verify): the kept spec answers differ (fetch {} "
                      "plain {:08X}/{:08X} clip {}/{} words {}; VS {:016X})",
                      std::memcmp(&fetch, &out.fetch, sizeof(fetch)) != 0, out.plain, plain, out.clip, clip,
                      std::memcmp(&words, &out.words, sizeof(words)) != 0, vs.hash);
          out.fetch = fetch;
          out.plain = plain;
          out.clip = clip;
          out.words = words;
          m.a = out;
        }
      }
      return;
    }
  }'''
assert s.count(old) == 1
s = s.replace(old, new)
open(p, 'w', encoding='utf-8').write(s)
print('ok')
