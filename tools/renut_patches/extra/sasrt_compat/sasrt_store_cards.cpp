// sasrt-nx (2026-10-21): whether this port's generated code marks banjo-nx's store cards (tools/store_cards.py) is
// defined in app/src/hot/sasrt_hot_guest.cpp (g_banjo_store_cards), which sees the generated code's macros, as sa2-nx's
// CPU code does.

// sasrt-nx (2026-10-20): sa2-nx's SDK pins its guest threads for sa2_renut_core_layout (off in this port: banjo-nx's
// measurement, the first Swap hung in Ryujinx 4 runs of 12). This port's SDK has no such layout: nothing is moved.
#include <cstdint>
extern "C" uint32_t RexSetGuestThreadCoreLayout(int, uint32_t, int) { return 0; }
