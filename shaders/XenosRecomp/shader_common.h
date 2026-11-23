#ifndef SHADER_COMMON_H_INCLUDED
#define SHADER_COMMON_H_INCLUDED

#define SPEC_CONSTANT_R11G11B10_NORMAL  (1 << 0)
#define SPEC_CONSTANT_ALPHA_TEST        (1 << 1)
// MASSEFFECT: constants arrive through a dynamic UBO (a constant bank on Maxwell) instead of being read
// through a 64-bit pointer. High bit so as not to clash with the UNLEASHED_RECOMP ones.
#define SPEC_CONSTANT_CONSTANTS_UBO    (1 << 8)
// The tfetch offset is scaled with 1/size taken from the shared constants instead of querying the
// texture for its size. A size query is another texture unit operation.
#define SPEC_CONSTANT_INV_TEX_SIZE    (1 << 9)
/*
 * The alpha test function, specialized (bits 16-18).
 *
 * g_AlphaFunction used to come from the shared constants, that is, at run time, so alphaTestValue
 * was a 7-case switch: ~8 branches in every pixel shader that does alpha testing. It was not needed
 * at all: the app already knows the function when it creates the pipeline (it comes from RB_COLORCONTROL, which is already in the key), so with three more bits the compiler
 * keeps the one comparison that applies and drops the other six. The output is bit-identical.
 */
// Bits 15, 19 and 23 are reserved (unused here; left free for the app's own use).
#define SPEC_CONSTANT_ALPHA_FUNC_SHIFT  16
#define SPEC_CONSTANT_ALPHA_FUNC_MASK   (7 << 16)
/*
 * sasrt-nx: the draw's pixel parameter generation (SQ_PROGRAM_CNTL.param_gen, SQ_CONTEXT_MISC.param_gen_pos), for
 * pixel shaders whose container lists no interpolators (Direct3D's own shaders, wrapped from ring microcode: their
 * container is a template). Bit 2 on: the register in bits 3-6 gets the pixel position instead of its interpolator.
 * Direct3D's Clear shader reads its colour from interpolator 0 (param_gen off); its depth-restore shader reads the
 * pixel position from r0 (param_gen on, register 0). Bits 2-6 are free outside UNLEASHED_RECOMP.
 */
#define SPEC_CONSTANT_PARAM_GEN         (1 << 2)
#define SPEC_CONSTANT_PARAM_GEN_SHIFT   3
/*
 * sa2-nx's GPU rounds, ported 2026-10-13 (the bit numbers are this port's: bits 2-6 are the parameter generation
 * here, 14-18 and 20-31 the renderer's own; 7 and 10-13 and 19 were free).
 * sasrt_gpu_blend_skip: the pixel's blend would leave the target exactly as it was (a UNORM target, no depth or
 * stencil write, a blend that keeps the destination when the source alpha, or the whole source, is 0 or less), so it
 * is discarded before the blend. Set by the renderer per pipeline; a NaN output is never discarded.
 */
#define SPEC_CONSTANT_BLEND_SKIP_ALPHA (1 << 10)
#define SPEC_CONSTANT_BLEND_SKIP_ZERO  (1 << 11)
// Per-pipeline facts the native renderer knows, so the shaders stop testing them per vertex or pixel:
// sasrt_gpu_texcoords_unswapped: the renderer never swaps texcoords (g_SwappedTexcoords is always 0).
#define SPEC_CONSTANT_TEXCOORDS_UNSWAPPED (1 << 12)
// sasrt_gpu_identity_remap: every vertex input of the pipeline keeps its component order (g_InputRemap is 0xFFF).
#define SPEC_CONSTANT_IDENTITY_REMAP   (1 << 13)
// sasrt_gpu_no_texture_signs: no texture of the draw has a signed, biased or gamma component, an integer format or
// an exponent bias (bits 12-31 of every descriptor index the draw passes are 0).
#define SPEC_CONSTANT_NO_TEXTURE_SIGNS (1 << 7)
// sasrt_gpu_index_base_held: the translator proved this vertex shader never reads the vertex index r0 starts with: with
// the bit, r0 starts at 0 and the renderer may hold g_VertexIndexBase (and the shared block) across draws.
#define SPEC_CONSTANT_VERTEX_INDEX_UNUSED (1 << 19)

#ifdef UNLEASHED_RECOMP
    #define SPEC_CONSTANT_BICUBIC_GI_FILTER (1 << 2)
    #define SPEC_CONSTANT_ALPHA_TO_COVERAGE (1 << 3)
    #define SPEC_CONSTANT_REVERSE_Z         (1 << 4)
#endif

#if !defined(__cplusplus) || defined(__INTELLISENSE__)

#define FLT_MIN asfloat(0xff7fffff)
#define FLT_MAX asfloat(0x7f7fffff)

#ifdef __spirv__

struct PushConstants
{
    uint64_t VertexShaderConstants;
    uint64_t PixelShaderConstants;
    uint64_t SharedConstants;
};

[[vk::push_constant]] ConstantBuffer<PushConstants> g_PushConstants;

// MASSEFFECT: the same blocks of the upload buffer, also as dynamic UBOs in set 4. With
// -fvk-use-dx-layout each float4 takes 16 contiguous bytes, so any 4-byte word of the shared block is
// a component: v[B / 16][(B % 16) / 4], and asuint reads it without changing a bit.
struct MassEffectBlockVs { float4 v[256]; };
struct MassEffectBlockPs { float4 v[256]; };  // banjo-nx: 256 (Nuts & Bolts reads up to c255)
struct MassEffectSharedBlock { float4 v[45]; };  // sasrt-nx: v[41..44] = the memory export streams (bytes 656..719)  // banjo-nx: + bool constants, indexed fetch buffers, vertex index base
[[vk::binding(0, 4)]] ConstantBuffer<MassEffectBlockVs> g_UboVertex;
[[vk::binding(1, 4)]] ConstantBuffer<MassEffectBlockPs> g_UboPixel;
[[vk::binding(2, 4)]] ConstantBuffer<MassEffectSharedBlock> g_UboShared;
// banjo-nx (sasrt-nx takes it): the renderer always reads the constants through set 4 (it forces
// masseffect_native_constants_ubo on), so the choice is made here at compile time. As a specialization constant every
// constant read was a branch pair (UBO load / 64-bit pointer load) in the SPIR-V: twice the words and blocks for the
// driver to parse and optimize before the dead side disappeared (NVK on the Switch: ~0.5 s per material pipeline).
// Same loads.
#define MASSEFFECT_UBO true
#define MASSEFFECT_SHARED_UINT(B)  asuint(g_UboShared.v[(B) / 16][((B) % 16) / 4])
#define MASSEFFECT_SHARED_FLOAT(B) g_UboShared.v[(B) / 16][((B) % 16) / 4]

