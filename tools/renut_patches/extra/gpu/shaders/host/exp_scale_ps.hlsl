// sasrt-nx (2026-10-20): a texture fetch constant's exponent adjust (its dword 3, bits 13-18): the console scales what
// the fetch returns by 2^adjust. Host samplers cannot, so a fetch with an adjust reads a copy of the texture's base
// level made by this pass (render/draw.cpp, ExpAdjustedSlotLocked): each texel of the source at the same host texel,
// times the factor. present_vs draws the fullscreen triangle.
//   g_Push.textureIndex : the source texture's slot (the bound view: the fetch swizzle applied)
//   g_Push.param0       : 2^adjust
#include "utility.hlsli"

float4 main(float4 position : SV_Position) : SV_Target
{
    const int2 texel = int2(position.xy);
    return g_Textures[NonUniformResourceIndex(g_Push.textureIndex)].Load(int3(texel, 0)) * g_Push.param0;
}
