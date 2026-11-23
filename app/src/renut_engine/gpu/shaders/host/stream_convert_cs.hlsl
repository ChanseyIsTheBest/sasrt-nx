// Builds a host vertex stream on the GPU from a memexport window (see stream_convert.hlsli and
// ConvertExportedStreamsLocked in draw.cpp): one thread per element of a vertex.
#include "stream_convert.hlsli"

[numthreads(64, 1, 1)]
void main(uint3 id : SV_DispatchThreadID)
{
    StreamConvertOne(id);
}
