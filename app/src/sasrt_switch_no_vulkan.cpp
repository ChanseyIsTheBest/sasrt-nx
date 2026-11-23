// sasrt-nx (2026-10-20): the Switch build links no Vulkan driver (the user's request: REXGLUE_SWITCH_LINK_NVK off in
// sdk/cmake/rexglue_switch.cmake and app/thirdparty/plume/CMakeLists.txt). The renderer on the Switch is Renut's on
// deko3d (docs/deko3d-renderer.md), which presents through deko3d; the code that would use Vulkan (the SDK's Vulkan
// presenter and emulated GPU, this port's NVK renderer, plume's Vulkan back end) reaches the driver only through the
// entry points below, which say there is none, as on a machine without Vulkan. Linked only into such a build
// (app/CMakeLists.txt).
//
// posix_memalign: newlib has no such function, and FFmpeg's av_malloc calls it; Mesa's archive supplied one before.
#include <cerrno>
#include <cstddef>
#include <cstdint>

#include <malloc.h>

extern "C" {

// PFN_vkVoidFunction vkGetInstanceProcAddr(VkInstance, const char *): no instance, no functions.
void *vkGetInstanceProcAddr(void *, const char *) {
  return nullptr;
}

// void vkDestroyInstance(VkInstance, const VkAllocationCallbacks *): nothing was ever created.
void vkDestroyInstance(void *, const void *) {}

// The loader-less driver interface the SDK's Vulkan instance code looks up first.
void *vk_icdGetInstanceProcAddr(void *, const char *) {
  return nullptr;
}

// VkResult vk_icdNegotiateLoaderICDInterfaceVersion(uint32_t *): VK_ERROR_INCOMPATIBLE_DRIVER (-9).
int32_t vk_icdNegotiateLoaderICDInterfaceVersion(uint32_t *) {
  return -9;
}

int posix_memalign(void **out, size_t alignment, size_t size) {
  if (!out || alignment < sizeof(void *) || (alignment & (alignment - 1)) != 0)
    return EINVAL;
  void *p = memalign(alignment, size ? size : 1);
  if (!p)
    return ENOMEM;
  *out = p;
  return 0;
}

}  // extern "C"
