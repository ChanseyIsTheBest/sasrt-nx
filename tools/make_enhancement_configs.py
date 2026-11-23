#!/usr/bin/env python3
"""Writes the premade enhancement configurations from app/sasrt_switch.toml (the default), each differing from it only
in what its name says (docs/enhancements.md; sa2-nx's script):

  sasrt_cpu_on.toml       the default                             (A/B: every enhancement on)
  sasrt_cpu_off.toml      sasrt_cpu_enhancements = false          (A/B baseline: the CPU group off, non-CPU on)
  sasrt_natives_off.toml  sasrt_cpu_natives = false               (A/B of the native replacements batch only)
  sasrt_noncpu_off.toml   sasrt_noncpu_enhancements = false       (the non-CPU group off, CPU on)
  sasrt_all_off.toml      both masters false                      (the original paths everywhere)
  sasrt_cpu_verify.toml   sasrt_cpu_verify = true, profiler on    (every enhancement on, every use checked; slow)
  sasrt_profile.toml      the default, profiler on                (kept for older notes: the same as sasrt_cpu_on)
  sasrt_test_direct_state_off.toml  sasrt_cpu_direct_state = false  (A/B of the direct renderer's draw state records)
  sasrt_test_deferred_on.toml       the three deferred-recording keys true (A/B of deferred Vulkan recording)
  sasrt_test_vertex_containment_off.toml  sasrt_cpu_vertex_containment = false (A/B of the vertex window reuse)
  sasrt_test_vertex_no_fingerprint_off.toml  sasrt_cpu_vertex_no_fingerprint = false (A/B of the hash-free dedupe)
  sasrt_test_ring_round_off.toml    the direct renderer round's six ring keys false (A/B of the whole round)
  sasrt_test_ab_round.toml          the same six keys switched off and on every 2 s in one run (the in-run A/B)
  sasrt_test_direct_flush_off.toml  sasrt_cpu_direct_flush = false (A/B of the direct renderer's step 2)
  sasrt_test_vertex_binds_off.toml  sasrt_cpu_vertices_base_zero_r0 and sasrt_cpu_ring_bind_changed false
  sasrt_test_note_shader_off.toml   sasrt_cpu_note_shader_fast and sasrt_cpu_note_shader_pair false
  sasrt_test_api_off.toml           sasrt_api_draws and sasrt_api_clears false (A/B of the native Direct3D layer)
  sasrt_test_api_zero_ahead_off.toml  sasrt_api_ring_zero_ahead = false (A/B of DC ZVA on the native layer's ring)
  sasrt_test_vs_identify_off.toml   sasrt_gpu_vs_swizzle_variants and sasrt_gpu_vs_fetch_reorder false
  sasrt_test_cpu_round12_off.toml   the run-time keys of the CPU round of 2026-10-12 false (its build-time parts stay)
  sasrt_test_gpu_round13_off.toml   the six GPU keys of 2026-10-13 (sa2-nx's GPU rounds) false, same shader package
  sasrt_test_vsync_relaxed_on.toml  sasrt_vsync_relaxed = true (off by default: no effect measured on the PC)
  sasrt_test_resolved_retire_off.toml  sasrt_native_resolved_retire_idle = false (resolved textures kept all session)
  sasrt_all_on.toml                 every optimisation on (also deferred recording and relaxed vsync), verify off
  sasrt_test_texture_slots_off.toml  sasrt_native_texture_slots_evict = false (the texture cache evicts by texel bytes only)
  sasrt_test_edram_banjo_off.toml  banjo-nx's five EDRAM items of 2026-10-14 off (the EDRAM transfers as before them)
  sasrt_test_dead_draws_off.toml   sasrt_gpu_skip_dead_draws = false (draws that can write nothing drawn again)
  sasrt_test_api_clear_off.toml    sasrt_gpu_api_clear = false (banjo-nx's Clear operation off)
  sasrt_test_ring_step4_off.toml   banjo-nx's step 4 on the ring off (texture range invalidation, persistent indices)
  sasrt_test_gpu_groups.toml       sasrt_diag_gpu_groups = 2 (GPU time per draw state and pixel shader)
  sasrt_test_vfetch_block_off.toml  sasrt_gpu_vfetch_block = false (bone-palette fetches word by word), table on
  sasrt_test_signs_per_slot_off.toml  sasrt_gpu_texture_signs_per_slot = false (texture tests per draw only), table on

The profiler is on in sasrt.toml itself and in every configuration (2026-10-06, the user's choice relayed from
sa2-nx: every test run brings its profile; since 2026-10-21, the user: "the profiler on in all logs", verify too):
switch_profile_stacks = true (the CPU sampler, logs/rex/rex_profile_NNN.log, NNN the session's log number),
masseffect_gpu_marks_categories = true (GPU time per pass category and the idle gap in the "GPU per Swap" lines) and
renut_gpu_profile = 10 (Renut's "GPU profile" line every 10 s: the GPU's time per frame by kind of work). Every A/B side
pays the same profiling cost. The variants set the keys explicitly, so a config stays profiled even if the default
changes; none is in the enhancement table, so the masters of cpu_off / noncpu_off / all_off do not touch them.
Deferred recording is explicit-only (futari-nx's lockstep captures found it not pixel-identical): sasrt_switch.toml
writes it false, so every config has it off but sasrt_test_deferred_on.toml.

  python tools/make_enhancement_configs.py [--out <folder>]     (default: out/nx/configs)
"""
import argparse
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROFILING = {'switch_profile_stacks': 'true', 'masseffect_gpu_marks_categories': 'true', 'renut_gpu_profile': '10.0'}
NO_PROFILING = {'switch_profile_stacks': 'false', 'masseffect_gpu_marks_categories': 'false',
                'renut_gpu_profile': '0.0'}