#define g_Booleans                 (MASSEFFECT_UBO ? MASSEFFECT_SHARED_UINT(256) : vk::RawBufferLoad<uint>(g_PushConstants.SharedConstants + 256))
// banjo-nx: all 256 bool constants (the 8 SHADER_CONSTANT_BOOL words, 0x4900..0x4907) at bytes 488..519 of the
// shared block; bool N is bit N % 32 of word N / 32, as on the Xenos. Nuts & Bolts' shaders (most without a CTAB)
// test bools anywhere in that range (pixel shaders up to b254), beyond g_Booleans' 16 bits per stage.
#define g_BoolWord(I)              (MASSEFFECT_UBO ? MASSEFFECT_SHARED_UINT(488 + (I) * 4) : vk::RawBufferLoad<uint>(g_PushConstants.SharedConstants + 488 + (I) * 4))
#define BANJO_BOOL(A)              ((g_BoolWord((A) >> 5) >> ((A) & 31)) & 1)
#define g_SwappedTexcoords         (MASSEFFECT_UBO ? MASSEFFECT_SHARED_UINT(260) : vk::RawBufferLoad<uint>(g_PushConstants.SharedConstants + 260))
#define g_HalfPixelOffset          (MASSEFFECT_UBO ? float2(MASSEFFECT_SHARED_FLOAT(264), MASSEFFECT_SHARED_FLOAT(268)) : vk::RawBufferLoad<float2>(g_PushConstants.SharedConstants + 264))
#define g_AlphaThreshold           (MASSEFFECT_UBO ? MASSEFFECT_SHARED_FLOAT(272) : vk::RawBufferLoad<float>(g_PushConstants.SharedConstants + 272))
// MASSEFFECT: alpha test function (RB_COLORCONTROL.alpha_func): 0 never, 1 <, 2 ==, 3 <=,
// 4 >, 5 !=, 6 >=, 7 always.
#define g_AlphaFunction            (MASSEFFECT_UBO ? MASSEFFECT_SHARED_UINT(276) : vk::RawBufferLoad<uint>(g_PushConstants.SharedConstants + 276))
// MASSEFFECT: position to host clip space, like ndc_scale/ndc_offset in the
// emulation (graphics/util/draw.cpp). (1, 1) and (0, 0) for normal draws;
// with Xenos clipping disabled it converts from pixels to NDC.
#define g_NdcScale                 (MASSEFFECT_UBO ? float2(MASSEFFECT_SHARED_FLOAT(280), MASSEFFECT_SHARED_FLOAT(284)) : vk::RawBufferLoad<float2>(g_PushConstants.SharedConstants + 280))
#define g_NdcOffset                (MASSEFFECT_UBO ? float2(MASSEFFECT_SHARED_FLOAT(288), MASSEFFECT_SHARED_FLOAT(292)) : vk::RawBufferLoad<float2>(g_PushConstants.SharedConstants + 288))
// MASSEFFECT: where each component of the vertex input at that location comes from
// (D3D patches the fetch swizzle according to the declaration). 0xFFF = as is.
#define g_InputRemap(LOC)          (MASSEFFECT_UBO ? MASSEFFECT_SHARED_UINT(296 + (LOC) * 4) : vk::RawBufferLoad<uint>(g_PushConstants.SharedConstants + 296 + (LOC) * 4))
// banjo-nx: SV_VertexID + this = the guest vertex index, which a Xenos vertex shader finds in r0.x (byte 544).
#define g_VertexIndexBase          (MASSEFFECT_UBO ? MASSEFFECT_SHARED_UINT(544) : vk::RawBufferLoad<uint>(g_PushConstants.SharedConstants + 544))

[[vk::constant_id(0)]] const uint g_SpecConstants = 0;

#define g_SpecConstants() g_SpecConstants

// masseffect_native_vs_pruned_outputs (banjo-nx's fix, 2026-10-15): bit L set = the pipeline's pixel shader reads input
// location L (TEXCOORD0-15 = 0-15, COLOR0-5 = 16-21; 0 for a pipeline without one). A vertex shader sets the outputs it
// does not read to 0 at its exit, so the math that only fed them is removed when the pipeline is specialised. The
// renderer had passed constant 60 all along, but no shader declared it: Vulkan ignores such a constant, and every
// vertex shader computed all 22 outputs.
[[vk::constant_id(60)]] const uint g_PsInputs = 0xFFFFFFFF;
#define BANJO_PS_READS(L) ((g_PsInputs & (1u << (L))) != 0)

// banjo-nx's shader item 4 (its shader-size findings, ported 2026-10-15): the OLD form, for the key's A/B. A bit set =
// the form as before; clear, the default, = the new one. banjo-nx keeps it in a bit of constant 0; here all 32 bits of
// constant 0 are taken (masseffect_native_draws.cpp, kSpec*), so old forms have a constant of their own, which the
// renderer passes to both stages (61 is banjo-nx's per-slot texture signs, item 2).
// sasrt_gpu_vfetch_block (bit 0): computed-index vertex fetches (bone palettes) word by word, a branch around every load.
// (Item 1, select() / and() for the translator's ?: and &&, was ported and measured here and taken out again: DXC
// already writes an OpSelect for each of this game's forms, whose operands are constants or one addition, so no
// instruction or branch of the 747 pixel shaders it touched changed; docs/enhancements.md.)
[[vk::constant_id(62)]] const uint g_OldForms = 0;
#define OLD_FORM_VFETCH_WORDWISE (1u << 0)
#define BANJO_VFETCH_WORDWISE ((g_OldForms & OLD_FORM_VFETCH_WORDWISE) != 0)

