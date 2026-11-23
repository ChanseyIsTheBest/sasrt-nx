// sasrt-nx (2026-11-09, sasrt_gpu_diag_restore_verify; the fifth GPU round): two textures compared texel by texel over a
// rectangle, for the check of sasrt_gpu_depth_restore_direct against the restore it replaces. Counts go to the readback
// buffer at destOffset: +0 rectangles compared, +4 texels compared, +8 texels that differ, +12..+28 the first that differed
// (x, y, A's first word, B's first word, then A's and B's other words' xor).
//   set 0 : bindless Texture2D table (t0, space0)
//   set 1 : RWByteAddressBuffer      (u0, space1)
//   push  : ComparePush              (b0, space2), in target_readback_cs's layout
//   mode  : 0 the first channel's bits (a depth plane, R32_FLOAT), 1 all four channels' bits, 2 A's first channel
//           against the constant in textureB, 5 as 0 and, for a texel that differs, which of B's neighbours A matches
//           (+36 + 4 * k: dx, dy in -1..1 as k = 0..8, k 9 / 10: dx -40 / +40, k 11: none of them),
//           7 A's first three channels' bits against the constants textureB, x0, y0 (sasrt_gpu_diag_take_cover: a
//           sentinel; the rectangle starts at 0, 0), 8 the same and A's fourth channel against textureB too,
//           9 the first channel's bits of A at the id plus (x0, y0) against B's at the id (sasrt_gpu_diag_atlas_verify)

struct ComparePush
{
    uint textureA;
    uint textureB;
    uint width;
    uint height;
    uint destOffset;
    uint mode;
    uint x0;
    uint y0;
};

#ifdef __spirv__
[[vk::push_constant]] ConstantBuffer<ComparePush> g_Push;
#else
ConstantBuffer<ComparePush> g_Push : register(b0, space2);
#endif

Texture2D<float4> g_Textures[] : register(t0, space0);
RWByteAddressBuffer g_Out : register(u0, space1);

