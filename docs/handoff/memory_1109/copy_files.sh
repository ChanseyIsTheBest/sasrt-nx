#!/bin/bash
# Copies the files this batch changed, whole, into files/ (SASRT's tree as of the last tested build).
cd "/d/sonic transformed/sasrt-nx"
B=docs/handoff/memory_1109/files
for f in \
  app/sasrt_switch.toml app/sasrt.toml \
  app/src/renut_engine/gpu/backend/memory_report.cpp \
  app/src/renut_engine/gpu/banjo_renut_tuning.cpp app/src/renut_engine/gpu/banjo_renut_tuning.h \
  app/src/renut_engine/gpu/guest/command_buffers.cpp app/src/renut_engine/gpu/guest/command_buffers.h \
  app/src/renut_engine/gpu/render/draw.cpp app/src/renut_engine/gpu/render/pipeline.cpp \
  app/src/renut_engine/gpu/render/smaa.cpp app/src/renut_engine/gpu/render/surfaces.cpp \
  app/src/renut_engine/gpu/render/surfaces.h app/src/renut_engine/gpu/render/textures.cpp \
  app/src/renut_engine/gpu/sasrt_gpu_round.cpp \
  app/thirdparty/plume/plume_deko3d.cpp app/thirdparty/plume/plume_deko3d.h app/thirdparty/plume/plume_deko3d_region.h \
  sdk/include/rex/filesystem/devices/host_path_file.h sdk/src/filesystem/devices/host_path_file.cpp \
  sdk/src/core/guest_memory_switch.cpp sdk/src/core/guest_memory_switch.h \
  sdk/src/core/threading_posix.cpp sdk/src/core/threading_switch.h \
  sdk/src/system/xthread.cpp sdk/src/ui/switch_perf.cpp \
  tools/test_gpu_region_bestfit.cpp tools/test_gpu_region_bestfit.cpp; do
  mkdir -p "$B/$(dirname $f)"; cp "$f" "$B/$f"
done
du -sh $B; find $B -type f | wc -l
