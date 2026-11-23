ROOT = r'D:/sonic transformed/sasrt-nx/app/src/renut_engine/gpu/'


def edit(path, old, new, count=1):
    p = ROOT + path
    s = open(p, encoding='utf-8').read()
    assert s.count(old) == count, (path, s.count(old), old[:80])
    s = s.replace(old, new)
    open(p, 'w', encoding='utf-8').write(s)


edit('render/draw.cpp', '''    FastPipeline *cp = &g_fast_pipelines[fp_index];
    bool hit = answers(*cp);
    if (!hit && ::renut::gpu::host_batch::On(::renut::gpu::host_batch::kPipelineTwoWay)) {''', '''    FastPipeline *cp = &g_fast_pipelines[fp_index];
    bool hit = answers(*cp);
    // sasrt-nx (2026-11-20, sasrt_rt4_pipeline_four_way; the third table's #24, the first's #17): the four entries of the
    // index's aligned group (the 4P race: 4,516 conflicts a 10 s with two ways, each a MakeKey and GetPipelineLocked).
    // The same choice as two ways: an entry that answers; else one made from this draw's inputs, else an empty one, else
    // the one used longest ago.
    if (!hit && ::renut::gpu::host_batch::On(::renut::gpu::host_batch::kPipelineTwoWay) &&
        sasrt::gpu_round::On(sasrt::gpu_round::kRt4PipelineFourWay)) {
      FastPipeline *victim = nullptr;
      int victim_rank = -1;  // 3: same inputs, 2: empty, 1: older (by age)
      uint32_t victim_age = 0;
      for (u32 w = 0; w < 4; ++w) {
        FastPipeline &e = g_fast_pipelines[(fp_index & ~3u) | w];
        if (answers(e)) {
          cp = &e;
          hit = true;
          break;
        }
        const int rank = same_inputs(e) ? 3 : !e.pipeline ? 2 : 1;
        const uint32_t age = uint8_t(g_fast_pipeline_stamp - e.stamp);
        if (rank > victim_rank || (rank == victim_rank && rank == 1 && age > victim_age)) {
          victim = &e;
          victim_rank = rank;
          victim_age = age;
        }
      }
      if (!hit) {
        cp = victim;
        sasrt::gpu_round::Count(sasrt::gpu_round::kRt4PipelineFourWay, 1, 1);  // a miss (the line's /n)
      } else {
        sasrt::gpu_round::Count(sasrt::gpu_round::kRt4PipelineFourWay);
      }
    } else if (!hit && ::renut::gpu::host_batch::On(::renut::gpu::host_batch::kPipelineTwoWay)) {''')
print('ok')
