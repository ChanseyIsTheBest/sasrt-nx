R = 'D:/sonic transformed/sasrt-nx/'
pending = {}


def edit(path, pairs):
    if path in pending:
        s, crlf = pending[path]
    else:
        b = open(R + path, 'rb').read()
        crlf = b'\r\n' in b
        s = b.decode('utf-8')
    for old, new in pairs:
        if crlf:
            old, new = old.replace('\n', '\r\n'), new.replace('\n', '\r\n')
        assert s.count(old) == 1, (path, s.count(old), old[:90])
        s = s.replace(old, new)
    pending[path] = (s, crlf)


Q = 'app/src/renut_engine/gpu/backend/queued.cpp'
edit(Q, [
    # audit 1 + 3: state for "compare everything next" and tags a whole capture consumed
    ('''// sasrt-nx (2026-11-10, sasrt_capture_marks): a check found a chunk changed without a mark: whole compares from then on.
std::atomic<bool> g_capture_marks_failed{false};''',
     '''// sasrt-nx (2026-11-10, sasrt_capture_marks): a check found a chunk changed without a mark: whole compares from then on.
std::atomic<bool> g_capture_marks_failed{false};
// sasrt-nx (2026-11-10, the batch's audit, finding 1): run tv1 found the resolve path changing fetch chunks 0, 1 and 11
// without a tag (NewOp compares every chunk at a resolve op). The chain's next delta after a resolve compares every
// chunk the same way: QueueResolve sets this, CaptureDelta takes it.
std::atomic<bool> g_capture_next_whole{false};
// The audit's finding 3: the tags a whole capture of the chain's device cleared (ClearPending), for its next delta.
uint64_t g_capture_cleared_tags = 0;  // under g_delta.mutex, as the chain'''),
    ('''  if (device == g_delta.device.load(std::memory_order_relaxed)) {
    g_delta.vs |= uint64_t(device->m_Pending[0]);
    g_delta.ps |= uint64_t(device->m_Pending[1]);
  }''',
     '''  if (device == g_delta.device.load(std::memory_order_relaxed)) {
    g_delta.vs |= uint64_t(device->m_Pending[0]);
    g_delta.ps |= uint64_t(device->m_Pending[1]);
    // sasrt-nx (2026-11-10, the audit's finding 3): their tags' chunks go with the chain's next delta too.
    g_capture_cleared_tags |= native::TagChunks(u64(device->m_Pending[2]), u64(device->m_Pending[3]),
                                                u64(device->m_Pending[4]));
  }'''),
    ('''      if (slot && c.marks_primed && !g_capture_marks_failed.load(std::memory_order_relaxed)) {
        marked = touched | kCaptureUntagged |
                 native::TagChunks(u64(device->m_Pending[2]), u64(device->m_Pending[3]), u64(device->m_Pending[4]));
        use_marks = true;''',
     '''      const bool whole_next = g_capture_next_whole.exchange(false, std::memory_order_relaxed);  // audit finding 1
      const uint64_t cleared = g_capture_cleared_tags;  // audit finding 3
      g_capture_cleared_tags = 0;
      if (slot && c.marks_primed && !whole_next && !g_capture_marks_failed.load(std::memory_order_relaxed)) {
        marked = touched | kCaptureUntagged | cleared |
                 native::TagChunks(u64(device->m_Pending[2]), u64(device->m_Pending[3]), u64(device->m_Pending[4]));
        use_marks = true;'''),
    ('''  FlushDeferredVertices(device_va);
  RunReadyCallbacks();
  const auto *device = GuestPtr<const u8>(device_va);
  if (!device)
    return;
  // The destination header as it is now: the game often builds it on the
  // stack (as for recorded resolves).''',
     '''  FlushDeferredVertices(device_va);
  RunReadyCallbacks();
  const auto *device = GuestPtr<const u8>(device_va);
  if (!device)
    return;
  // sasrt-nx (2026-11-10, the batch's audit, finding 1): the chain's next delta compares every chunk (sasrt_capture_marks).
  g_capture_next_whole.store(true, std::memory_order_relaxed);
  // The destination header as it is now: the game often builds it on the
  // stack (as for recorded resolves).'''),
    # audit 7: the counters in the report
    ('''    line += fmt::format("; verify: {} draws checked, {} differ", g_delta_verified.exchange(0, std::memory_order_relaxed),''',
     '''    line += fmt::format("; verify: {} draws checked, {} differ", g_delta_verified.exchange(0, std::memory_order_relaxed),'''),
])