// banjo-nx's shader item 2 (sasrt_gpu_texture_signs_per_slot here, ported 2026-10-15, banjo-nx's constant number): bit r
// set = fetch constant r's texture may have signs, a gamma curve, an integer width or an exponent bias (bits 12-31 of
// its slot word). The renderer clears the bits of the registers 0-15 whose slot words have nothing above the heap slot
// in the draw, and their fetches fold to the path they take anyway at run time (the texel as is). Both stages read the
// same slot words. The default (every bit set) is every fetch with its tests, as before.
[[vk::constant_id(61)]] const uint g_SignSlots = 0xFFFFFFFF;
#define BANJO_SLOT_SIGNS(REG) ((g_SignSlots & (1u << (REG))) != 0)

// banjo-nx: vertex fetches indexed by a computed register (bone palettes; classifyVertexFetches in
// shader_recompiler.cpp). The renderer uploads the buffer of each such fetch constant K (0..1) in host word order
// and passes its device address at bytes 520 + 8K of the shared block and its size in words at bytes 536 + 4K.
// Formats decode like the emulation's vertex fetch (graphics/pipeline/shader/spirv_translator_fetch.cpp).
uint banjoVfetchWord(uint K, int dword)
{
    const uint2 address = MASSEFFECT_UBO ? uint2(MASSEFFECT_SHARED_UINT(520 + K * 8), MASSEFFECT_SHARED_UINT(524 + K * 8))
                                         : vk::RawBufferLoad<uint2>(g_PushConstants.SharedConstants + 520 + K * 8, 8);
    const uint words = MASSEFFECT_UBO ? MASSEFFECT_SHARED_UINT(536 + K * 4)
                                      : vk::RawBufferLoad<uint>(g_PushConstants.SharedConstants + 536 + K * 4);
    if (dword < 0 || uint(dword) >= words)
        return 0;
    return vk::RawBufferLoad<uint>(((uint64_t(address.y) << 32) | uint64_t(address.x)) + uint64_t(uint(dword)) * 4, 4);
}

float4 banjoVfetchPacked(uint4 values, uint4 widths, uint isSigned, uint isInteger)
{
    float4 result;
    [unroll] for (uint i = 0; i < 4; i++)
    {
        const uint width = widths[i];
        if (width == 0)
        {
            result[i] = i == 3 ? 1.0 : 0.0;
            continue;
        }
        const uint value = values[i] & ((1u << width) - 1u);
        if (isSigned != 0)
        {
            const int signedValue = int(value << (32 - width)) >> (32 - width);
            result[i] = isInteger != 0 ? float(signedValue)
                                       : max(float(signedValue) / float((1u << (width - 1)) - 1u), -1.0);
        }
        else
        {
            result[i] = isInteger != 0 ? float(value) : float(value) / float((1u << width) - 1u);
        }
    }
    return result;
}

// banjo-nx: the words an element of the format reads (as the cases below; k_32_32_32_32 reads 3 there).
uint banjoVfetchCount(uint format)
{
    switch (format)
    {
    case 26: case 32: case 34: case 37: return 2;
    case 35: case 57: return 3;
    case 38: return 4;
    default: return 1;
    }
}

// banjo-nx (sasrt_gpu_vfetch_block here): the n words from dword with no branch. Each word is loaded at its index
// clamped into the buffer and replaced by 0 when its index is outside it (dword + i < 0 wraps to a large uint), which is
// what banjoVfetchWord returns for it. An empty buffer (0 words) still has a readable address (the renderer gives it the
// upload buffer's start): one word is loaded there and discarded. The old form put a test and a branch around every load
// (up to 64 per vertex in this game's 16-fetch skinning and morph shaders), so no two loads were in flight together.
// With OLD_FORM_VFETCH_WORDWISE, banjoVfetchWord for each word as before.
uint4 banjoVfetchWords(uint K, int dword, uint n)
{
    [branch] if (!BANJO_VFETCH_WORDWISE)
    {
        const uint2 address = MASSEFFECT_UBO ? uint2(MASSEFFECT_SHARED_UINT(520 + K * 8), MASSEFFECT_SHARED_UINT(524 + K * 8))
                                             : vk::RawBufferLoad<uint2>(g_PushConstants.SharedConstants + 520 + K * 8, 8);
        const uint words = MASSEFFECT_UBO ? MASSEFFECT_SHARED_UINT(536 + K * 4)
                                          : vk::RawBufferLoad<uint>(g_PushConstants.SharedConstants + 536 + K * 4);
        uint4 w = uint4(0, 0, 0, 0);
        const uint64_t base = (uint64_t(address.y) << 32) | uint64_t(address.x);
        const uint last = max(words, 1u) - 1u;
        [unroll] for (uint i = 0; i < 4; i++)
        {
            if (i < n)
            {
                const uint index = uint(dword + int(i));
                // 32-bit byte offset: the renderer caps these buffers far below 4 GB (kIndexedFetchMaxBytes, 4 MB).
                const uint loaded = vk::RawBufferLoad<uint>(base + uint64_t(min(index, last) * 4u), 4);
                w[i] = select(index < words, loaded, 0u);
            }
        }
        return w;
    }
    uint4 w = uint4(banjoVfetchWord(K, dword), 0, 0, 0);
    if (n > 1) w.y = banjoVfetchWord(K, dword + 1);
    if (n > 2) w.z = banjoVfetchWord(K, dword + 2);
    if (n > 3) w.w = banjoVfetchWord(K, dword + 3);
    return w;
}