PROFILING_NOTE = ('# Profiler on (every config): the CPU sampler records every pc into\n'
                  '# logs/rex/rex_profile_NNN.log (python tools/switch_hot_functions.py logs/rex/rex_profile_NNN.log --map\n'
                  '# out/nx/sdcard_sasrt.map); the GPU time per pass category is in the "GPU per Swap" log lines.\n')
NO_PROFILING_NOTE = '# Profiler off: verify mode checks, it does not measure.\n'

VARIANTS = {
    'sasrt_cpu_on.toml': dict(PROFILING),
    'sasrt_cpu_off.toml': {'sasrt_cpu_enhancements': 'false', **PROFILING},
    # A/B of the native replacements batch (app/src/hot): everything else as sasrt_cpu_on.toml.
    'sasrt_natives_off.toml': {'sasrt_cpu_natives': 'false', **PROFILING},
    'sasrt_noncpu_off.toml': {'sasrt_noncpu_enhancements': 'false', **PROFILING},
    'sasrt_all_off.toml': {'sasrt_cpu_enhancements': 'false', 'sasrt_noncpu_enhancements': 'false', **PROFILING},
    'sasrt_cpu_verify.toml': {'sasrt_cpu_verify': 'true', **PROFILING},
    'sasrt_profile.toml': dict(PROFILING),
    # The direct renderer (2026-10-07): the draw state records off, everything else as sasrt_cpu_on.toml.
    'sasrt_test_direct_state_off.toml': {'sasrt_cpu_direct_state': 'false', **PROFILING},
    # The vertex window reuse off, everything else as sasrt_cpu_on.toml.
    'sasrt_test_vertex_containment_off.toml': {'sasrt_cpu_vertex_containment': 'false', **PROFILING},
    # The hash-free vertex dedupe off (small windows fingerprinted again), everything else as sasrt_cpu_on.toml.
    'sasrt_test_vertex_no_fingerprint_off.toml': {'sasrt_cpu_vertex_no_fingerprint': 'false', **PROFILING},
    # The whole direct renderer round of 2026-10-07 off (its six ring keys), everything else as sasrt_cpu_on.toml:
    # the console A/B of the round (the PC's in-run A/B: -14.6 % whole-process CPU per Swap, -21 % ring cycles).
    'sasrt_test_ring_round_off.toml': {'sasrt_cpu_direct_state': 'false', 'sasrt_cpu_ring_edram_memo': 'false',
                                       'sasrt_cpu_ring_compare_uploaded': 'false',
                                       'sasrt_cpu_vertex_containment': 'false', 'sasrt_cpu_vertex_merge': 'false',
                                       'sasrt_cpu_vertex_no_fingerprint': 'false', **PROFILING},
    # The direct renderer's step 2 off (Direct3D's flush functions write PM4 again), everything else as sasrt_cpu_on.
    'sasrt_test_direct_flush_off.toml': {'sasrt_cpu_direct_flush': 'false', **PROFILING},
    # The vertex binding keys off (r0 shaders bind their own offset again, every changed draw binds all), else as
    # sasrt_cpu_on.toml.
    'sasrt_test_vertex_binds_off.toml': {'sasrt_cpu_vertices_base_zero_r0': 'false',
                                         'sasrt_cpu_ring_bind_changed': 'false', **PROFILING},
    # The drawing threads' shader notes as before (the diagnostic's mutex and a TLS lookup on each of the four calls a
    # draw), else as sasrt_cpu_on.toml.
    'sasrt_test_note_shader_off.toml': {'sasrt_cpu_note_shader_fast': 'false', 'sasrt_cpu_note_shader_pair': 'false',
                                        **PROFILING},
    # The native Direct3D draws off (the step 1 / step 2 path: Direct3D writes PM4, decoded into records), else as
    # sasrt_cpu_on.toml.
    'sasrt_test_api_off.toml': {'sasrt_api_draws': 'false', 'sasrt_api_clears': 'false', **PROFILING},
    'sasrt_test_api_zero_ahead_off.toml': {'sasrt_api_ring_zero_ahead': 'false', **PROFILING},
    'sasrt_test_vs_identify_off.toml': {'sasrt_gpu_vs_swizzle_variants': 'false', 'sasrt_gpu_vs_fetch_reorder': 'false',
                                        **PROFILING},
    # The run-time keys of the CPU round of 2026-10-12 off: the `dmb ish` back after every compare-and-swap, the index
    # ranges hashed again, the hook counters shared again, the layer's statistics shared again, every signal a wake
    # syscall. The round's build-time parts (frame pointer, flush-mode flow, fp_compares_modeless) are in the code.
    'sasrt_test_cpu_round12_off.toml': {'sasrt_cpu_guest_cas_no_barrier': 'false',
                                        'sasrt_cpu_index_no_fingerprint': 'false',
                                        'sasrt_cpu_ring_draw_trims': 'false', 'sasrt_cpu_hook_counter_ctx': 'false',
                                        'sasrt_api_thread_stats': 'false', 'thread_signal_skip_idle': 'false',
                                        'kernel_critsec_pcr_owner': 'false', **PROFILING},
    # sa2-nx's GPU rounds off (2026-10-13): resolves copied on the copy engine again and no shader specialization
    # bit of the round set (the same shader package: its variants are then never selected).
    'sasrt_test_gpu_round13_off.toml': {'sasrt_gpu_resolve_draw': 'false', 'sasrt_gpu_index_base_held': 'false',
                                        'sasrt_gpu_blend_skip': 'false', 'sasrt_gpu_texcoords_unswapped': 'false',
                                        'sasrt_gpu_no_texture_signs': 'false', 'sasrt_gpu_identity_remap': 'false',
                                        **PROFILING},
    # Relaxed vsync on (off by default: on the PC this game is not held to the next 1/60 s tick when a frame is late,
    # so the key changed nothing there; the console may differ).
    'sasrt_test_vsync_relaxed_on.toml': {'sasrt_vsync_relaxed': 'true', **PROFILING},
    # The long-session fix off: every address ever resolved to keeps its image (and its crops) for the session, as
    # before 2026-10-13. Only to tell whether a problem comes from a released texture.
    'sasrt_test_resolved_retire_off.toml': {'sasrt_native_resolved_retire_idle': 'false', **PROFILING},
    # The texture cache as before 2026-10-14: eviction by texel bytes only, no eviction for descriptor slots or
    # pool gaps. Only to tell whether a problem comes from a released texture.
    'sasrt_test_texture_slots_off.toml': {'sasrt_native_texture_slots_evict': 'false', **PROFILING},
    # banjo-nx's EDRAM traffic items of 2026-10-14 off (the overwrite proof's three extensions, split tiles, rect
    # split, the Clear operation): the EDRAM transfers as before them, for the console A/B of what they save
    # (docs/enhancements.md).
    'sasrt_test_edram_banjo_off.toml': {'sasrt_gpu_proof_tess_leftover': 'false', 'sasrt_gpu_proof_triangle': 'false',
                                        'sasrt_gpu_proof_depth_only': 'false', 'sasrt_gpu_edram4_split_tiles': 'false',
                                        'sasrt_gpu_rect_split': 'false', 'sasrt_gpu_api_clear': 'false', **PROFILING},
    # Draws that can write nothing drawn again (with their EDRAM preparation, which imported whole surfaces for them):
    # only to tell whether a problem comes from skipping them.
    'sasrt_test_dead_draws_off.toml': {'sasrt_gpu_skip_dead_draws': 'false', **PROFILING},
    # banjo-nx's Clear operation off (ported 2026-10-14 after the other four): a whole-surface Clear's edge tiles are
    # brought in from their previous owner again. Only to tell whether a problem comes from the widened clears.
    'sasrt_test_api_clear_off.toml': {'sasrt_gpu_api_clear': 'false', **PROFILING},
    # banjo-nx's step 4 on the ring (2026-10-15) off: the sampler cache cleared whole by every resolve again, and the
    # 16-bit indices converted and copied on every frame again (no persistent arena). The console A/B of the ring's CPU.
    'sasrt_test_ring_step4_off.toml': {'sasrt_cpu_ring_texture_invalidate_range': 'false',
                                       'sasrt_cpu_ring_index_persistent': 'false', **PROFILING},
    # Measurement: the 10 s "GPU time by pass" lines split by draw state and pixel shader (banjo-nx's per-shader table,
    # sasrt_diag_gpu_groups = 2): which scene shaders the console's GPU spends its time in. One timestamp per change
    # of group; everything else as the default.
    'sasrt_test_gpu_groups.toml': {'sasrt_diag_gpu_groups': '2', **PROFILING},
    # banjo-nx's shader item 4 (2026-10-15) back to its old form: the bone-palette fetches word by word with a branch
    # around every load. Same package; the GPU A/B of the form, with the per-shader table on (as
    # sasrt_test_gpu_groups.toml, its other side).
    'sasrt_test_vfetch_block_off.toml': {'sasrt_gpu_vfetch_block': 'false', 'sasrt_diag_gpu_groups': '2', **PROFILING},
    # banjo-nx's shader item 2 (2026-10-15) off: in a draw with a signed / gamma / biased / integer texture, every fetch
    # keeps the tests again (only draws with no such texture lose them, sasrt_gpu_no_texture_signs). Same package; the
    # GPU A/B with the per-shader table on.
    'sasrt_test_signs_per_slot_off.toml': {'sasrt_gpu_texture_signs_per_slot': 'false', 'sasrt_diag_gpu_groups': '2',
                                           **PROFILING},
    # The round's A/B in one console run (sasrt_ab_keys, docs/enhancements.md "In-run A/B"): the six ring keys
    # switched off and on together every 2 s at a Swap. The "[ab] window" lines give each phase's ring time and the
    # ring thread's own CPU cycles per draw; tools/ab_summary.py adds up the race windows. Else as sasrt_cpu_on.toml.
    'sasrt_test_ab_round.toml': {'sasrt_ab_keys': '"sasrt_cpu_direct_state;sasrt_cpu_ring_edram_memo;'
                                                  'sasrt_cpu_ring_compare_uploaded;sasrt_cpu_vertex_containment;'
                                                  'sasrt_cpu_vertex_merge;sasrt_cpu_vertex_no_fingerprint"',
                                 'sasrt_ab_period_ms': '2000', **PROFILING},
    # Deferred Vulkan recording on (the three keys), everything else as sasrt_cpu_on.toml: the console A/B. Not
    # pixel-identical in futari-nx's lockstep captures (a menu fade): a measurement, not a default.
    'sasrt_test_deferred_on.toml': {'masseffect_native_deferred_recording': 'true',
                                    'masseffect_deferred_native_fast': 'true',
                                    'masseffect_deferred_native_update': 'true', **PROFILING},
    # Every optimisation on, verify off (the user's request of 2026-10-14). The default already has every key on
    # except four: the three deferred-recording keys (masseffect-nx's console: ring thread 62 -> 40 % of a core, but
    # futari-nx found a menu fade that is not pixel-identical with it) and relaxed vsync (no effect measured here).
    # This one turns those on too. Not in it: sa2_native_zcull_1x_depth (a GPU change that needs a 30-minute test;
    # UnleashedRecomp-NX lost the GPU with depth-clear and ZCULL changes).
    # The native deko3d renderer (docs/deko3d-renderer.md, 2026-10-20): Renut's Direct3D-level renderer on deko3d, no
    # PM4 ring and no EDRAM emulation, banjo-nx's shader generator. Copy deko3d_shaders.bin next to the NRO too (the
    # DKSH cache; without it the console compiles every shader variant with uam at its first draw). Else as
    # sasrt_cpu_on.toml.
    'sasrt_renderer_deko3d.toml': {'sasrt_renderer': '"renut"', 'renut_gpu_backend': '"deko3d"', **PROFILING},
    'sasrt_all_on.toml': {'sasrt_cpu_enhancements': 'true', 'sasrt_noncpu_enhancements': 'true',
                          'sasrt_cpu_verify': 'false',
                          'masseffect_native_deferred_recording': 'true', 'masseffect_deferred_native_fast': 'true',
                          'masseffect_deferred_native_update': 'true', 'sasrt_vsync_relaxed': 'true', **PROFILING},
}


