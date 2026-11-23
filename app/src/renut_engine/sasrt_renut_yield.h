// sasrt-nx (2026-10-19): this port's own Direct3D hooks with Renut's renderer chosen (sasrt_renderer = "renut",
// cmake/sasrt_renut_gpu.cmake). First thing in such a hook's body:
//   SASRT_RENUT_YIELD_SHARED(sub_X): Renut hooks the same address too (tools/renut_gpu_retarget.py lists these in
//     renut_engine/gpu/banjo_shared_hooks.h): Renut's side runs, and nothing of this port's renderer;
//   SASRT_RENUT_YIELD(sub_X): the game's original runs (an address Renut leaves to the original).
// Without the Renut renderer built (-DSASRT_RENUT_RENDERER=OFF) both are empty.
#pragma once

#if SASRT_RENUT_RENDERER
#include "renut_engine/gpu/banjo_renut_select.h"
#include "renut_engine/gpu/banjo_shared_hooks.h"
#define SASRT_RENUT_YIELD_SHARED(subroutine) BANJO_RENUT_YIELD_SHARED(subroutine)
#define SASRT_RENUT_YIELD(subroutine) BANJO_RENUT_YIELD(subroutine)
#else
#define SASRT_RENUT_YIELD_SHARED(subroutine)
#define SASRT_RENUT_YIELD(subroutine)
#endif