float4 banjoVfetch(uint K, int dword, uint format, uint isSigned, uint isInteger, int expAdjust)
{
    float4 result = float4(0.0, 0.0, 0.0, 1.0);
    const uint4 words = banjoVfetchWords(K, dword, banjoVfetchCount(format));
    const uint w0 = words.x;
    switch (format)
    {
    case 6:   // k_8_8_8_8
        result = banjoVfetchPacked(uint4(w0, w0 >> 8, w0 >> 16, w0 >> 24), uint4(8, 8, 8, 8), isSigned, isInteger);
        break;
    case 7:   // k_2_10_10_10
        result = banjoVfetchPacked(uint4(w0, w0 >> 10, w0 >> 20, w0 >> 30), uint4(10, 10, 10, 2), isSigned, isInteger);
        break;
    case 16:  // k_10_11_11
        result = banjoVfetchPacked(uint4(w0, w0 >> 11, w0 >> 22, 0), uint4(11, 11, 10, 0), isSigned, isInteger);
        break;
    case 17:  // k_11_11_10
        result = banjoVfetchPacked(uint4(w0, w0 >> 10, w0 >> 21, 0), uint4(10, 11, 11, 0), isSigned, isInteger);
        break;
    case 25:  // k_16_16
        result = banjoVfetchPacked(uint4(w0, w0 >> 16, 0, 0), uint4(16, 16, 0, 0), isSigned, isInteger);
        break;
    case 26:  // k_16_16_16_16
    {
        const uint w1 = words.y;
        result = banjoVfetchPacked(uint4(w0, w0 >> 16, w1, w1 >> 16), uint4(16, 16, 16, 16), isSigned, isInteger);
        break;
    }
    case 31:  // k_16_16_FLOAT
        result.xy = f16tof32(uint2(w0, w0 >> 16));
        return result;
    case 32:  // k_16_16_16_16_FLOAT
    {
        const uint w1 = words.y;
        result = f16tof32(uint4(w0, w0 >> 16, w1, w1 >> 16));
        return result;
    }
    case 33:  // k_32
    case 34:  // k_32_32
    case 35:  // k_32_32_32_32
    {
        const uint count = format - 32;
        [unroll] for (uint i = 0; i < 4; i++)
        {
            if (i >= count)
                break;
            const uint w = words[i];
            float value = isSigned != 0 ? float(int(w)) : float(w);
            if (isInteger == 0)
                value = isSigned != 0 ? max(value / 2147483647.0, -1.0) : value / 4294967295.0;
            result[i] = value;
        }
        break;
    }
    case 36:  // k_32_FLOAT
        return float4(asfloat(w0), 0.0, 0.0, 1.0);
    case 37:  // k_32_32_FLOAT
        return float4(asfloat(w0), asfloat(words.y), 0.0, 1.0);
    case 57:  // k_32_32_32_FLOAT
        return float4(asfloat(w0), asfloat(words.y), asfloat(words.z), 1.0);
    case 38:  // k_32_32_32_32_FLOAT
        return asfloat(words);
    default:
        break;
    }
    return expAdjust != 0 ? result * exp2(float(expAdjust)) : result;
}

// banjo-nx (sasrt-nx takes it): memory export (Xenos memexport: the eA / eM0..4 exports of a vertex shader), as
// graphics/pipeline/shader/dxbc_translator_memexport.cpp without its 8- and 16-bit element formats. eA is the stream:
// x = 0x40000000 | (base address >> 2), y = 2^23 + element index (as a float), z = endianness (bits 0-2), format
// (8-13), signed (16), integer (17), red/blue swap (19), w = 2^23 + element count; eMk is element index + k. The
// renderer gives each stream of the draw a buffer (shared bytes 656 + 16S: guest base, size in bytes, device address)
// holding the guest words in host order (as a vertex upload with the stream's endianness leaves them): later draws
// read it as their vertex buffer. The elements are therefore stored in host word order; 8-in-64 / 8-in-128 are taken
// as 8-in-32.
uint banjoMemexportPack(float4 v, uint4 widths, uint isSigned, uint isInteger)
{
    uint packed = 0u;
    uint shift = 0u;
    [unroll] for (uint i = 0; i < 4; i++)
    {
        const uint width = widths[i];
        if (width == 0u)
            continue;
        const float x = isnan(v[i]) ? 0.0 : v[i];
        uint bits;
        if (isSigned != 0u)
        {
            const float maxValue = float((1u << (width - 1u)) - 1u);
            const float scaled = isInteger != 0u ? clamp(x, -1.0 - maxValue, maxValue) : clamp(x, -1.0, 1.0) * maxValue;
            bits = uint(int(round(scaled))) & ((1u << width) - 1u);
        }
        else
        {
            const float maxValue = float((1u << width) - 1u);
            bits = uint(round(isInteger != 0u ? clamp(x, 0.0, maxValue) : saturate(x) * maxValue));
        }
        packed |= bits << shift;
        shift += width;
    }
    return packed;
}

