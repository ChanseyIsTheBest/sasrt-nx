// sasrt-nx (2026-11-09, sasrt_gpu_depth_restore_direct; the fifth GPU round): the EDRAM depth restore straight from the depth
// resolve. 2026-11-09 (after console run G): FUSED. The first form read the resolve's float target at the pixel; the
// console's check (sasrt_gpu_diag_restore_verify) found 60 % of the texels differ from the old chain, whose copy samples the
// words at texel corners ((pixel) / size, not (pixel + 0.5) / size), which the hardware's point sampling can take to the
// neighbour. Now this shader computes exactly what the old chain gives a pixel: the pixel depth_restore_ps reads (the other
// 40-pixel half of its tile column), what A393B1E0 drew there (restore_copy_ps's arithmetic, with the copy draw's own words
// view, sampler and size: the console's check found it equal to the game's draw on every texel), stored as RGBA8 (bytes
// rounded as the target stores them) and decoded as depth_restore_ps decodes it. The colour target's round trip is gone.
//   g_Push.textureIndex / samplerIndex : the copy draw's fetch 0 view (the resolve's words) and sampler
//   g_Push.scale                       : the copy's texture size (the txq it divides by)
//   g_Push.translate                   : the colour target's size: a pixel the old restore would read outside it reads 0
// (the rest of this comment is the first form's) Sonic Transformed restores its scene depth for the light pass (and again for the composite) by drawing the depth
// resolve's words as colour (A393B1E0: the 40-pixel halves of each 80-pixel EDRAM tile column swapped) into the EDRAM the
// depth then sits in; depth_restore_ps turns that colour back into depth, the halves swapped back. Words are made from the
// float (depth_resolve.hlsli: SV_Target0 the float, SV_Target1 the word, both from the same load), so the restored depth is
// the float's word decoded: this pass reads the resolve's float target and computes that, with the same encode and decode
// (EncodeUnorm24 / EncodeFloat20e4 as depth_resolve.hlsli writes them, the decode as depth_restore_ps). Drawn with present_vs.
//   g_Push.textureIndex : the depth resolve's float target (R32_FLOAT, an unswizzled view)
//   g_Push.translate    : the texel's offset from the pixel (0)
//   g_Push.param0       : 1 for D24FS8 (20e4 float depth), 0 for D24S8
//   g_Push.param1       : sasrt-nx (2026-11-09, sasrt_gpu_depth_restore_clear_skip): >= 0: the depth the target was
//                         cleared to; a pixel whose restored depth is exactly that is discarded (it keeps the clear)
// DEPTH_RESTORE_DIRECT_COLOR 1: the same value as a colour (sasrt_gpu_diag_restore_verify's R32_FLOAT copy).
#include "utility.hlsli"

uint EncodeUnorm24(float depth)
{
    return uint(saturate(depth) * 16777215.0 + 0.5);
}

uint EncodeFloat20e4(float depth)
{
    const float d = clamp(depth, 0.0, 1.99999988);
    if (d < 6.103515625e-5) // 2^-14
        return uint(d * 17179869184.0); // 2^34
    const uint bits = asuint(d);
    return (((bits >> 23) - 112) << 20) | ((bits >> 3) & 0xFFFFF);
}

float DecodeFloat20e4(uint value)
{
    const uint exponent = value >> 20;
    const uint mantissa = value & 0xFFFFF;
    if (exponent == 0)
        return float(mantissa) * (1.0 / 17179869184.0);
    return asfloat(((exponent + 112) << 23) | (mantissa << 3));
}

#if DEPTH_RESTORE_DIRECT_COLOR
float main(float4 position : SV_Position) : SV_Target
#else
float main(float4 position : SV_Position) : SV_Depth
#endif
{
    // depth_restore_ps: the colour texel at the other 40-pixel half of the pixel's 80-pixel EDRAM tile column
    int2 texel = int2(position.xy);
    texel.x += (texel.x % 80) < 40 ? 40 : -40;
    uint word = 0;
    [branch] if (texel.x >= 0 && texel.x < int(g_Push.translate.x) && texel.y < int(g_Push.translate.y))
    {
        // restore_copy_ps (A393B1E0) at that pixel: p = its gl_FragCoord - 0.5
        const float2 p = float2(texel);
        const float ax = abs(p.x);
        const float u = frac(ax * 0.0125) >= 0.5 ? ax - 40.0 : ax + 40.0;
        const float2 uv = float2(u, abs(p.y)) / g_Push.scale;
        const float4 c = SampleBindless(g_Push.textureIndex, g_Push.samplerIndex, uv).zyxw;
        // stored in the RGBA8 target, read back by depth_restore_ps
        const uint4 b = uint4(round(saturate(c) * 255.0));
        word = b.x | (b.y << 8) | (b.z << 16) | (b.w << 24);
    }
    const uint depth24 = word >> 8;
    const float restored = g_Push.param0 != 0.0 ? DecodeFloat20e4(depth24) : float(depth24) * (1.0 / 16777215.0);
#if !DEPTH_RESTORE_DIRECT_COLOR
    if (g_Push.param1 >= 0.0 && restored == g_Push.param1)
        discard;
#endif
    return restored;
}
