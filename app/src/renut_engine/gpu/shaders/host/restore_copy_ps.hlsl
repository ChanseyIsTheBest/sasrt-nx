// sasrt-nx (2026-11-09, sasrt_gpu_depth_restore_direct; the fifth GPU round): SASRT's EDRAM depth restore copy (pixel shader
// A393B1E0F77E8311) as its 1x variant computes it, for a colour target whose copy draw was left out and that something other
// than the depth restore then uses (render/draw.cpp SasrtMaterialiseCopyLocked). The game's shader (Renut's translation):
//   p = gl_FragCoord.xy - 0.5 - pixel origin (0, 0), x times +-1 by the face (abs below drops it)
//   u = abs(p.x) + (fract(abs(p.x) * c255.w) >= 0.5 ? -40 : 40), v = abs(p.y)     (c255 = 40, -40, 0.5, 0.0125)
//   colour = texture(fetch 0, (u, v) / its size).zyxw
// with the same texture view and sampler as the draw had. Drawn with present_vs over the copy draw's scissor.
//   g_Push.textureIndex / samplerIndex : the draw's fetch 0 view and sampler
//   g_Push.scale                       : that texture's size (the txq the shader divides by)
//   g_Push.param0                      : c255.w (0.0125)
//   g_Push.param1                      : the copy draw's resolution scale (sasrt-nx 2026-11-11: the game's translation
//                                        divides gl_FragCoord by the shared constants' scale, v[83].z; 1 at 1x)
#include "utility.hlsli"

float4 main(float4 position : SV_Position) : SV_Target
{
    const float2 p = position.xy / g_Push.param1 - 0.5;
    const float ax = abs(p.x);
    const float u = frac(ax * g_Push.param0) >= 0.5 ? ax - 40.0 : ax + 40.0;
    const float2 uv = float2(u, abs(p.y)) / g_Push.scale;
    return SampleBindless(g_Push.textureIndex, g_Push.samplerIndex, uv).zyxw;
}