void banjoMemexportStore(float4 eA, float4 e0, float4 e1, float4 e2, float4 e3, float4 e4, uint written)
{
    if (written == 0u)
        return;
    const uint4 a = asuint(eA);
    if ((a.x >> 30) != 1u || (a.y >> 23) != 0x96u || (a.z >> 23) != 0x96u || (a.w >> 23) != 0x96u)
        return;
    const uint base = (a.x & 0x3FFFFFFFu) << 2;
    uint64_t device = 0;
    uint limit = 0u;
    [unroll] for (uint s = 0; s < 4; s++)
    {
        const uint4 stream = uint4(MASSEFFECT_SHARED_UINT(656 + s * 16), MASSEFFECT_SHARED_UINT(660 + s * 16),
                                   MASSEFFECT_SHARED_UINT(664 + s * 16), MASSEFFECT_SHARED_UINT(668 + s * 16));
        if (stream.y != 0u && stream.x == base)
        {
            device = (uint64_t(stream.w) << 32) | uint64_t(stream.z);
            limit = stream.y;
        }
    }
    if (device == 0)
        return;
    const uint index = a.y & 0x7FFFFFu;
    const uint count = a.w & 0x7FFFFFu;
    const uint format = (a.z >> 8) & 0x3Fu;
    const uint isSigned = (a.z >> 16) & 1u;
    const uint isInteger = (a.z >> 17) & 1u;
    const bool swapRB = ((a.z >> 19) & 1u) != 0u;
    float4 elements[5] = {e0, e1, e2, e3, e4};
    [unroll] for (uint k = 0; k < 5; k++)
    {
        if (((written >> k) & 1u) == 0u || index + k >= count)
            continue;
        const float4 v = swapRB ? elements[k].zyxw : elements[k];
        uint4 words = uint4(0u, 0u, 0u, 0u);
        uint n = 0u;
        switch (format)
        {
        case 6u:   // k_8_8_8_8
        case 50u:  // k_8_8_8_8_AS_16_16_16_16
            words.x = banjoMemexportPack(v, uint4(8, 8, 8, 8), isSigned, isInteger);
            n = 1u;
            break;
        case 7u:   // k_2_10_10_10
        case 54u:  // k_2_10_10_10_AS_16_16_16_16
            words.x = banjoMemexportPack(v, uint4(10, 10, 10, 2), isSigned, isInteger);
            n = 1u;
            break;
        case 25u:  // k_16_16
            words.x = banjoMemexportPack(v, uint4(16, 16, 0, 0), isSigned, isInteger);
            n = 1u;
            break;
        case 26u:  // k_16_16_16_16
            words.x = banjoMemexportPack(v, uint4(16, 16, 0, 0), isSigned, isInteger);
            words.y = banjoMemexportPack(v.zwxy, uint4(16, 16, 0, 0), isSigned, isInteger);
            n = 2u;
            break;
        case 31u:  // k_16_16_FLOAT
            words.x = f32tof16(v.x) | (f32tof16(v.y) << 16);
            n = 1u;
            break;
        case 32u:  // k_16_16_16_16_FLOAT
            words.x = f32tof16(v.x) | (f32tof16(v.y) << 16);
            words.y = f32tof16(v.z) | (f32tof16(v.w) << 16);
            n = 2u;
            break;
        case 36u:  // k_32_FLOAT
            words.x = asuint(v.x);
            n = 1u;
            break;
        case 37u:  // k_32_32_FLOAT
            words.xy = asuint(v.xy);
            n = 2u;
            break;
        case 38u:  // k_32_32_32_32_FLOAT
            words = asuint(v);
            n = 4u;
            break;
        default:
            return;
        }
        const uint offset = (index + k) * n * 4u;
        if (offset + n * 4u > limit)
            continue;
        [unroll] for (uint i = 0; i < 4; i++)
        {
            if (i < n)
                vk::RawBufferStore<uint>(device + offset + i * 4u, words[i]);
        }
    }
}

#else

#define DEFINE_SHARED_CONSTANTS() \
    uint g_Booleans : packoffset(c16.x); \
    uint g_SwappedTexcoords : packoffset(c16.y); \
    float2 g_HalfPixelOffset : packoffset(c16.z); \
    float g_AlphaThreshold : packoffset(c17.x); \
    uint g_AlphaFunction : packoffset(c17.y); \
    float2 g_NdcScale : packoffset(c17.z); \
    float2 g_NdcOffset : packoffset(c18.x);

uint g_SpecConstants();
#define BANJO_PS_READS(L) true
#define BANJO_VFETCH_WORDWISE false
#define BANJO_SLOT_SIGNS(REG) true

#define g_InputRemap(LOC) 0xFFF
#define BANJO_BOOL(A) 0
#define g_VertexIndexBase 0u
float4 banjoVfetch(uint K, int dword, uint format, uint isSigned, uint isInteger, int expAdjust) { return float4(0.0, 0.0, 0.0, 1.0); }
void banjoMemexportStore(float4 eA, float4 e0, float4 e1, float4 e2, float4 e3, float4 e4, uint written) {}

#endif


// banjo-nx: the W of a MOVA's vector operand; the translator passes it already reduced by the write mask.
float banjoMovaW(float v) { return v; }
float banjoMovaW(float2 v) { return v.y; }
float banjoMovaW(float3 v) { return v.z; }
float banjoMovaW(float4 v) { return v.w; }
Texture2D<float4> g_Texture2DDescriptorHeap[] : register(t0, space0);
Texture3D<float4> g_Texture3DDescriptorHeap[] : register(t0, space1);
TextureCube<float4> g_TextureCubeDescriptorHeap[] : register(t0, space2);
SamplerState g_SamplerDescriptorHeap[] : register(s0, space3);

uint2 getTexture2DDimensions(Texture2D<float4> texture)
{
    uint2 dimensions;
    texture.GetDimensions(dimensions.x, dimensions.y);
    return dimensions;
}

// The native renderer packs the four post-swizzle Xenos TextureSign values into bits 24-31 of the
// descriptor index. Values: 0 unsigned, 1 signed (the renderer still warns for it), 2 unsigned biased,
// 3 Xenos piecewise-linear gamma. Descriptor heaps use the low 24 bits.
// banjo-nx (sasrt-nx takes it): the four components at once and without per-component branches. The old form (a loop
// of four if / else if, and four nested ifs in the gamma curve) unrolled into ~20 blocks per texture fetch, and a
// material pixel shader has dozens of fetches. Same operations on the same values: the comparisons pick the same
// scale and offset, and components whose sign is 0 or 1 pass through select() untouched. One branch skips all of it
// for textures without signs (almost all of them).
float4 masseffectGammaToLinear(float4 gamma)
{
    gamma = saturate(gamma);
    const bool4 high = gamma >= 96.0 / 255.0;
    const bool4 top = gamma >= 192.0 / 255.0;
    const bool4 mid = gamma >= 64.0 / 255.0;
    const float4 scale = select(high, select(top, 8.0 / 1024.0, 4.0 / 1024.0), select(mid, 2.0 / 1024.0, 1.0 / 1024.0));
    const float4 offset = select(high, select(top, -1024.0, -256.0), select(mid, -64.0, 0.0));
    float4 linearValue = gamma * ((255.0 * 1024.0) * scale) + offset;
    linearValue += trunc(linearValue * scale);
    return linearValue * (1.0 / 1023.0);
}

