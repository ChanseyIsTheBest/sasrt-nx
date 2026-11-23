#include "utility.hlsli"

struct PSInput
{
    float4 position : SV_Position;
    float2 uv : TEXCOORD0;
};

float4 main(PSInput input) : SV_Target0
{
    // kameo-nx (2026-11-03): all ones in the sampler index: the frame covers the output one to one (present.cpp), so
    // this pixel is that texel, what the filter gives at its centre.
    float4 color = g_Push.samplerIndex == 0xFFFFFFFFu
                       ? g_Textures[NonUniformResourceIndex(g_Push.textureIndex)].Load(int3(int2(input.position.xy), 0))
                       : SampleBindless(g_Push.textureIndex, g_Push.samplerIndex, input.uv);
    // param0 = output gamma exponent. kameo-nx (2026-11-03): exactly 1 skips the pow: an 8-bit value goes through it within
    // far less than half a level, and the ramp's index and the output are 8-bit. Negative: its size, with the pow.
    color.rgb = saturate(color.rgb);
    if (g_Push.param0 != 1.0)
        color.rgb = pow(color.rgb, abs(g_Push.param0));
    // banjo-nx (2026-10-20, banjo_renut_game_gamma): param1's bits = the bindless slot of the gamma ramp the game loaded
    // (256 x 1, its red, green and blue entries over 1023; 0 = none), looked up by the 8-bit value as the 360's display
    // does. The slot goes in as raw bits: Ryujinx follows a bindless handle only back to a constant buffer load, so one
    // computed from a float read zero (black) there (the SA2 port's finding).
    // sasrt-nx (2026-11-08, sasrt_gpu_identity_ramp): 1 = the linear ramp at an 8-bit target: the level itself
    // (present.cpp: the ramp's entry would store the same level).
    const uint ramp = asuint(g_Push.param1);
    if (ramp == 1u)
    {
        const uint3 i = uint3(saturate(color.rgb) * 255.0 + 0.5);
        color.rgb = float3(i) / 255.0;
    }
    else if (ramp != 0u)
    {
        const uint3 i = uint3(saturate(color.rgb) * 255.0 + 0.5);
        color.rgb = float3(g_Textures[NonUniformResourceIndex(ramp)].Load(int3(i.x, 0, 0)).x,
                           g_Textures[NonUniformResourceIndex(ramp)].Load(int3(i.y, 0, 0)).y,
                           g_Textures[NonUniformResourceIndex(ramp)].Load(int3(i.z, 0, 0)).z);
    }
    // param0 = output gamma exponent (1 = passthrough). sa2-nx: skipped at 1, where pow's exp2(log2) could move a
    // value by an ulp.
    if (g_Push.param0 != 1.0)
        color.rgb = pow(saturate(color.rgb), g_Push.param0);
    return float4(color.rgb, 1.0);
}
