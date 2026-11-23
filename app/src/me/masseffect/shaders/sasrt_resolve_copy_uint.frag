#version 450

// sasrt-nx (sasrt_gpu_resolve_draw): a same-format float color resolve (RGBA16F, R32F) as one fragment pass on the 3D
// engine, through integer views of both images (R16G16B16A16_UINT / R32_UINT): destination texel (x, y) = source
// texel (x, y) + delta, bit pattern for bit pattern. A float pass would not promise a NaN its payload or a denormal
// its value; vkCmdCopyImage, which this replaces, copies bits. The viewport and scissor are the destination rectangle
// (loadOp LOAD keeps the rest of the texture). An R32 attachment takes the red component.
layout(set = 0, binding = 0) uniform usampler2D source;
layout(push_constant) uniform Constants {
  ivec2 delta;
} c;
layout(location = 0) out uvec4 output_value;

void main() {
  output_value = texelFetch(source, ivec2(gl_FragCoord.xy) + c.delta, 0);
}