// banjo-nx (sasrt_gpu_texture_signs_per_slot): the per-register flags the translator passes to the fetches (sN_Signs,
// N = the fetch constant).
#define s0_Signs BANJO_SLOT_SIGNS(0)
#define s1_Signs BANJO_SLOT_SIGNS(1)
#define s2_Signs BANJO_SLOT_SIGNS(2)
#define s3_Signs BANJO_SLOT_SIGNS(3)
#define s4_Signs BANJO_SLOT_SIGNS(4)
#define s5_Signs BANJO_SLOT_SIGNS(5)
#define s6_Signs BANJO_SLOT_SIGNS(6)
#define s7_Signs BANJO_SLOT_SIGNS(7)
#define s8_Signs BANJO_SLOT_SIGNS(8)
#define s9_Signs BANJO_SLOT_SIGNS(9)
#define s10_Signs BANJO_SLOT_SIGNS(10)
#define s11_Signs BANJO_SLOT_SIGNS(11)
#define s12_Signs BANJO_SLOT_SIGNS(12)
#define s13_Signs BANJO_SLOT_SIGNS(13)
#define s14_Signs BANJO_SLOT_SIGNS(14)
#define s15_Signs BANJO_SLOT_SIGNS(15)
#define s16_Signs BANJO_SLOT_SIGNS(16)
#define s17_Signs BANJO_SLOT_SIGNS(17)
#define s18_Signs BANJO_SLOT_SIGNS(18)
#define s19_Signs BANJO_SLOT_SIGNS(19)
#define s20_Signs BANJO_SLOT_SIGNS(20)
#define s21_Signs BANJO_SLOT_SIGNS(21)
#define s22_Signs BANJO_SLOT_SIGNS(22)
#define s23_Signs BANJO_SLOT_SIGNS(23)
#define s24_Signs BANJO_SLOT_SIGNS(24)
#define s25_Signs BANJO_SLOT_SIGNS(25)
#define s26_Signs BANJO_SLOT_SIGNS(26)
#define s27_Signs BANJO_SLOT_SIGNS(27)
#define s28_Signs BANJO_SLOT_SIGNS(28)
#define s29_Signs BANJO_SLOT_SIGNS(29)
#define s30_Signs BANJO_SLOT_SIGNS(30)
#define s31_Signs BANJO_SLOT_SIGNS(31)

float4 masseffectApplyTextureSigns(float4 value, uint packedSigns, bool slotSigns = true)
{
    // sa2-nx (sasrt_gpu_no_texture_signs): the renderer sets the bit only when every texture of the draw has packed
    // signs 0, which is the early return below: the test goes with it.
    [branch] if (g_SpecConstants() & SPEC_CONSTANT_NO_TEXTURE_SIGNS)
        return value;
    // banjo-nx (sasrt_gpu_texture_signs_per_slot): the same for this fetch's register alone.
    [branch] if (!slotSigns)
        return value;
    [branch] if (packedSigns == 0)
        return value;
    const uint4 sign = (uint4(packedSigns, packedSigns, packedSigns, packedSigns) >> uint4(0, 2, 4, 6)) & 3;
    return select(sign == 2, value * 2.0 - 1.0, select(sign == 3, masseffectGammaToLinear(value), value));
}

// sasrt-nx: the descriptor index the renderer passes for a texture slot is the heap slot (bits 0-11; the heaps hold
// at most 4096), the component width of an integer-format texture (bits 12-16, 0 = a fraction), the fetch constant's
// exponent bias (bits 18-23, signed: dword 3 bits 13-18 of the fetch constant, the result is scaled by 2^bias) and
// the remapped signs (bits 24-31).
#define MASSEFFECT_TEXTURE_SLOT(index) ((index) & 0x00000FFF)

// The number format and the exponent bias, applied after the signs. An integer-format texture returns its raw
// integers on the hardware; the host image is UNORM (0-1), hence the 2^bits - 1 (the tracks' global-illumination
// volumes: 16-bit integers with a bias of -10, 0-64). FXAA 360 binds the image it smooths three times, with biases 0,
// -1 and -2, so that two fetches add up to their average; unscaled, every edge it blended came out up to twice as
// bright (1-pixel bright outlines around everything in a race).
float4 masseffectApplyTextureBias(float4 value, uint resourceDescriptorIndex, bool slotSigns = true)
{
    // sasrt_gpu_no_texture_signs: bits 12-31 of every index of the draw are 0, so bits and bias are 0 and the value
    // passes through below: the test goes with it.
    [branch] if (g_SpecConstants() & SPEC_CONSTANT_NO_TEXTURE_SIGNS)
        return value;
    // sasrt_gpu_texture_signs_per_slot: the same for this fetch's register alone.
    [branch] if (!slotSigns)
        return value;
    const uint bits = (resourceDescriptorIndex >> 12) & 0x1F;
    const int bias = int(resourceDescriptorIndex << 8) >> 26;
    [branch] if ((bits | uint(bias)) != 0)
        value *= (bits != 0 ? exp2(float(bits)) - 1.0 : 1.0) * exp2(float(bias));
    return value;
}

float4 tfetch2D(uint resourceDescriptorIndex, uint samplerDescriptorIndex, float2 texCoord, float2 offset, float2 invSize,
               bool slotSigns = true)
{
    const uint packed = resourceDescriptorIndex;
    uint packedSigns = resourceDescriptorIndex >> 24;
    resourceDescriptorIndex = MASSEFFECT_TEXTURE_SLOT(resourceDescriptorIndex);
    Texture2D<float4> texture = g_Texture2DDescriptorHeap[resourceDescriptorIndex];
    // With the bit set, the size comes from a constant and the texture does not have to be queried. It
    // is the same computation with the same number: the renderer writes 1/size of the host image. With a
    // ternary, DXC evaluates both branches and the size query stays: an if with [branch] is needed for
    // the dead branch to disappear when the pipeline is specialized.
    // banjo-nx (sasrt-nx takes it): always by constant (the renderer forces masseffect_native_inv_tex_size on): the
    // branch is decided at compile time, like MASSEFFECT_UBO.
    float2 displacement = offset * invSize;
    return masseffectApplyTextureBias(masseffectApplyTextureSigns(
        texture.Sample(g_SamplerDescriptorHeap[samplerDescriptorIndex], texCoord + displacement), packedSigns, slotSigns),
        packed, slotSigns);
}