[numthreads(8, 8, 1)]
void main(uint3 id : SV_DispatchThreadID)
{
    if (id.x == 0 && id.y == 0 && g_Push.mode < 11)  // sasrt-nx (2026-11-21): modes 11-13 are copies, no counts
    {
        g_Out.InterlockedAdd(g_Push.destOffset + 0, 1);
        g_Out.InterlockedAdd(g_Push.destOffset + 4, g_Push.width * g_Push.height);
        if (g_Push.mode >= 7)  // sasrt_gpu_diag_take_cover: the size of the target last checked
            g_Out.Store2(g_Push.destOffset + 52, uint2(g_Push.width, g_Push.height));
    }
    if (id.x >= g_Push.width || id.y >= g_Push.height)
        return;
    const uint2 origin = (g_Push.mode == 7 || g_Push.mode == 8) ? uint2(0, 0) : uint2(g_Push.x0, g_Push.y0);
    const int3 p = int3(int(id.x + origin.x), int(id.y + origin.y), 0);
    const int3 pb = g_Push.mode == 9 ? int3(int(id.x), int(id.y), 0) : p;
    uint4 a = asuint(g_Textures[NonUniformResourceIndex(g_Push.textureA)].Load(p));
    // sasrt-nx (2026-11-20, sasrt_renut_diag_view_stats): mode 10, A's first channel as a float, counted in bins at
    // +64: 16 over [0, 1), then <= 0 (16) and >= 1 (17); and at +160 eight fine bins over [0.99, 1).
    // sasrt-nx (2026-11-21, sasrt_renut_diag_view_dump): copies of A's texels at destOffset, row by row: 11 the first
    // channel's bits (4 bytes a texel), 12 four channels as unorm8 (r least significant), 13 all four channels' bits.
    [branch] if (g_Push.mode >= 11)
    {
        const uint i = id.y * g_Push.width + id.x;
        if (g_Push.mode == 11)
            g_Out.Store(g_Push.destOffset + 4 * i, a.x);
        else if (g_Push.mode == 12)
        {
            const uint4 b8 = uint4(round(saturate(asfloat(a)) * 255.0));
            g_Out.Store(g_Push.destOffset + 4 * i, b8.x | (b8.y << 8) | (b8.z << 16) | (b8.w << 24));
        }
        else
            g_Out.Store4(g_Push.destOffset + 16 * i, a);
        return;
    }
    [branch] if (g_Push.mode == 10)
    {
        const float v = asfloat(a.x);
        const uint bin = v >= 1.0 ? 17u : (v <= 0.0 ? 16u : min(uint(v * 16.0), 15u));
        g_Out.InterlockedAdd(g_Push.destOffset + 64 + 4 * bin, 1);
        if (v >= 0.99 && v < 1.0)
            g_Out.InterlockedAdd(g_Push.destOffset + 160 + 4 * min(uint((v - 0.99) * 800.0), 7u), 1);
        return;
    }
    uint4 b = uint4(g_Push.textureB, 0, 0, 0);  // mode 2: A's first word against this constant (sasrt_gpu_diag_gbuffer_cover)
    [branch] if (g_Push.mode >= 7)
        b = uint4(g_Push.textureB, g_Push.x0, g_Push.y0, g_Push.mode == 8 ? g_Push.textureB : a.w);
    else if (g_Push.mode != 2)
        b = asuint(g_Textures[NonUniformResourceIndex(g_Push.textureB)].Load(pb));
    // mode 3 / 4 (sasrt_gpu_diag_restore_verify): A = a depth resolve's words (8_8_8_8, the word least significant byte
    // first), B = its float: the word's depth (word >> 8) against the float encoded as the resolve encodes it (3: 24-bit
    // unorm, 4: 20e4).
    [branch] if (g_Push.mode >= 3)
    {
        const uint4 bytes = uint4(round(saturate(asfloat(a)) * 255.0));
        const uint depth24 = (bytes.x | (bytes.y << 8) | (bytes.z << 16) | (bytes.w << 24)) >> 8;
        const float f = asfloat(b.x);
        uint want;
        if (g_Push.mode == 3)
            want = uint(saturate(f) * 16777215.0 + 0.5);
        else
        {
            const float d = clamp(f, 0.0, 1.99999988);
            want = d < 6.103515625e-5 ? uint(d * 17179869184.0) : ((((asuint(d) >> 23) - 112) << 20) | ((asuint(d) >> 3) & 0xFFFFF));
        }
        a = uint4(depth24, 0, 0, 0);
        b = uint4(want, 0, 0, 0);
    }
    const bool same = (g_Push.mode == 1 || g_Push.mode >= 7) ? all(a == b) : a.x == b.x;
    [branch] if (same && g_Push.mode >= 7)  // the sentinel found: the first such texel at +44 (counted at +40)
    {
        uint hits;
        g_Out.InterlockedAdd(g_Push.destOffset + 40, 1, hits);
        if (hits == 0)
        {
            g_Out.Store2(g_Push.destOffset + 44, uint2(uint(p.x), uint(p.y)));
            g_Out.Store(g_Push.destOffset + 60, (g_Push.width << 16) | g_Push.height);  // that target's size
        }
    }
    if (same)
        return;
    [branch] if (g_Push.mode == 5)  // sasrt-nx (2026-11-09): where the differing texel's value is in B
    {
        uint k = 11;
        for (uint i = 0; i < 11; ++i)
        {
            const int2 d = i < 9 ? int2(int(i % 3) - 1, int(i / 3) - 1) : int2(i == 9 ? -40 : 40, 0);
            const int2 q = p.xy + d;
            if (q.x < 0 || q.y < 0 || q.x >= int(g_Push.width + g_Push.x0) || q.y >= int(g_Push.height + g_Push.y0))
                continue;
            if (asuint(g_Textures[NonUniformResourceIndex(g_Push.textureB)].Load(int3(q, 0))).x == a.x)
            {
                k = i;
                break;
            }
        }
        g_Out.InterlockedAdd(g_Push.destOffset + 36 + 4 * k, 1);
    }
    uint before;
    g_Out.InterlockedAdd(g_Push.destOffset + 8, 1, before);
    if (before == 0)
    {
        g_Out.Store4(g_Push.destOffset + 12, uint4(uint(p.x), uint(p.y), a.x, b.x));
        g_Out.Store2(g_Push.destOffset + 28, uint2((a.y ^ b.y) | (a.z ^ b.z), a.w ^ b.w));
    }
}
