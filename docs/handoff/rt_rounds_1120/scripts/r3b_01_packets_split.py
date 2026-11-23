ROOT = r'D:/sonic transformed/sasrt-nx/app/src/renut_engine/gpu/'


def edit(path, old, new):
    p = ROOT + path
    s = open(p, encoding='utf-8').read()
    assert s.count(old) == 1, (path, old[:70])
    s = s.replace(old, new)
    open(p, 'w', encoding='utf-8').write(s)


edit('render/draw.cpp', '''inline bool HostPacketsOn() {
  static const bool on = REXCVAR_GET(banjo_renut_host_packets);
  return on;
}''', '''inline bool HostPacketsOn() {
  static const bool on = REXCVAR_GET(banjo_renut_host_packets);
  // sasrt-nx (2026-11-20, sasrt_rt3_host_packets_split; the third render-thread round's #1): also while the screen is
  // split (the composites' count of the frame before: g_sasrt_split_views), where the views replay the same state words
  // (an in-run A/B of banjo_renut_host_packets in four players, run 317: about -4 % of the render thread at equal
  // draws). One player keeps the key's own answer (off by default: neutral there).
  return on || (g_sasrt_split_views.load(std::memory_order_relaxed) > 1 &&
                sasrt::gpu_round::On(sasrt::gpu_round::kRt3HostPacketsSplit));
}''')

edit('guest/command_buffers.cpp', '''  return REXCVAR_GET(banjo_renut_host_packets) || REXCVAR_GET(banjo_renut_diag_packet_census);''',
     '''  // sasrt-nx (2026-11-20): sasrt_rt3_host_packets_split's draws need the keys too (the recording makes them always then).
  return REXCVAR_GET(banjo_renut_host_packets) || REXCVAR_GET(banjo_renut_diag_packet_census) ||
         REXCVAR_GET(sasrt_rt3_host_packets_split);''')
edit('guest/command_buffers.cpp', '''REXCVAR_DECLARE(bool, banjo_renut_host_packets);  // banjo-nx (2026-10-28): render/draw.cpp''',
     '''REXCVAR_DECLARE(bool, banjo_renut_host_packets);  // banjo-nx (2026-10-28): render/draw.cpp
REXCVAR_DECLARE(bool, sasrt_rt3_host_packets_split);  // sasrt-nx (2026-11-20): sasrt_gpu_round.cpp''')
print('ok')
