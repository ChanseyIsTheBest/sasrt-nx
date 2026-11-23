p = r'D:/sonic transformed/sasrt-nx/app/src/renut_engine/gpu/render/draw.cpp'
s = open(p, encoding='utf-8').read()
old = '''  SetDrawDepthBias(cmd, dev);  // rr6-nx (2026-11-03, rr6_depth_bias)
  float blend_constant[4];
  if (f.blend_used && DrawBlendConstant(dev, *f.kp, blend_constant) &&'''
new = '''  // rr6-nx (2026-11-03, rr6_depth_bias). sasrt-nx (2026-11-20, sasrt_rt3_depth_bias_fields; the third render-thread
  // round's #31): not called when the bias set is still bound and none of the packets it reads changed since the draw
  // before in the chain (its mode control in the view packets, its words in the point packet, kFieldMisc, the depth
  // info in the destination packet): it would read three cold lines of the snapshot to set what is set.
  if (!(g_bound.depth_bias_set && !(fields & (kFieldDest | kFieldViewPackets | kFieldMisc)) &&
        sasrt::gpu_round::On(sasrt::gpu_round::kRt3DepthBiasFields)))
    SetDrawDepthBias(cmd, dev);
  else
    sasrt::gpu_round::Count(sasrt::gpu_round::kRt3DepthBiasFields);
  float blend_constant[4];
  if (f.blend_used && DrawBlendConstant(dev, *f.kp, blend_constant) &&'''
assert s.count(old) == 1
s = s.replace(old, new)
open(p, 'w', encoding='utf-8').write(s)
print('ok')
