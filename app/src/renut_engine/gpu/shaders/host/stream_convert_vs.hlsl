// sasrt-nx (2026-11-09, sasrt_gpu_convert_vertex_pass; the fifth GPU round): stream_convert.hlsli as a vertex shader, one
// vertex per element of a vertex (the dispatch's thread index), drawn as a point list with the rasterizer off: the
// same stores of the same words, with no switch from the 3D engine to compute and back.
#include "stream_convert.hlsli"

float4 main(uint vertexId : SV_VertexID) : SV_Position
{
    StreamConvertOne(uint3(vertexId, 0, 0));
    return float4(0.0, 0.0, 0.0, 1.0);
}
