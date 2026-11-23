// sasrt-nx (2026-11-09, sasrt_gpu_convert_vertex_pass; the fifth GPU round): the conversion's body, shared by
// stream_convert_cs.hlsl (a compute dispatch, as before) and stream_convert_vs.hlsl (the same per element, one vertex
// each, in a point-list draw with the rasterizer off: the conversion stays on the 3D engine).
// Builds a host vertex stream on the GPU from a memexport window, so a draw
// can read what an earlier draw exported without the CPU waiting for it (see
// ConvertExportedStreamsLocked in draw.cpp). Writes what ConvertVertices
// (vertex_format.cpp) writes: each element either its words endian-swapped
// (Copy32) or decoded and swizzled to four floats (ExpandFloat). One thread
// per element of a vertex.
//   set 0 : RWByteAddressBuffer[3] (u0, space0): the slots' export buffers,
//           then the current slot's stream buffer
//   push  : StreamConvertPush       (b0, space1)
// Must match BuildStreamConvertPipeline in video.cpp and StreamConvertPush in
// video.h.

#include "deko3d.hlsli"  // banjo-nx: BANJO_UDIV (the deko3d renderer)
struct StreamConvertPush
{
    uint source;           // g_Buffers index of the export buffer
    uint sourceOffset;     // bytes, of vertex 0
    uint destOffset;       // bytes, in the stream buffer
    uint vertices;
    uint guestStrideWords;
    uint hostStrideWords;
    uint elementCount;     // up to 8
    uint pad;
    // Two words per element (StreamConvertElement in draw.cpp):
    //   x: guest offset (words) 0-7, host offset (words) 8-15, endian 16-17,
    //      expand 18, words copied 19-21
    //   y: its type as bound: format 0-5, signed 8, integer 9, swizzles 10-21
    uint4 elements[4];
};

#ifdef __spirv__
[[vk::push_constant]] ConstantBuffer<StreamConvertPush> g_Push;
#else
ConstantBuffer<StreamConvertPush> g_Push : register(b0, space1);
#endif

RWByteAddressBuffer g_Buffers[3] : register(u0, space0);

static const uint kStreamBuffer = 2;

uint LoadSource(uint address)
{
#ifdef BANJO_DEKO3D
    // sasrt-nx (2026-10-20): constant indices (kFramesInFlight 2 export buffers). uam reaches an element picked at
    // run time through a computed constant buffer offset, which Ryujinx cannot trace: its loads read 0 there.
    [branch] if (g_Push.source == 0)
        return g_Buffers[0].Load(address);
    return g_Buffers[1].Load(address);
#else
    return g_Buffers[g_Push.source].Load(address);
#endif
}

// SwapDword in vertex_format.cpp.
uint SwapWord(uint value, uint endian)
{
    if (endian == 1) // 8in16
        return ((value & 0x00FF00FFu) << 8) | ((value >> 8) & 0x00FF00FFu);
    if (endian == 2) // 8in32
        return (value << 24) | ((value << 8) & 0x00FF0000u) | ((value >> 8) & 0x0000FF00u) | (value >> 24);
    if (endian == 3) // 16in32
        return (value << 16) | (value >> 16);
    return value;
}

// DecodeComponent in vertex_format.cpp.
float DecodeComponent(uint word, uint shift, uint bits, bool isSigned, bool isInteger)
{
    const uint raw = bits == 32 ? word : (word >> shift) & ((1u << bits) - 1u);
    if (isSigned)
    {
        const int value = bits == 32 ? int(raw) : (int(raw << (32 - bits)) >> (32 - bits));
        if (isInteger)
            return float(value);
        const float maxValue = bits == 32 ? 2147483647.0f : float((1u << (bits - 1)) - 1u);
        return max(float(value) / maxValue, -1.0f);
    }
    if (isInteger)
        return float(raw);
    return float(raw) / (bits == 32 ? 4294967295.0f : float((1u << bits) - 1u));
}