// banjo-nx: a 1D texture is a row of the 2D heap (sN_Texture1DDescriptorIndex is the 2D index).
// sasrt-nx: a 2D fetch with unnormalized coordinates (the instruction's texCoordDenorm bit: texels, not 0-1), as
// Direct3D's depth-restore shader samples the depth resolve at pixel positions. The coordinates are scaled by 1/size
// of the bound texture (the same source as tfetch2D's offset) before the ordinary fetch.
float4 tfetch2DDenorm(uint resourceDescriptorIndex, uint samplerDescriptorIndex, float2 texCoord, float2 offset,
                      float2 invSize, bool slotSigns = true)
{
    const float2 scale = invSize;  // always by constant, as in tfetch2D
    // A pixel position from the parameter generation is a whole texel coordinate, the very edge between two texels.
    // Normalized and scaled back by the sampler it can land a hair below the edge, and point sampling then took the
    // texel to the left or above for ~40% of the restored depth. 1/1024 texel puts it inside the intended texel; for
    // linear filtering that is far below the sampler's sub-texel precision.
    return tfetch2D(resourceDescriptorIndex, samplerDescriptorIndex, (texCoord + 1.0 / 1024.0) * scale, offset,
                    invSize, slotSigns);
}

float4 tfetch1D(uint resourceDescriptorIndex, uint samplerDescriptorIndex, float texCoord, bool slotSigns = true)
{
    // sasrt-nx: the signs and the exponent bias too (the index was used whole: a signed 1D texture read past the heap).
    Texture2D<float4> texture = g_Texture2DDescriptorHeap[MASSEFFECT_TEXTURE_SLOT(resourceDescriptorIndex)];
    return masseffectApplyTextureBias(masseffectApplyTextureSigns(
        texture.Sample(g_SamplerDescriptorHeap[samplerDescriptorIndex], float2(texCoord, 0.5)),
        resourceDescriptorIndex >> 24, slotSigns), resourceDescriptorIndex, slotSigns);
}

float2 getWeights2D(uint resourceDescriptorIndex, uint samplerDescriptorIndex, float2 texCoord, float2 offset)
{
    resourceDescriptorIndex = MASSEFFECT_TEXTURE_SLOT(resourceDescriptorIndex);
    Texture2D<float4> texture = g_Texture2DDescriptorHeap[resourceDescriptorIndex];
    return select(isnan(texCoord), 0.0, frac(texCoord * getTexture2DDimensions(texture) + offset - 0.5));
}

float w0(float a)
{
    return (1.0f / 6.0f) * (a * (a * (-a + 3.0f) - 3.0f) + 1.0f);
}

float w1(float a)
{
    return (1.0f / 6.0f) * (a * a * (3.0f * a - 6.0f) + 4.0f);
}

float w2(float a)
{
    return (1.0f / 6.0f) * (a * (a * (-3.0f * a + 3.0f) + 3.0f) + 1.0f);
}

float w3(float a)
{
    return (1.0f / 6.0f) * (a * a * a);
}

float g0(float a)
{
    return w0(a) + w1(a);
}

float g1(float a)
{
    return w2(a) + w3(a);
}

float h0(float a)
{
    return -1.0f + w1(a) / (w0(a) + w1(a)) + 0.5f;
}

float h1(float a)
{
    return 1.0f + w3(a) / (w2(a) + w3(a)) + 0.5f;
}

float4 tfetch2DBicubic(uint resourceDescriptorIndex, uint samplerDescriptorIndex, float2 texCoord, float2 offset,
                       bool slotSigns = true)
{
    const uint packed = resourceDescriptorIndex;
    uint packedSigns = resourceDescriptorIndex >> 24;
    resourceDescriptorIndex = MASSEFFECT_TEXTURE_SLOT(resourceDescriptorIndex);
    Texture2D<float4> texture = g_Texture2DDescriptorHeap[resourceDescriptorIndex];
    SamplerState samplerState = g_SamplerDescriptorHeap[samplerDescriptorIndex];
    uint2 dimensions = getTexture2DDimensions(texture);
    
    float x = texCoord.x * dimensions.x + offset.x;
    float y = texCoord.y * dimensions.y + offset.y;

    x -= 0.5f;
    y -= 0.5f;
    float px = floor(x);
    float py = floor(y);
    float fx = x - px;
    float fy = y - py;

    float g0x = g0(fx);
    float g1x = g1(fx);
    float h0x = h0(fx);
    float h1x = h1(fx);
    float h0y = h0(fy);
    float h1y = h1(fy);

    float4 r =
        g0(fy) * (g0x * texture.Sample(samplerState, float2(px + h0x, py + h0y) / float2(dimensions)) +
            g1x * texture.Sample(samplerState, float2(px + h1x, py + h0y) / float2(dimensions))) +
        g1(fy) * (g0x * texture.Sample(samplerState, float2(px + h0x, py + h1y) / float2(dimensions)) +
            g1x * texture.Sample(samplerState, float2(px + h1x, py + h1y) / float2(dimensions)));

    return masseffectApplyTextureBias(masseffectApplyTextureSigns(r, packedSigns, slotSigns), packed, slotSigns);
}

float4 tfetch3D(uint resourceDescriptorIndex, uint samplerDescriptorIndex, float3 texCoord, bool slotSigns = true)
{
    const uint packed = resourceDescriptorIndex;
    uint packedSigns = resourceDescriptorIndex >> 24;
    resourceDescriptorIndex = MASSEFFECT_TEXTURE_SLOT(resourceDescriptorIndex);
    return masseffectApplyTextureBias(masseffectApplyTextureSigns(
        g_Texture3DDescriptorHeap[resourceDescriptorIndex].Sample(g_SamplerDescriptorHeap[samplerDescriptorIndex], texCoord),
        packedSigns, slotSigns), packed, slotSigns);
}

