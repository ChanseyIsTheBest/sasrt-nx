// sasrt-nx (2026-11-09, the user's request): rr6-nx's app/src/banjo_pgo.h (banjo-nx's, from sa2-nx, GPL-3.0, the same
// project family; credit those ports), only the names differ.
// banjo-nx: profile collection of the PGO-instrumented Switch build (SASRT_PGO=generate), see banjo_pgo.cpp.
// From sa2-nx (app/src/sa2_pgo.h, GPL-3.0, same project family). In every other build these do nothing.

#pragma once

namespace sasrt::pgo {

#if !defined(__SWITCH__)
// banjo-nx (2026-10-29): banjo_pgo.cpp is a Switch source (app/CMakeLists.txt); the PC build has nothing to collect.
inline void Start() {}
inline void DumpNow() {}
inline void Stop() {}
#else
// Picks this session's file (pgo/sasrt_pgo_<N>.stream next to the executable) and starts the 2-minute dumps.
void Start();
// Writes every count so far to this session's file (the whole session each time, replacing the previous dump).
void DumpNow();
// The last dump, then the dump thread ends.
void Stop();
#endif

}  // namespace sasrt::pgo