void StreamConvertOne(uint3 id)
{
    const uint count = g_Push.elementCount;
    if (count == 0 || id.x >= g_Push.vertices * count)
        return;
    // banjo-nx (deko3d): exact on Maxwell, which has no integer divide (deko3d.hlsli)
    const uint vertex = BANJO_UDIV(id.x, count);
    const uint element = id.x - vertex * count;
#ifdef BANJO_DEKO3D
    // sasrt-nx (2026-10-21): constant indices, as LoadSource (Ryujinx).
    const uint pairIndex = element >> 1;
    uint4 pair = g_Push.elements[0];
    [flatten] if (pairIndex == 1) pair = g_Push.elements[1];
    [flatten] if (pairIndex == 2) pair = g_Push.elements[2];
    [flatten] if (pairIndex == 3) pair = g_Push.elements[3];
#else
    const uint4 pair = g_Push.elements[element >> 1];
#endif
    const uint layout = (element & 1) ? pair.z : pair.x;
    const uint type = (element & 1) ? pair.w : pair.y;

    const uint guestOffset = layout & 0xFF;
    const uint hostOffset = (layout >> 8) & 0xFF;
    const uint endian = (layout >> 16) & 3;
    const uint src = g_Push.sourceOffset + (vertex * g_Push.guestStrideWords + guestOffset) * 4;
    const uint dst = g_Push.destOffset + (vertex * g_Push.hostStrideWords + hostOffset) * 4;
#ifdef BANJO_DEKO3D
    // sasrt-nx (2026-10-21, sasrt_renut_diag_convert_check "<hash>:probe"): a checked job reports what the
    // conversion computes instead of converting.
    if (g_Push.pad == 0xD1A60001u)
    {
        if (id.x == 0)
        {
            g_Buffers[kStreamBuffer].Store(g_Push.destOffset, 0xABCD0000u | count);
            g_Buffers[kStreamBuffer].Store(g_Push.destOffset + 4, g_Push.elements[(id.x + g_Push.vertices) >> 30].x);
            g_Buffers[kStreamBuffer].Store(g_Push.destOffset + 8, layout);
        }
        if (id.x == 5)
        {
            g_Buffers[kStreamBuffer].Store(g_Push.destOffset + 12, vertex);
            g_Buffers[kStreamBuffer].Store(g_Push.destOffset + 16, src - g_Push.sourceOffset);
            g_Buffers[kStreamBuffer].Store(g_Push.destOffset + 20, SwapWord(LoadSource(src), endian));
        }
        return;
    }
#endif

    if (!((layout >> 18) & 1))
    {
        // Copy32: the words endian-swapped (the halves too when the endian
        // mode says so).
        const uint words = (layout >> 19) & 7;
#ifdef BANJO_DEKO3D
        // sasrt-nx (2026-10-21): unrolled (Ryujinx cannot trace a load whose address a loop advances).
        [branch] if (words > 0) g_Buffers[kStreamBuffer].Store(dst, SwapWord(LoadSource(src), endian));
        [branch] if (words > 1) g_Buffers[kStreamBuffer].Store(dst + 4, SwapWord(LoadSource(src + 4), endian));
        [branch] if (words > 2) g_Buffers[kStreamBuffer].Store(dst + 8, SwapWord(LoadSource(src + 8), endian));
        [branch] if (words > 3) g_Buffers[kStreamBuffer].Store(dst + 12, SwapWord(LoadSource(src + 12), endian));
        [branch] if (words > 4) g_Buffers[kStreamBuffer].Store(dst + 16, SwapWord(LoadSource(src + 16), endian));
        [branch] if (words > 5) g_Buffers[kStreamBuffer].Store(dst + 20, SwapWord(LoadSource(src + 20), endian));
        [branch] if (words > 6) g_Buffers[kStreamBuffer].Store(dst + 24, SwapWord(LoadSource(src + 24), endian));
#else
        for (uint i = 0; i < words; ++i)
            g_Buffers[kStreamBuffer].Store(dst + i * 4, SwapWord(LoadSource(src + i * 4), endian));
#endif
        return;
    }

    // ExpandFloat (ExpandElement): components before the swizzle, then the
    // swizzle constants 0 and 1.
    const uint format = type & 0x3F;
    const bool isSigned = (type >> 8) & 1;
    const bool isInteger = (type >> 9) & 1;
    // sasrt-nx (2026-11-19, base port 164; fnxf_xiii's note of 2026-10-27): the components as four scalars and the
    // swizzle's pick a switch, not a float[6] indexed at run time (uam put that array in local memory: 5 KB of scratch
    // a warp). The same values.
    float c0 = 0.0f, c1 = 0.0f, c2 = 0.0f, c3 = 1.0f;
    const uint w0 = SwapWord(LoadSource(src), endian);
    switch (format)
    {
    case 6: // 8_8_8_8
        c0 = DecodeComponent(w0, 0, 8, isSigned, isInteger);
        c1 = DecodeComponent(w0, 8, 8, isSigned, isInteger);
        c2 = DecodeComponent(w0, 16, 8, isSigned, isInteger);
        c3 = DecodeComponent(w0, 24, 8, isSigned, isInteger);
        break;
    case 7: // 2_10_10_10
        c0 = DecodeComponent(w0, 0, 10, isSigned, isInteger);
        c1 = DecodeComponent(w0, 10, 10, isSigned, isInteger);
        c2 = DecodeComponent(w0, 20, 10, isSigned, isInteger);
        c3 = DecodeComponent(w0, 30, 2, isSigned, isInteger);
        break;
    case 16: // 10_11_11
        c0 = DecodeComponent(w0, 0, 11, isSigned, isInteger);
        c1 = DecodeComponent(w0, 11, 11, isSigned, isInteger);
        c2 = DecodeComponent(w0, 22, 10, isSigned, isInteger);
        break;
    case 17: // 11_11_10
        c0 = DecodeComponent(w0, 0, 10, isSigned, isInteger);
        c1 = DecodeComponent(w0, 10, 11, isSigned, isInteger);
        c2 = DecodeComponent(w0, 21, 11, isSigned, isInteger);
        break;
    case 25: // 16_16
        c0 = DecodeComponent(w0, 0, 16, isSigned, isInteger);
        c1 = DecodeComponent(w0, 16, 16, isSigned, isInteger);
        break;
    case 26: // 16_16_16_16
    {
        const uint w1 = SwapWord(LoadSource(src + 4), endian);
        c0 = DecodeComponent(w0, 0, 16, isSigned, isInteger);
        c1 = DecodeComponent(w0, 16, 16, isSigned, isInteger);
        c2 = DecodeComponent(w1, 0, 16, isSigned, isInteger);
        c3 = DecodeComponent(w1, 16, 16, isSigned, isInteger);
        break;
    }
    case 31: // 16_16_FLOAT
        c0 = f16tof32(w0);
        c1 = f16tof32(w0 >> 16);
        break;
    case 32: // 16_16_16_16_FLOAT
    {
        const uint w1 = SwapWord(LoadSource(src + 4), endian);
        c0 = f16tof32(w0);
        c1 = f16tof32(w0 >> 16);
        c2 = f16tof32(w1);
        c3 = f16tof32(w1 >> 16);
        break;
    }
    case 33: // 32
    case 34: // 32_32
    case 35: // 32_32_32_32
        // sasrt-nx (2026-10-21): unrolled, as Copy32's (Ryujinx); base port 164's scalar form.
        c0 = DecodeComponent(w0, 0, 32, isSigned, isInteger);
        [branch] if (format != 33)
            c1 = DecodeComponent(SwapWord(LoadSource(src + 4), endian), 0, 32, isSigned, isInteger);
        [branch] if (format == 35)
        {
            c2 = DecodeComponent(SwapWord(LoadSource(src + 8), endian), 0, 32, isSigned, isInteger);
            c3 = DecodeComponent(SwapWord(LoadSource(src + 12), endian), 0, 32, isSigned, isInteger);
        }
        break;
    case 36: // 32_FLOAT
    case 37: // 32_32_FLOAT
    case 38: // 32_32_32_32_FLOAT
    case 57: // 32_32_32_FLOAT
        c0 = asfloat(w0);
        [branch] if (format != 36) c1 = asfloat(SwapWord(LoadSource(src + 4), endian));
        [branch] if (format == 38 || format == 57) c2 = asfloat(SwapWord(LoadSource(src + 8), endian));
        [branch] if (format == 38) c3 = asfloat(SwapWord(LoadSource(src + 12), endian));
        break;
    default:
        break;
    }
    uint4 result;
    [unroll]
    for (uint i = 0; i < 4; ++i)
    {
        const uint pick = (type >> (10 + 3 * i)) & 7;  // 0-3 the components, 5: 1; 4 and the rest read 0
        float v = 0.0f;
        switch (pick)
        {
        case 0: v = c0; break;
        case 1: v = c1; break;
        case 2: v = c2; break;
        case 3: v = c3; break;
        case 5: v = 1.0f; break;
        default: break;
        }
        result[i] = asuint(v);
    }
    g_Buffers[kStreamBuffer].Store4(dst, result);
}