def apply(text, changes, name):
    for key, value in changes.items():
        pattern = re.compile(r'^' + re.escape(key) + r'\s*=.*$', re.M)
        if pattern.search(text):
            text = pattern.sub(f'{key} = {value}', text, count=1)
        else:
            text += f'\n{key} = {value}\n'
    own = {k: v for k, v in changes.items() if k not in PROFILING}
    profiled = changes.get('switch_profile_stacks') == 'true'
    what = ', '.join(f'{k} = {v}' for k, v in own.items()) or 'nothing changed'
    header = (f'# {name}: app/sasrt_switch.toml with {what}, profiler {"on" if profiled else "OFF"}'
              ' (tools/make_enhancement_configs.py). Copy it over sasrt.toml next to the NRO.\n')
    return header + (PROFILING_NOTE if profiled else NO_PROFILING_NOTE) + text


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=os.path.join(ROOT, 'out', 'nx', 'configs'))
    a = ap.parse_args()
    base = open(os.path.join(ROOT, 'app', 'sasrt_switch.toml'), encoding='utf-8').read()
    os.makedirs(a.out, exist_ok=True)
    for name, changes in VARIANTS.items():
        with open(os.path.join(a.out, name), 'w', encoding='utf-8', newline='\n') as f:
            f.write(apply(base, changes, name))
        print(os.path.join(a.out, name))


if __name__ == '__main__':
    main()
