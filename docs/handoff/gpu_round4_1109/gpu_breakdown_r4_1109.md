# SASRT GPU breakdown after round 4: console, race (2026-11-09, night)

Build: round 4's kept set (items 46 and 48 on, 45 and 47 off), SMAA in place of FXAA, stock clocks (GPU 460.8 MHz).
Same measure as round 3's report: the race windows of 10 s (console, 200 s from the start line).

| | Round 3 as kept (r3_ship, 2026-11-08 21:30) | Round 4 as kept (r4_ship, 2026-11-09 01:52) |
|---|---|---|
| fps | 20.78 | **23.59** |
| GPU ms a frame | 46.59 | **38.79** |
| render thread ms a frame | 32.09 | 29.36 |

The final build's confirmation run (r4_final, shipping toml): 40.27 ms, 22.88 fps (runs differ by 1-2 ms).
The goal was 33 ms: 6-7 ms are left, and no pixel-identical lever of that size was found (below).

## 1. The frame by pass (profile run r4n_prof, 22 race windows, 39.9 ms profiled a frame)

| Pass | ms a frame | Draws a frame | Round 3 | What it is |
|---|---|---|---|---|
| G-buffer and lighting (1152x544 colour + depth) | 18.78 | 596 | 18.67 | the scene, 17 light volumes, the full-screen lighting and fog passes |
| Colour resolves | 5.35 | | 4.84 | EDRAM targets copied into textures (item 45 off again) |
| Shadow cascades (1024x1024 depth) | **3.01** | 490 | 9.56 | three cascades; the skinning exports now 0.48 ms |
| Post passes (1152x544 colour) | 3.00 | 5 | 2.96 | composite, bloom and tone passes |
| 1200x544 (A393B1E0) | 2.53 | 2 | 2.50 | one fetch with the game's anisotropic filtering over coordinates 80 px apart |
| Depth resolves | 2.51 | | 2.47 | the three cascades into the 1024x3072 float atlas, and the scene depth |
| Half-res passes (576x272) | 1.02 | 3 | 1.02 | |
| SMAA (edges, weights, blend) | 1.41 | | 1.33 | |
| Exported stream conversion | 0.68 | ~45 dispatches | 0.69 | skinned vertices into vertex format |
| Present and overlays | 0.65 | | 0.64 | the scan-out draw into the swap chain |
| Small passes (288x136, HUD at 1280x720, ...) | 0.91 | | | |

## 2. The heaviest draws (G-buffer and post)

| Shader | ms | Draws | Per draw | Notes |
|---|---|---|---|---|
| ED0A8D53 (blended) | 3.60 | 1 | 3.77 ms | full-screen lighting with three 3D LUT lookups (stacked: two fetches each) |
| A393B1E0 | 2.53 | 2 | 1.26 ms | the game's anisotropic filtering: changing it changes pixels |
| 9041AFF6 | 2.05 | 1 | 2.05 ms | full-screen filter, 34 fetches, 64 registers |
| light-volume stencil marking (VS 98B53A18, no pixel shader) | 1.90 | 11 | 173 us | depth/stencil fill of the volumes |
| 364C9BF8 | 1.57 | 17 | 94 us | the lights' shading |
| 9805DE9C | 1.38 | 37 | 37 us | scene |
| F5211E5E | 1.05 | 181 | 5.8 us | the most-drawn scene shader (the game's alpha kill keeps it late-Z) |
| 2414CA96 | 1.01 | 1 | 1.0 ms | the composite |

## 3. What round 4 found

- The skinning export draws (point lists, ~47,000 points a frame) cost 8.4 ms because Renut attached its point-sprite
  geometry shader to every Xenos point list, export draws with the rasterizer off included: a quad for every point for a
  rasterizer that is off. Item 48 builds them without it: -6.7 ms (in-run A/B). The export draws now cost 0.48 ms.
- Their window search kept a local-memory copy of four constant-buffer words: item 46 (pass expwin) reads the constant
  buffer directly: -2 ms (in-run A/B, before item 48).
- Waits for idle cost nothing (35 of 68 a frame removed: 0.0 ms). The resolves run close to the memory's speed
  (the 1152x544 RGBA16F copies ~0.74 ms each). D32F shadow maps did not help. Only A393B1E0's two rectangles still go
  through a Renut geometry shader.

## 4. What is left, by size, and what would change pixels

1. **G-buffer and lighting, 18.8 ms**: real shading and fill work. The register caps were slower (round 3).
2. **Colour resolves, 5.4 ms**: copies at memory speed; banjo's hand-over helps only in the menus (most handed resolves
   are drawn later anyway).
3. **A393B1E0, 2.5 ms**: lowering its anisotropy (~2 ms) would change pixels: the user's call.
4. **Depth resolves, 2.5 ms**: decompression and copy at memory speed.
5. **Stream conversion, 0.7 ms**: a host-order mirror of the exports could remove it; it needs mirror seeding for words the
   export does not write, more risk than 0.6 ms was worth tonight.
