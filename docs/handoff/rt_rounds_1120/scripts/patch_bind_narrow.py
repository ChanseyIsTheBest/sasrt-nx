# The second render-thread round, batch 2: #14 (sasrt_rt2_bind_layout_narrow).
p = r'D:/sonic transformed/sasrt-nx/app/src/renut_engine/gpu/render/draw.cpp'
s = open(p, encoding='utf-8').read()
old = '''  if (targets_changed || !g_bound.framebuffer || g_bound.framebuffer != f.bound_framebuffer ||
      f.bind_layout_epoch != g_layout_epoch || f.framebuffer_epoch != FramebufferEpochLocked() ||'''
new = '''  // sasrt-nx (2026-11-20, sasrt_rt2_bind_layout_narrow; the second render-thread round's #14): a layout change somewhere
  // since the last bind (g_layout_epoch moves at every transition: a texture made readable, any target) binds the targets
  // again only when this draw's own targets are not all in the layouts BindTargets would leave them in, or hold
  // something BindTargets does first (a pending restore copy, a hand-over); else nothing it does would change anything.
  const auto layouts_hold = [&] {
    if (!sasrt::gpu_round::On(sasrt::gpu_round::kRt2BindLayoutNarrow) || gpu_profile::Timed())
      return false;
    for (u32 i = 0; i < targets.color_count; ++i) {
      const HostSurface *c = targets.colors[i];
      if (c->layout != plume::RenderTextureLayout::COLOR_WRITE || c->handed || c->sasrt_copy_pending)
        return false;
    }
    if (const HostSurface *d = targets.depth) {
      if (d->handed)
        return false;
      if (d->layout != plume::RenderTextureLayout::DEPTH_WRITE &&
          (fast_depth_writes || d->layout != plume::RenderTextureLayout::SHADER_READ ||
           !banjo::renut_gpu::DepthReadLayoutOn()))
        return false;
    }
    sasrt::gpu_round::Count(sasrt::gpu_round::kRt2BindLayoutNarrow);
    f.bind_layout_epoch = g_layout_epoch;
    return true;
  };
  if (targets_changed || !g_bound.framebuffer || g_bound.framebuffer != f.bound_framebuffer ||
      (f.bind_layout_epoch != g_layout_epoch && !layouts_hold()) || f.framebuffer_epoch != FramebufferEpochLocked() ||'''
assert s.count(old) == 1
s = s.replace(old, new)
open(p, 'w', encoding='utf-8').write(s)
print('ok')