struct CubeMapData
{
    float3 cubeMapDirections[2];
    uint cubeMapIndex;
};

float4 tfetchCube(uint resourceDescriptorIndex, uint samplerDescriptorIndex, float3 texCoord, inout CubeMapData cubeMapData,
                  bool slotSigns = true)
{
    const uint packed = resourceDescriptorIndex;
    uint packedSigns = resourceDescriptorIndex >> 24;
    resourceDescriptorIndex = MASSEFFECT_TEXTURE_SLOT(resourceDescriptorIndex);
    return masseffectApplyTextureBias(masseffectApplyTextureSigns(
        g_TextureCubeDescriptorHeap[resourceDescriptorIndex].Sample(g_SamplerDescriptorHeap[samplerDescriptorIndex], cubeMapData.cubeMapDirections[texCoord.z]),
        packedSigns, slotSigns), packed, slotSigns);
}

float4 tfetchR11G11B10(uint4 value)
{
    if (g_SpecConstants() & SPEC_CONSTANT_R11G11B10_NORMAL)
    {
        return float4(
            (value.x & 0x00000400 ? -1.0 : 0.0) + ((value.x & 0x3FF) / 1024.0),
            (value.x & 0x00200000 ? -1.0 : 0.0) + (((value.x >> 11) & 0x3FF) / 1024.0),
            (value.x & 0x80000000 ? -1.0 : 0.0) + (((value.x >> 22) & 0x1FF) / 512.0),
            0.0);
    }
    else
    {
        return asfloat(value);
    }
}

float4 tfetchTexcoord(uint swappedTexcoords, float4 value, uint semanticIndex)
{
    // sa2-nx (sasrt_gpu_texcoords_unswapped): swappedTexcoords is always 0 in the native renderer.
    [branch] if (g_SpecConstants() & SPEC_CONSTANT_TEXCOORDS_UNSWAPPED)
        return value;
    return (swappedTexcoords & (1ull << semanticIndex)) != 0 ? value.yxwz : value;
}

// MASSEFFECT: 3 bits per component: 0-3 = data component, 4 = 0, 5 = 1, 7 = unchanged.
// sa2-nx: one component of remapInput as a select chain: value[source] with a runtime index can be lowered to
// scratch memory (local memory on Maxwell), the selects cannot. Same result: 0-3 pick a component, 4 is 0, 5 is 1,
// 6 and 7 keep the original component.
float masseffectRemapComponent(float4 value, float original, uint source)
{
    float result = original;
    result = source == 0 ? value.x : result;
    result = source == 1 ? value.y : result;
    result = source == 2 ? value.z : result;
    result = source == 3 ? value.w : result;
    result = source == 4 ? 0.0 : result;
    result = source == 5 ? 1.0 : result;
    return result;
}

float4 remapInput(float4 value, uint code)
{
    // sa2-nx (sasrt_gpu_identity_remap): set only when every code of the pipeline's vertex input is 0xFFF, the early
    // return below.
    [branch] if (g_SpecConstants() & SPEC_CONSTANT_IDENTITY_REMAP)
        return value;
    // The code comes from the shared constants (the same for the whole draw): a uniform branch.
    [branch] if (code == 0xFFF)
        return value;

    // banjo-nx / sasrt-nx: select() on all four components (HLSL 2021 ?: on scalars branches, a block per component
    // for the driver), and no runtime vector index (it can become scratch memory on Maxwell): the same picks as
    // masseffectRemapComponent.
    const uint4 source = (uint4(code, code, code, code) >> uint4(0, 3, 6, 9)) & 7;
    const float4 picked = select(source == 0, value.xxxx, select(source == 1, value.yyyy,
                                 select(source == 2, value.zzzz, value.wwww)));
    return select(source < 4, picked, select(source == 4, 0.0, select(source == 5, 1.0, value)));
}

// MASSEFFECT: Xenos alpha test with its comparison function. Positive if the pixel passes.
float alphaTestValue(float alpha)
{
    bool pass = true;
    switch ((g_SpecConstants() & SPEC_CONSTANT_ALPHA_FUNC_MASK) >> SPEC_CONSTANT_ALPHA_FUNC_SHIFT)
    {
    case 0: pass = false; break;
    case 1: pass = alpha < g_AlphaThreshold; break;
    case 2: pass = alpha == g_AlphaThreshold; break;
    case 3: pass = alpha <= g_AlphaThreshold; break;
    case 4: pass = alpha > g_AlphaThreshold; break;
    case 5: pass = alpha != g_AlphaThreshold; break;
    case 6: pass = alpha >= g_AlphaThreshold; break;
    default: break;
    }
    return pass ? 1.0 : -1.0;
}

float4 cube(float4 value, inout CubeMapData cubeMapData)
{
    uint index = cubeMapData.cubeMapIndex;
    cubeMapData.cubeMapDirections[index] = value.xyz;
    ++cubeMapData.cubeMapIndex;
    
    return float4(0.0, 0.0, 0.0, index);
}

float4 dst(float4 src0, float4 src1)
{
    float4 dest;
    dest.x = 1.0;
    dest.y = src0.y * src1.y;
    dest.z = src0.z;
    dest.w = src1.w;
    return dest;
}

float4 max4(float4 src0)
{
    return max(max(src0.x, src0.y), max(src0.z, src0.w));
}

float2 getPixelCoord(uint resourceDescriptorIndex, float2 texCoord)
{
    resourceDescriptorIndex = MASSEFFECT_TEXTURE_SLOT(resourceDescriptorIndex);
    return getTexture2DDimensions(g_Texture2DDescriptorHeap[resourceDescriptorIndex]) * texCoord;
}

float computeMipLevel(float2 pixelCoord)
{
    float2 dx = ddx(pixelCoord);
    float2 dy = ddy(pixelCoord);
    float deltaMaxSqr = max(dot(dx, dx), dot(dy, dy));
    return max(0.0, 0.5 * log2(deltaMaxSqr));
}

#endif

#endif
