# A resolve destination's content kept across a render-scale change (SASRT, 2026-11-21): handoff

`sasrt_resolve_remake_carry` (1 by default in SASRT) fixes SASRT's split-screen dark far shadows. It is a generic
renderer fix, not a render-thread change.

## The bug

Renut makes a resolve destination again when the resolve comes at another render scale or size (ResolveTarget:
"made again ... scale differs"). Every dynamic-resolution step does this to every destination. The new image's
content is undefined (`discardTexture`). That is harmless for a destination the game resolves whole every frame. It is
not harmless for a destination with a part the game resolves only now and then: on the 360 that memory keeps what was
resolved, but here the part becomes whatever memory the new image got.

SASRT in three and four players:
- Each view's shadow cascades are one 512x1024 destination: the near cascade's resolve into the top half every frame,
  the far cascade's into the bottom half only when the game redraws it (at the race's start).
- At the user's clocks the race starts below 1x and the 3D steps up to 720 lines.
- After the last step, the far half held NaN, 3.4e38, -25.7 and old scene depths (run 336, `t2_before_run336.png`:
  the four views' textures, near half above, far half below).
- The shadow compare read that as "lit" or "shadowed" by chance: the far geometry was flat dark grey for the whole
  race, in some views of some runs, never at the overclock (no steps there).

## The fix (`textures_cpp.diff`, `draw_cpp.diff`)

- **render/textures.cpp `ResolveTarget`.** A destination made again with the same description and format, a 2D
  single-level image that has resolves (so only its scale or size changed), is moved into `carry_from` instead of
  being retired.
- **render/draw.cpp `SasrtCarryResolveContentLocked`.** After the new one is created and discarded, this draws the old
  one's raw view (`RawViewSlotLocked`: no swizzle) into it: `present_vs` plus `ui_upscale_ps`, the point-clamp sampler,
  scaled. Then the old one is retired.
- Texture slots are freed a frame late (`retired_texture_slots`), so the draw's read of the old slot is safe.
- The key: 1 = depth destinations, 2 = colour destinations too, 0 = off. Each carry logs "[sasrt] resolve destination
  ... made again at WxH: its content drawn into the new image" (the first 8, then powers of two).
- `t2_after_run337.png`: the far halves are a real far cascade in all four views.

## Results

- **Console, run 337** (four players, the user's clocks): fps unchanged.
- **Ryujinx** (a step a second, `banjo_renut_dynamic_test_s = 1`): 256+ carried, none failed.

## How it was found

`sasrt_renut_diag_view_dump N` (in the same draw.cpp; off by default) writes one frame's per-view images to
`view_dump/`:
- the sun pass's inputs;
- the depth and colour targets right after the sun pass, copied at the next draw from `Video::NoteFrameDrawLocked`, so
  DrawStateLocked keeps its PGO profile;
- the composite's inputs.

`view_dump.py` turns them into PNGs and a sheet. The file writes stall the game about 40 s a dump.

For N&B: look for "made again ... scale differs true" on destinations the game resolves only now and then.