# the report: append the marks counters (read under the chain's lock, as the other counters)
edit(Q, [
    ('''    g_delta.whole = 0;''',
     '''    g_delta.whole = 0;
    // sasrt-nx (2026-11-10, the batch's audit, finding 7): sasrt_capture_marks' counts since the last report.
    g_capture_marks_report = fmt::format(
        "; capture marks (sasrt_capture_marks): {} deltas from marks, {:.1f} chunks compared a delta, {} whole checks, "
        "{} chunks changed without a mark{}",
        g_delta.marks_deltas, g_delta.marks_deltas ? double(g_delta.marks_chunks) / double(g_delta.marks_deltas) : 0.0,
        g_delta.marks_checks, g_delta.marks_missed,
        g_capture_marks_failed.load(std::memory_order_relaxed) ? " (marks off: a miss was found)" : "");
    g_delta.marks_deltas = g_delta.marks_chunks = g_delta.marks_checks = g_delta.marks_missed = 0;'''),
    ('''uint64_t g_capture_cleared_tags = 0;  // under g_delta.mutex, as the chain''',
     '''uint64_t g_capture_cleared_tags = 0;  // under g_delta.mutex, as the chain
std::string g_capture_marks_report;  // the audit's finding 7: SnapshotDeltaReport's part (under g_delta.mutex)'''),
])

edit(Q, [
    ('''  return line;
}

// bangaio-nx (2026-10-29, v6, banjo_renut_delta_prefetch)''',
     '''  line += g_capture_marks_report;  // sasrt-nx (2026-11-10, the audit's finding 7)
  return line;
}

// bangaio-nx (2026-10-29, v6, banjo_renut_delta_prefetch)'''),
])

C = 'app/src/renut_engine/gpu/guest/command_buffers.cpp'
edit(C, [
    ('''  static const bool sasrt_marks = REXCVAR_GET(sasrt_record_device_slots);
  if (sasrt_marks && tracked) {''',
     '''  // (The batch's audit, finding 8: any device with a slot, the title device's included when sasrt_capture_marks gives it one.)
  if (tracked) {'''),
])

L = 'tools/localize_native.py'
edit(L, [
    ('''        me = INDEX_FORMAT''',
     '''        me = f'{INDEX_FORMAT}-atomics{int(ATOMICS)}'  # sasrt-nx (2026-11-10, the audit's finding 2): ATOMICS changes summarise()'''),
])

B = 'tools/switch_hot_bulk.py'
edit(B, [
    ('''        rows = [r for r in rows if r[0][4:].upper() not in have]
        lines = [l for l in kept if l.strip()]''',
     '''        lines = [l for l in kept if l.strip()]'''),
    ('''                pruned.append(l)
            lines = pruned''',
     '''                pruned.append(l)
            lines = pruned
        # (The audit's finding 5: what the list still has after the prune, so a pruned function the profiles now find
        # hot enough comes back.)
        have = {m.group(1).upper() for l in lines for m in [re.match(r'\\s*([0-9A-Fa-f]{8})\\b', l)] if m}
        rows = [r for r in rows if r[0][4:].upper() not in have]'''),
    ('''            if 'REX_RAW_ADDR(' in l and not (ln.RAW_VECTOR_STORE.match(l) or ln.RAW_MEMSET.match(l) or
                                             ln.RAW_LOAD.match(l)):
                return False''',
     '''            if 'REX_RAW_ADDR(' in l and not (ln.RAW_VECTOR_STORE.match(l) or ln.RAW_MEMSET.match(l) or
                                             ln.RAW_LOAD.match(l) or
                                             (ln.ATOMICS and (ln.ATOMIC_LOAD.match(l) or ln.ATOMIC_CAS.match(l)))):
                return False  # (the audit's finding 9: the atomic forms localize_native.py now copies)'''),
])

P = 'tools/win/pgo_cycle.ps1'
edit(P, [
    ('''$pgo = Join-Path $root 'pgo'
if ((Test-Path $pgo) -and (Get-ChildItem $pgo -Filter *.gcda -ErrorAction SilentlyContinue)) {
    $aside = Join-Path $root ('pgo_' + (Get-Date -Format 'yyyyMMdd_HHmm'))''',
     '''$pgo = Join-Path $root 'pgo'
# (The batch's audit, finding 10: the streams must not be in the profile folder, which is moved aside below.)
if ((Resolve-Path $Streams).Path.StartsWith($pgo, [System.StringComparison]::OrdinalIgnoreCase)) {
    Write-Error 'pgo_cycle: -Streams must not be the pgo folder or inside it (it is moved aside): copy the stream elsewhere'
    exit 1
}
if ((Test-Path $pgo) -and (Get-ChildItem $pgo -Filter *.gcda -ErrorAction SilentlyContinue)) {
    $aside = Join-Path $root ('pgo_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))'''),
])

for path, (s, crlf) in pending.items():
    open(R + path, 'wb').write(s.encode('utf-8'))
print('written', len(pending))
