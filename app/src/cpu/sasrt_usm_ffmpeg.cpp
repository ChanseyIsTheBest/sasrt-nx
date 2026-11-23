// sasrt-nx (2026-11-19, the user: "can we please have a native ffpmeg decoder for the videos in the game like this port
// please https://github.com/recomp-nx/tw2de_nx"; tw2de_nx's app/src/cpu/tw2de_usm_ffmpeg.cpp of 2026-11-12/13, credit
// tw2de_nx): the game's USM movies (CRI Sofdec: MPEG-1 video; Data\Movies\*.usm, all 1280x720 at 30 fps) decoded by
// FFmpeg on the host instead of Sofdec's MPEG decoder in guest code (docs/intro-movie-1109.md: the decoder took the
// SlRenderer thread and two worker threads at 35-39 % each, and the intro ran at 21-25 fps with gaps in its sound).
//
// SASRT's Sofdec is the same version as TW2's (the decoder's fields at the same offsets: dec+4976 the picture's
// parameters, +5084 the macroblock decoder, +5204 / +5216 the last macroblock and the count, +5288 the chunk, +5408 the
// slice errors, +5412 a stop flag, +5416 the thread pool, +5036 the slice count):
//   sub_82EA4F08(dec, sj)   the picture's slices: to the thread pool (dec+5416), or one by one through the slice decoder
//                           (sub_82EA4B88, reached through the branch island sub_823CE9E0) = TW2's sub_828C2290
//   sub_82EA4B88(dec, sj, out)  one slice: its header, then the macroblock decoder at dec+5084 = TW2's sub_828C1FA0;
//                           a machine copy in place here, so it is not hooked: the slice loop below is done natively
//                           (its instructions one for one) and, with FFmpeg, takes each slice's bytes off the stream
//                           joint as Sofdec would have consumed them, without decoding them
//   sub_82424200(sj)        (an island to sub_82E9A868) the macroblock decoders' last call: the next start code looked
//                           at = TW2's sub_828BB068
//   sub_823B0AC0(dec, -1, sj)  (island to sub_82E9BF10) the next start code found: 0, or an error for sub_82481580
//   sub_8247D060(p)         (island to sub_82E97710) bit 0: p is a slice's start code
// The stream joint (sj): vtable +24 GetChunk(sj, line, max, &chunk), +28 UngetChunk(sj, line, &chunk), +32
// PutChunk(sj, line, &chunk); a chunk is {pointer, length}; line 1 holds the data, line 0 takes what was consumed.
//
// sasrt_usm_ffmpeg: 0 Sofdec (the original, thread pool and all), 1 FFmpeg (mpeg2video, which decodes MPEG-1 too;
// AV_CODEC_FLAG_LOW_DELAY: every picture out at once, in decode order, as the guest decodes it), 2 both and compared
// ([usm] lines; Sofdec's picture is shown). FFmpeg's picture goes over the guest's output planes (store cards marked:
// Renut's texture copies of them), from which the game's colour conversion (sub_82E7F918, hot/n_82E7F918_yuv.h) makes
// the movie's frame as before.
#include <rex/cvar.h>
#include <rex/hook.h>
#include <rex/logging.h>
#include <rex/ppc/func.h>
#include <rex/system/xmemory.h>

#include <atomic>
#include <chrono>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

#include <algorithm>           // sasrt-nx (2026-11-21): the H.265 movies
#include <condition_variable>
#include <map>
#include <memory>
#include <thread>

#include <rex/filesystem/sfd_hevc.h>

#if SASRT_NXVIDEO
#include <switch.h>  // threadCreate, svcGetThreadPriority / svcSetThreadPriority (sasrt_hevc_decode_priority)

#include "nxvideo.h"
#endif

extern "C" {
#include <libavcodec/avcodec.h>
#include <libavutil/frame.h>
#include <libavutil/log.h>
}

REXCVAR_DEFINE_INT32(sasrt_usm_ffmpeg, 1, "SASRT",
                     "The USM movies' MPEG video (the intro, the menus' and the cups' movies): 0 Sofdec's decoder (guest "
                     "code), 1 FFmpeg on the host (from tw2de_nx), 2 both, compared ([usm] log lines; Sofdec's picture "
                     "is shown)")
    .range(0, 2);
REXCVAR_DEFINE_STRING(sasrt_usm_planes, "UVY", "SASRT",
                      "Which picture plane each of Sofdec's three output planes (the picture's parameters +32, +36, +40) "
                      "is (sasrt_usm_ffmpeg 2's [usm] lines show it; TW2's Sofdec: +32 Cb, +36 Cr, +40 Y)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
// sasrt-nx (2026-11-21): the H.265 movies (rr6-nx's rr6_hevc_* keys).
REXCVAR_DEFINE_BOOL(sasrt_hevc_movies, true, "SASRT",
                    "The movies the installer made H.265 (NAME.usm.hevc beside the game files) shown from H.265 on the "
                    "Switch's video hardware; false: their tags are not looked for (such a movie then shows nothing)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_hevc_nvdec, true, "SASRT",
                    "The H.265 movies on the Switch's video hardware (NVDEC); false: FFmpeg's software decoder (slow: for "
                    "an emulator, which has no H.265 NVDEC)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_hevc_log, false, "SASRT",
                    "One [hevc] line every 300 pictures shown from H.265 (else every 3000): the time reading, decoding "
                    "and copying")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_INT32(sasrt_hevc_decode_priority, 0x2C, "SASRT",
                     "The thread's priority while it waits for an H.265 picture on NVDEC (0x1C-0x3B, lower runs first; "
                     "the game's threads 0x3B); 0 = the thread's own")
    .range(0, 0x3B)
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_usm_black_incomplete, true, "SASRT",
                    "A movie picture that lost slices (a skipped movie's stream cut mid-picture), that FFmpeg marks as "
                    "damaged or that lacks its reference pictures is shown black instead of half decoded "
                    "(sasrt_usm_ffmpeg 1; tw2de_nx's)");

REX_EXTERN(__imp__sub_82EA4F08);
REX_EXTERN(sub_823B0AC0);  // -> sub_82E9BF10: the next start code (dec, -1, sj): 0 or an error
REX_EXTERN(sub_8247D060);  // -> sub_82E97710: bit 0 of r3: a slice start code at r3
REX_EXTERN(sub_823CE9E0);  // -> sub_82EA4B88: Sofdec's slice decoder (dec, sj, out)
REX_EXTERN(sub_82424200);  // -> sub_82E9A868: the macroblock decoders' last call (sj)
REX_EXTERN(sub_82481580);  // -> sub_82E99660: the error path (dec, error)

namespace {

constexpr uint32_t kDecPlanes = 4976 + 32;  // dec+4976: the picture's 64 bytes of parameters
constexpr uint32_t kDecPitches = 4976 + 44;
constexpr uint32_t kDecCounterA = 4968;      // what the slice decoder reports in out+0 (as a difference)
constexpr uint32_t kDecSliceCount = 5036;    // halfword
constexpr uint32_t kDecLastMb = 5204;
constexpr uint32_t kDecMbCount = 5216;
constexpr uint32_t kDecChunk = 5288;
constexpr uint32_t kDecSliceErrors = 5408;
constexpr uint32_t kDecStop = 5412;

uint32_t Ld32(const uint8_t *base, uint32_t va) {
  uint32_t v;
  std::memcpy(&v, base + va, 4);
  return __builtin_bswap32(v);
}
uint16_t Ld16(const uint8_t *base, uint32_t va) {
  uint16_t v;
  std::memcpy(&v, base + va, 2);
  return __builtin_bswap16(v);
}
void St32(uint8_t *base, uint32_t va, uint32_t v) {
  v = __builtin_bswap32(v);
  std::memcpy(base + va, &v, 4);
  rex::memory::MarkStoreCardsAt(base, va, 4);
}
void St16(uint8_t *base, uint32_t va, uint16_t v) {
  v = __builtin_bswap16(v);
  std::memcpy(base + va, &v, 2);
  rex::memory::MarkStoreCardsAt(base, va, 2);
}

struct Movie {
  std::mutex mutex;
  AVCodecContext *avctx = nullptr;
  AVPacket *packet = nullptr;
  AVFrame *frame = nullptr;
  bool have_sequence = false;
  std::vector<uint8_t> bytes;  // this picture's: [sequence header,] picture header, slices
  uint32_t slices = 0;
  bool header_found = false;
  bool unterminated = false;
  uint64_t pictures = 0, decoded = 0, failed = 0, compared = 0, blacked = 0;
  uint32_t width = 0, height = 0;  // the last picture's (BlackPlanes)
  // tw2de_nx (2026-11-13): the reference pictures FFmpeg has of this stream (0-2), and when the last picture came. A
  // new stream (a sequence header after a pause) drops the old movie's references; a P picture without one, or a B
  // picture without two (an open GOP's leading B pictures at a movie's start), would be drawn against a grey stand-in
  // or the movie before: those are written black.
  uint32_t refs = 0;
  std::chrono::steady_clock::time_point last_picture{};
  uint64_t missing_refs = 0, bad_sequences = 0;
  // sasrt-nx: the host's time a picture (the 10 s line)
  double decode_ms = 0.0, copy_ms = 0.0;
  uint64_t timed = 0;
  std::chrono::steady_clock::time_point since{};
};

std::mutex g_movies_mutex;
std::unordered_map<uint32_t, Movie *> g_movies;  // by the guest decoder's address; never freed (a few a game)

Movie &MovieFor(uint32_t dec) {
  std::lock_guard lock(g_movies_mutex);
  Movie *&m = g_movies[dec];
  if (!m)
    m = new Movie();
  return *m;
}

// The next start code (00 00 01 xx) in [p + from, p + n): its offset, or n.
uint32_t NextStartCode(const uint8_t *p, uint32_t from, uint32_t n) {
  for (uint32_t i = from; i + 3 < n; ++i)
    if (p[i] == 0 && p[i + 1] == 0 && p[i + 2] == 1)
      return i;
  return n;
}

// A guest function through a pointer (the stream joint's vtable).
void CallGuest(PPCContext &ctx, uint8_t *base, uint32_t address) {
  PPCFunc *f = rex::runtime::ResolveIndirectFunction(address);
  f(ctx, base);
}
// The stream joint's GetChunk / UngetChunk / PutChunk.
void Chunk(PPCContext &ctx, uint8_t *base, uint32_t sj, uint32_t slot, uint32_t line, uint32_t chunk) {
  const uint32_t vtable = Ld32(base, sj);
  ctx.r3.u64 = sj;
  ctx.r4.u64 = line;
  if (slot == 24) {
    ctx.r5.u64 = 0x7FFFFFFF;
    ctx.r6.u64 = chunk;
  } else {
    ctx.r5.u64 = chunk;
  }
  CallGuest(ctx, base, Ld32(base, vtable + slot));
}

// Before the picture's first slice: its picture header, and the sequence header (and GOP header) before that when there
// is one, from the memory just before the slice (consumed a moment ago, still there). tw2de_nx's.
void TakeHeaders(Movie &m, uint8_t *base, uint32_t slice_va) {
  constexpr uint32_t kBack = 4096;
  const uint32_t from = slice_va > kBack ? slice_va - kBack : 0;
  const uint8_t *p = base + from;
  const uint32_t n = slice_va - from;
  int64_t picture = -1, sequence = -1;
  for (int64_t i = int64_t(n) - 4; i >= 0; --i) {
    if (p[i] != 0 || p[i + 1] != 0 || p[i + 2] != 1)
      continue;
    if (picture < 0) {
      if (p[i + 3] == 0x00)
        picture = i;
      else if (p[i + 3] != 0xB5 && p[i + 3] != 0xB2)  // extensions and user data may follow the picture header
        break;
      continue;
    }
    if (p[i + 3] == 0xB3) {
      sequence = i;
      break;
    }
    if (p[i + 3] != 0xB8 && p[i + 3] != 0xB5 && p[i + 3] != 0xB2)  // GOP header, extensions, user data
      break;
  }
  if (picture < 0)
    return;
  // tw2de_nx (2026-11-13): a sequence header found this way must be a sane one (the bytes before the slice are whatever
  // the stream buffer last held there): width and height not 0, aspect ratio code 1-4, frame rate code 1-8.
  if (sequence >= 0) {
    const uint8_t *q = p + sequence + 4;
    const bool sane = sequence + 8 <= picture && ((q[0] << 4) | (q[1] >> 4)) != 0 &&
                      (((q[1] & 0xF) << 8) | q[2]) != 0 && (q[3] >> 4) >= 1 && (q[3] >> 4) <= 4 &&
                      (q[3] & 0xF) >= 1 && (q[3] & 0xF) <= 8;
    if (!sane) {
      if (m.bad_sequences++ < 8)
        REXLOG_INFO("[usm] a sequence header before a picture is not a sane one ({:02X} {:02X} {:02X} {:02X}): left out",
                    q[0], q[1], q[2], q[3]);
      sequence = -1;
    }
  }
  m.header_found = true;
  const int64_t start = sequence >= 0 ? sequence : picture;
  if (sequence >= 0)
    m.have_sequence = true;
  m.bytes.insert(m.bytes.end(), p + start, p + n);
}

// FFmpeg's messages: a picture decoded against a stand-in reference ("first frame is no keyframe" / "allocating dummy
// last picture": grey) is marked for this thread's picture; warnings and errors to the log (the first 32). tw2de_nx's.
thread_local bool t_stand_in_ref = false;
void AvLogCallback(void *, int level, const char *fmt, va_list vl) {
  if (!fmt)
    return;
  if (std::strstr(fmt, "no keyframe") || std::strstr(fmt, "dummy"))
    t_stand_in_ref = true;
  if (level > AV_LOG_WARNING)
    return;
  static std::atomic<int> logged{0};
  if (logged.fetch_add(1, std::memory_order_relaxed) >= 32)
    return;
  char line[256];
  std::vsnprintf(line, sizeof(line), fmt, vl);
  size_t n = std::strlen(line);
  while (n && (line[n - 1] == '\n' || line[n - 1] == '\r'))
    line[--n] = 0;
  REXLOG_INFO("[usm] FFmpeg: {}", line);
}

bool OpenDecoder(Movie &m) {
  if (m.avctx)
    return true;
  static std::once_flag log_once;
  std::call_once(log_once, [] { av_log_set_callback(AvLogCallback); });
  const AVCodec *codec = avcodec_find_decoder(AV_CODEC_ID_MPEG2VIDEO);
  if (!codec) {
    static bool said = false;
    if (!said) {
      said = true;
      REXLOG_WARN("[usm] FFmpeg has no MPEG-1/2 video decoder in this build: Sofdec decodes the movies");
    }
    return false;
  }
  m.avctx = avcodec_alloc_context3(codec);
  m.avctx->flags |= AV_CODEC_FLAG_LOW_DELAY;  // each picture out as it is decoded (the guest's order)
  m.avctx->thread_count = 1;
  if (avcodec_open2(m.avctx, codec, nullptr) < 0) {
    avcodec_free_context(&m.avctx);
    return false;
  }
  m.packet = av_packet_alloc();
  m.frame = av_frame_alloc();
  return true;
}

int PlaneIndex(char c) { return c == 'Y' ? 0 : c == 'U' ? 1 : c == 'V' ? 2 : -1; }
const std::string &PlaneOrder() {
  static const std::string order = [] {
    std::string s = REXCVAR_GET(sasrt_usm_planes);
    return s.size() == 3 ? s : std::string("UVY");
  }();
  return order;
}

// The guest's output planes black (luma 0, chroma 128) at the movie's last size: a picture FFmpeg could not decode
// (Sofdec decoded nothing either) is black, not whatever the buffer held before. tw2de_nx's.
void BlackPlanes(Movie &m, uint8_t *base, uint32_t dec) {
  if (!m.width || !m.height || !REXCVAR_GET(sasrt_usm_black_incomplete))
    return;
  const uint32_t pitch_c = Ld16(base, dec + kDecPitches), pitch_y = Ld16(base, dec + kDecPitches + 2);
  for (int g = 0; g < 3; ++g) {
    const uint32_t plane = Ld32(base, dec + kDecPlanes + uint32_t(g) * 4);
    const bool luma = PlaneIndex(PlaneOrder()[size_t(g)]) == 0;
    const uint32_t pw = luma ? m.width : m.width / 2, ph = luma ? m.height : m.height / 2;
    const uint32_t pitch = luma ? pitch_y : pitch_c;
    if (!plane || pitch < pw)
      continue;
    for (uint32_t y = 0; y < ph; ++y)
      std::memset(base + plane + y * pitch, luma ? 0 : 128, pw);
    rex::memory::MarkStoreCardsAt(base, plane, pitch * ph);
  }
}

// ---------------------------------------------------------------------------------------------------------------------
// sasrt-nx (2026-11-21, the user: "please compress all the videos and audio", "you can take them from culdcept directly
// its fine as well as ridge racer 6"): the movies re-encoded to H.265 (NAME.usm.hevc or NAME.usm.hevc.lz4b beside the
// game files: rr6-nx's rex/filesystem/sfd_hevc.h, made by tools/hevc_usm_pack.py or sasrt-nx-installer). The USM is the
// game's byte for byte but each picture's slice data: one slice header, a 10-byte tag (the movie and the picture's
// display index) and zeros. The slice loop above takes that slice as any other; FinishPicture finds the tag and writes
// the H.265 picture of that index into the coded picture's planes. The H.265 is in display order without B frames and
// MPEG asks for its pictures in coded order (I0 P3 B1 B2 P6 ...): the decoder runs forward to the index asked for and
// keeps the pictures decoded on the way (a few) for the B pictures that follow. The decode and its read-ahead are
// rr6-nx's (app/src/cpu/rr6_hevc_movies.cpp: nxvideo, culdcept-nx's, on NVDEC; the frames read ahead on a libnx thread;
// nxv_decode at a raised priority).
std::atomic<uint64_t> g_hevc_shown{0}, g_hevc_missing{0};

// The tag after the picture's first slice header, if it has one.
bool FindHevcTag(const Movie &m, uint32_t *id, uint32_t *index) {
  const uint8_t *p = m.bytes.data();
  const size_t n = m.bytes.size();
  for (size_t i = 0; i + 4 + 4 + rex::filesystem::kSfdHevcTagBytes <= n; ++i) {
    if (p[i] != 0 || p[i + 1] != 0 || p[i + 2] != 1 || p[i + 3] < 0x01 || p[i + 3] > 0xAF)
      continue;
    for (size_t off = 4; off <= 8 && i + off + rex::filesystem::kSfdHevcTagBytes <= n; ++off)
      if (rex::filesystem::ParseSfdHevcTag(p + i + off, id, index))
        return true;
    return false;  // the first slice has none
  }
  return false;
}

#if SASRT_NXVIDEO
constexpr int64_t kAhead = 45;     // frames read ahead: 1.5 s at 30 frames a second (rr6-nx's)
constexpr size_t kKeptPictures = 5;  // MPEG's B pictures come at most a few pictures behind the decoder

struct Prefetch {
  std::shared_ptr<const rex::filesystem::SfdHevcMovie> movie;
  std::mutex m;
  int64_t want = 0;  // the first frame the decoder still needs
  std::map<uint32_t, std::vector<uint8_t>> ready;
  uint64_t hits = 0, misses = 0;
};

std::mutex g_ahead_mutex;
std::condition_variable g_ahead_cv;
std::vector<std::weak_ptr<Prefetch>> g_ahead;

// The read-ahead thread: the first frame missing from any open movie's window, read, then the next.
void AheadLoop() {
  std::vector<uint8_t> bytes;
  for (;;) {
    std::shared_ptr<Prefetch> job;
    uint32_t frame = 0;
    {
      std::unique_lock<std::mutex> lock(g_ahead_mutex);
      for (;;) {
        g_ahead.erase(std::remove_if(g_ahead.begin(), g_ahead.end(), [](const auto &w) { return w.expired(); }),
                      g_ahead.end());
        for (const auto &w : g_ahead) {
          auto p = w.lock();
          if (!p)
            continue;
          std::lock_guard<std::mutex> pl(p->m);
          const int64_t end = std::min<int64_t>(p->want + kAhead, int64_t(p->movie->frames.size()));
          for (int64_t f = std::max<int64_t>(p->want, 0); f < end; ++f) {
            if (!p->ready.count(uint32_t(f))) {
              job = std::move(p);
              frame = uint32_t(f);
              break;
            }
          }
          if (job)
            break;
        }
        if (job)
          break;
        g_ahead_cv.wait_for(lock, std::chrono::milliseconds(50));
      }
    }
    if (!job->movie->ReadFrame(frame, &bytes)) {
      std::this_thread::sleep_for(std::chrono::milliseconds(20));  // read again later rather than spin on a failure
      continue;
    }
    std::lock_guard<std::mutex> pl(job->m);
    if (int64_t(frame) >= job->want && int64_t(frame) < job->want + kAhead)
      job->ready[frame].swap(bytes);
  }
}

// The read-ahead thread, once: a libnx thread, not std::thread (rr6-nx: a std::thread started from the game's thread
// aborted the process in Ryujinx), above the game's threads; null if it did not start (frames read on the game's thread).
std::shared_ptr<Prefetch> StartAhead(std::shared_ptr<const rex::filesystem::SfdHevcMovie> movie) {
  static const bool running = [] {
    static Thread thread;
    const int prio = REXCVAR_GET(sasrt_hevc_decode_priority);
    const bool ok = R_SUCCEEDED(threadCreate(&thread, [](void *) { AheadLoop(); }, nullptr, nullptr, 256 * 1024,
                                             prio > 0 ? prio : 0x2C, -2)) &&
                    R_SUCCEEDED(threadStart(&thread));
    if (!ok)
      REXLOG_WARN("[hevc] the read-ahead thread did not start: the frames are read on the game's thread");
    return ok;
  }();
  if (!running)
    return nullptr;
  auto p = std::make_shared<Prefetch>();
  p->movie = std::move(movie);
  {
    std::lock_guard<std::mutex> lock(g_ahead_mutex);
    g_ahead.push_back(p);
  }
  g_ahead_cv.notify_one();
  return p;
}

// Frame `f`'s bytes into `out`: from the read-ahead when it has them, else read here. The window moves to f + 1.
bool TakeFrame(Prefetch &p, uint32_t f, std::vector<uint8_t> *out) {
  bool hit = false;
  {
    std::lock_guard<std::mutex> lock(p.m);
    p.want = int64_t(f) + 1;
    auto it = p.ready.find(f);
    if (it != p.ready.end()) {
      out->swap(it->second);
      hit = true;
    }
    for (auto i = p.ready.begin(); i != p.ready.end();) {
      if (int64_t(i->first) < p.want || int64_t(i->first) >= p.want + kAhead)
        i = p.ready.erase(i);
      else
        ++i;
    }
    ++(hit ? p.hits : p.misses);
  }
  g_ahead_cv.notify_one();
  return hit || p.movie->ReadFrame(f, out);
}

// A decoded picture kept for a B picture still to come: I420, tight rows.
struct KeptPicture {
  int w = 0, h = 0;
  std::vector<uint8_t> yuv;  // Y (w x h), U, V (w/2 x h/2 each)
};

struct HevcDecoder {
  std::shared_ptr<const rex::filesystem::SfdHevcMovie> movie;
  std::shared_ptr<Prefetch> ahead;
  NxvDecoder *d = nullptr;
  int64_t next = 0;  // the next frame nxv_decode would give
  std::vector<uint8_t> bytes;
  std::map<uint32_t, KeptPicture> kept;
  std::chrono::steady_clock::time_point used;
  double decode_ms = 0, copy_ms = 0, read_ms = 0, nxv_ms = 0;
  uint64_t frames = 0, decoded = 0;
};

std::mutex g_hevc_mutex;
std::map<uint32_t, HevcDecoder> g_hevc_decoders;

void CloseIdleHevc() {
  const auto now = std::chrono::steady_clock::now();
  for (auto it = g_hevc_decoders.begin(); it != g_hevc_decoders.end();) {
    if (now - it->second.used > std::chrono::seconds(15)) {
      if (it->second.d)
        nxv_close(it->second.d);
      it = g_hevc_decoders.erase(it);
    } else {
      ++it;
    }
  }
}

// nxv_decode at sasrt_hevc_decode_priority (rr6-nx's rr6_hevc_decode_priority: the game's threads at 0x3B are not
// time-sliced, so a thread woken from NVDEC at their priority waits for a core), timed into dc.nxv_ms.
int DecodeRaised(HevcDecoder &dc, NxvPicture *pic) {
  static const int boost = REXCVAR_GET(sasrt_hevc_decode_priority);
  s32 own = 0;
  const bool raised = boost > 0 && R_SUCCEEDED(svcGetThreadPriority(&own, CUR_THREAD_HANDLE)) && own > boost &&
                      R_SUCCEEDED(svcSetThreadPriority(CUR_THREAD_HANDLE, u32(boost)));
  const auto t0 = std::chrono::steady_clock::now();
  const int r = nxv_decode(dc.d, dc.bytes.data(), int(dc.bytes.size()), pic);
  dc.nxv_ms += std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
  if (raised)
    svcSetThreadPriority(CUR_THREAD_HANDLE, u32(own));
  return r;
}

void Keep(KeptPicture &k, const NxvPicture &pic) {
  k.w = pic.width;
  k.h = pic.height;
  const size_t ys = size_t(k.w) * size_t(k.h), cs = size_t(k.w / 2) * size_t(k.h / 2);
  k.yuv.resize(ys + 2 * cs);
  uint8_t *y = k.yuv.data(), *u = y + ys, *v = u + cs;
  for (int r = 0; r < k.h; ++r)
    std::memcpy(y + size_t(r) * k.w, pic.data[0] + size_t(r) * size_t(pic.linesize[0]), size_t(k.w));
  for (int r = 0; r < k.h / 2; ++r) {
    uint8_t *ur = u + size_t(r) * (k.w / 2), *vr = v + size_t(r) * (k.w / 2);
    if (pic.nv12) {
      const uint8_t *s = pic.data[1] + size_t(r) * size_t(pic.linesize[1]);
      for (int x = 0; x < k.w / 2; ++x) {
        ur[x] = s[2 * x];
        vr[x] = s[2 * x + 1];
      }
    } else {
      std::memcpy(ur, pic.data[1] + size_t(r) * size_t(pic.linesize[1]), size_t(k.w / 2));
      std::memcpy(vr, pic.data[2] + size_t(r) * size_t(pic.linesize[2]), size_t(k.w / 2));
    }
  }
}

// Display picture `index`, decoded in order from the last one (or from the keyframe at or before it), the pictures on
// the way kept; null when it cannot be had.
const KeptPicture *PictureAt(HevcDecoder &dc, uint32_t index) {
  auto hit = dc.kept.find(index);
  if (hit != dc.kept.end())
    return &hit->second;
  const auto &frames = dc.movie->frames;
  if (index >= frames.size())
    return nullptr;
  if (!dc.d) {
    char why[256] = {};
    static const bool hw = REXCVAR_GET(sasrt_hevc_nvdec);
    dc.d = nxv_open(NXV_HEVC, nullptr, 0, int(dc.movie->width), int(dc.movie->height), hw ? 1 : 0, why, sizeof(why));
    REXLOG_INFO("[hevc] {}: {}", dc.movie->name, dc.d ? why : "the H.265 decoder did not open");
    if (!dc.d)
      return nullptr;
    dc.next = 0;
  }
  if (int64_t(index) < dc.next || int64_t(index) > dc.next + 120) {
    int64_t k = index;
    while (k > 0 && !frames[size_t(k)].keyframe)
      --k;
    if (!(int64_t(index) >= dc.next && k <= dc.next)) {
      nxv_flush(dc.d);
      dc.next = k;
      dc.kept.clear();
    }
  }
  while (dc.next <= int64_t(index)) {
    const uint32_t f = uint32_t(dc.next++);
    const auto t0 = std::chrono::steady_clock::now();
    if (!(dc.ahead ? TakeFrame(*dc.ahead, f, &dc.bytes) : dc.movie->ReadFrame(f, &dc.bytes)))
      return nullptr;
    dc.read_ms += std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
    NxvPicture pic{};
    const int r = DecodeRaised(dc, &pic);
    if (r < 0) {
      REXLOG_WARN("[hevc] {}: frame {} did not decode", dc.movie->name, f);
      return nullptr;
    }
    if (r == 1) {
      Keep(dc.kept[f], pic);
      ++dc.decoded;
    }
  }
  while (dc.kept.size() > kKeptPictures)  // the oldest go
    dc.kept.erase(dc.kept.begin());
  auto it = dc.kept.find(index);
  return it == dc.kept.end() ? nullptr : &it->second;
}
#endif  // SASRT_NXVIDEO

// A tagged picture: its H.265 picture into the guest's planes. False when the picture has no tag (decode it as MPEG-1).
bool HevcPicture(Movie &m, uint8_t *base, uint32_t dec) {
  static const bool on = REXCVAR_GET(sasrt_hevc_movies);
  uint32_t id = 0, index = 0;
  if (!on || !FindHevcTag(m, &id, &index))
    return false;
#if SASRT_NXVIDEO
  using Clock = std::chrono::steady_clock;
  std::lock_guard<std::mutex> lock(g_hevc_mutex);
  auto it = g_hevc_decoders.find(id);
  if (it == g_hevc_decoders.end()) {
    CloseIdleHevc();
    auto movie = rex::filesystem::FindSfdHevcMovie(id);
    if (!movie) {
      if (g_hevc_missing.fetch_add(1, std::memory_order_relaxed) < 4)
        REXLOG_WARN("[hevc] a tagged picture of movie id {} that is not open: shown black", id);
      BlackPlanes(m, base, dec);
      return true;
    }
    it = g_hevc_decoders.emplace(id, HevcDecoder{}).first;
    it->second.ahead = StartAhead(movie);
    it->second.movie = std::move(movie);
  }
  HevcDecoder &dc = it->second;
  dc.used = Clock::now();
  const auto t0 = Clock::now();
  const KeptPicture *k = PictureAt(dc, index);
  const auto t1 = Clock::now();
  if (!k) {
    BlackPlanes(m, base, dec);
    return true;
  }
  const uint32_t planes[3] = {Ld32(base, dec + kDecPlanes), Ld32(base, dec + kDecPlanes + 4),
                              Ld32(base, dec + kDecPlanes + 8)};
  const uint32_t pitch_c = Ld16(base, dec + kDecPitches), pitch_y = Ld16(base, dec + kDecPitches + 2);
  const int w = k->w, h = k->h;
  m.width = uint32_t(w);
  m.height = uint32_t(h);
  const uint8_t *src[3] = {k->yuv.data(), k->yuv.data() + size_t(w) * h,
                           k->yuv.data() + size_t(w) * h + size_t(w / 2) * (h / 2)};
  const std::string &order = PlaneOrder();
  for (int g = 0; g < 3; ++g) {
    const int c = PlaneIndex(order[size_t(g)]);
    if (c < 0 || !planes[g])
      continue;
    const int pw = c ? w / 2 : w, ph = c ? h / 2 : h;
    const uint32_t pitch = c ? pitch_c : pitch_y;
    if (pitch < uint32_t(pw))
      continue;
    for (int y = 0; y < ph; ++y)
      std::memcpy(base + planes[g] + uint32_t(y) * pitch, src[c] + size_t(y) * size_t(pw), size_t(pw));
    rex::memory::MarkStoreCardsAt(base, planes[g], pitch * uint32_t(ph));
  }
  const auto t2 = Clock::now();
  dc.decode_ms += std::chrono::duration<double, std::milli>(t1 - t0).count();
  dc.copy_ms += std::chrono::duration<double, std::milli>(t2 - t1).count();
  ++dc.frames;
  const uint64_t shown = g_hevc_shown.fetch_add(1, std::memory_order_relaxed) + 1;
  static const bool log = REXCVAR_GET(sasrt_hevc_log);
  if (shown == 1 || dc.frames % (log ? 300 : 3000) == 0) {
    uint64_t hits = 0, misses = 0;
    if (dc.ahead) {
      std::lock_guard<std::mutex> pl(dc.ahead->m);
      hits = dc.ahead->hits;
      misses = dc.ahead->misses;
    }
    REXLOG_INFO("[hevc] {}: picture {} of {} shown from H.265 ({}x{}); {} pictures, {:.2f} ms decoding ({:.2f} taking "
                "the frames: {} from the read-ahead, {} read here; {:.2f} in nxv_decode; {} decoded) and {:.2f} ms "
                "copying a picture",
                dc.movie->name, index, dc.movie->frames.size(), w, h, dc.frames, dc.decode_ms / double(dc.frames),
                dc.read_ms / double(dc.frames), hits, misses, dc.nxv_ms / double(dc.frames), dc.decoded,
                dc.copy_ms / double(dc.frames));
  }
#else
  if (g_hevc_missing.fetch_add(1, std::memory_order_relaxed) == 0)
    REXLOG_WARN("[hevc] movie id {}: an H.265 movie, and this build has no H.265 decoder (the Switch's nxvideo): black",
                id);
  (void)index;
  BlackPlanes(m, base, dec);
#endif
  return true;
}

// FFmpeg's picture into the guest's planes (mode 1), or compared with them (mode 2).
void FinishPicture(Movie &m, uint8_t *base, uint32_t dec, int mode) {
  using Clock = std::chrono::steady_clock;
  ++m.pictures;
  if (mode == 1 && HevcPicture(m, base, dec))  // sasrt-nx (2026-11-21): a picture of an H.265 movie
    return;
  if (m.bytes.empty() || !m.slices || !m.header_found || !m.have_sequence || !OpenDecoder(m)) {
    ++m.failed;
    if (m.failed <= 8)
      REXLOG_WARN("[usm] {:08X}: picture {} not decoded by FFmpeg ({} slices, header {}, sequence {})", dec,
                  m.pictures, m.slices, m.header_found, m.have_sequence);
    if (mode == 1)
      BlackPlanes(m, base, dec);
    return;
  }
  const auto t0 = Clock::now();
  {
    const bool sequence_first = m.bytes.size() > 4 && m.bytes[0] == 0 && m.bytes[1] == 0 && m.bytes[2] == 1 &&
                                m.bytes[3] == 0xB3;
    if (sequence_first && m.last_picture.time_since_epoch().count() != 0 &&
        t0 - m.last_picture > std::chrono::milliseconds(250)) {
      avcodec_flush_buffers(m.avctx);  // a new movie on this decoder: the old one's references go
      m.refs = 0;
    }
    m.last_picture = t0;
  }
  av_packet_unref(m.packet);
  if (av_new_packet(m.packet, int(m.bytes.size())) < 0)
    return;
  std::memcpy(m.packet->data, m.bytes.data(), m.bytes.size());
  bool got = false;
  t_stand_in_ref = false;
  if (avcodec_send_packet(m.avctx, m.packet) >= 0)
    got = avcodec_receive_frame(m.avctx, m.frame) >= 0;  // one picture a packet (low delay)
  if (!got) {
    ++m.failed;
    if (m.failed <= 8)
      REXLOG_WARN("[usm] {:08X}: FFmpeg gave no picture for picture {} ({} bytes, {} slices)", dec, m.pictures,
                  m.bytes.size(), m.slices);
    if (mode == 1)
      BlackPlanes(m, base, dec);
    return;
  }
  const auto t1 = Clock::now();
  ++m.decoded;
  const AVFrame *f = m.frame;
  const uint32_t planes[3] = {Ld32(base, dec + kDecPlanes), Ld32(base, dec + kDecPlanes + 4),
                              Ld32(base, dec + kDecPlanes + 8)};
  const uint32_t pitch_c = Ld16(base, dec + kDecPitches), pitch_y = Ld16(base, dec + kDecPitches + 2);
  const int w = f->width, h = f->height;
  m.width = uint32_t(w);
  m.height = uint32_t(h);
  if (mode == 2) {
    if (m.compared++ < 24) {
      // Every guest plane against every FFmpeg plane: the mean absolute difference over the top rows.
      std::string line;
      for (int g = 0; g < 3; ++g) {
        for (int k = 0; k < 3; ++k) {
          const int pw = k ? w / 2 : w, ph = k ? h / 2 : h;
          const uint32_t pitch = k ? pitch_c : pitch_y;
          const int rows = ph < 64 ? ph : 64;
          uint64_t sum = 0;
          for (int y = 0; y < rows; ++y) {
            const uint8_t *a = base + planes[g] + uint32_t(y) * pitch;
            const uint8_t *b = f->data[k] + y * f->linesize[k];
            for (int x = 0; x < pw; ++x)
              sum += uint32_t(a[x] > b[x] ? a[x] - b[x] : b[x] - a[x]);
          }
          line += fmt::format(" g{}-{}c {:.2f}", g, "YUV"[k], double(sum) / double(rows * pw));
        }
      }
      REXLOG_INFO("[usm] {:08X} picture {} type {} {}x{} pitches {}/{} planes {:08X} {:08X} {:08X}; {} bytes {} "
                  "slices{}; mean |Sofdec - FFmpeg| by plane:{}",
                  dec, m.pictures, int(f->pict_type), w, h, pitch_y, pitch_c, planes[0], planes[1], planes[2],
                  m.bytes.size(), m.slices, m.unterminated ? " (a slice ran to its chunk's end)" : "", line);
    }
    return;
  }
  // tw2de_nx (2026-11-12/13): a picture that lost slices (fewer than macroblock rows: a skipped movie's stream cut off),
  // that FFmpeg flags as damaged, or that lacks its reference pictures is written black.
  const uint32_t rows = uint32_t(h + 15) / 16;
  const bool damaged = f->decode_error_flags != 0 || (f->flags & AV_FRAME_FLAG_CORRUPT) != 0;
  bool missing_ref = t_stand_in_ref;
  if (f->pict_type == AV_PICTURE_TYPE_B) {
    missing_ref = missing_ref || m.refs < 2;
  } else {
    missing_ref = missing_ref || (f->pict_type != AV_PICTURE_TYPE_I && m.refs < 1);
    m.refs = m.refs < 2 ? m.refs + 1 : 2;
  }
  if (missing_ref)
    ++m.missing_refs;
  const bool incomplete = REXCVAR_GET(sasrt_usm_black_incomplete) && (m.slices < rows || damaged || missing_ref);
  if (incomplete && m.blacked++ < 16)
    REXLOG_INFO("[usm] {:08X}: picture {} (type {}) incomplete ({} of {} slices{}{}): shown black", dec, m.pictures,
                av_get_picture_type_char(f->pict_type), m.slices, rows, damaged ? ", FFmpeg: damaged" : "",
                missing_ref ? ", its reference pictures missing" : "");
  const std::string &order = PlaneOrder();
  for (int g = 0; g < 3; ++g) {
    const int k = PlaneIndex(order[size_t(g)]);
    if (k < 0 || !planes[g])
      continue;
    const int pw = k ? w / 2 : w, ph = k ? h / 2 : h;
    const uint32_t pitch = k ? pitch_c : pitch_y;
    if (pitch < uint32_t(pw))
      continue;
    for (int y = 0; y < ph; ++y) {
      if (incomplete)  // black: luma 0, chroma 128
        std::memset(base + planes[g] + uint32_t(y) * pitch, k ? 128 : 0, size_t(pw));
      else
        std::memcpy(base + planes[g] + uint32_t(y) * pitch, f->data[k] + y * f->linesize[k], size_t(pw));
    }
    rex::memory::MarkStoreCardsAt(base, planes[g], pitch * uint32_t(ph));
  }
  // sasrt-nx: the host's time a picture, every 10 s of a movie
  const auto t2 = Clock::now();
  m.decode_ms += std::chrono::duration<double, std::milli>(t1 - t0).count();
  m.copy_ms += std::chrono::duration<double, std::milli>(t2 - t1).count();
  ++m.timed;
  if (m.since.time_since_epoch().count() == 0)
    m.since = t2;
  if (t2 - m.since >= std::chrono::seconds(10)) {
    REXLOG_INFO("[usm] {:08X}: {} pictures by FFmpeg in {:.1f} s ({}x{}): {:.2f} ms decoding and {:.2f} ms copying a "
                "picture; {} decoded, {} not, {} shown black, {} without their references so far",
                dec, m.timed, std::chrono::duration<double>(t2 - m.since).count(), w, h, m.decode_ms / double(m.timed),
                m.copy_ms / double(m.timed), m.decoded, m.failed, m.blacked, m.missing_refs);
    m.decode_ms = m.copy_ms = 0.0;
    m.timed = 0;
    m.since = t2;
  }
}

// One slice, with FFmpeg: its bytes off the stream joint as Sofdec consumes them (tw2de_nx's sub_828C1FA0 hook), and
// what the slice decoder leaves in the decoder and in 'out' (24 bytes). Mode 2: the bytes taken, the chunk put back and
// Sofdec's slice decoder run on it. Returns nothing; 'out' + 20 is the last-slice flag.
void TakeSlice(PPCContext &ctx, uint8_t *base, Movie &m, uint32_t dec, uint32_t sj, uint32_t out, uint32_t rest,
               int mode) {
  const uint32_t chunk = dec + kDecChunk;
  Chunk(ctx, base, sj, 24, 1, chunk);  // GetChunk(sj, 1, max, &dec->chunk)
  const uint32_t ptr = Ld32(base, chunk), len = Ld32(base, chunk + 4);
  uint32_t end = len;
  bool last = true;
  if (ptr && len >= 4) {
    end = NextStartCode(base + ptr, 4, len);
    if (end + 3 < len) {
      const uint8_t next = base[ptr + end + 3];
      last = !(next >= 0x01 && next <= 0xAF);
    } else {
      m.unterminated = true;
    }
    if (!m.slices)
      TakeHeaders(m, base, ptr);
    m.bytes.insert(m.bytes.end(), base + ptr, base + ptr + end);
    ++m.slices;
  }
  if (mode == 2) {
    Chunk(ctx, base, sj, 28, 1, chunk);  // UngetChunk(sj, 1, &dec->chunk): back as it was
    ctx.r3.u64 = dec;
    ctx.r4.u64 = sj;
    ctx.r5.u64 = out;
    sub_823CE9E0(ctx, base);  // Sofdec's slice decoder
    return;
  }
  // Consumed: {ptr, end} into line 0, the rest {ptr + end, len - end} back into line 1.
  St32(base, chunk, ptr);
  St32(base, chunk + 4, end);
  St32(base, rest, end < len ? ptr + end : 0);
  St32(base, rest + 4, len - end);
  Chunk(ctx, base, sj, 32, 0, chunk);  // PutChunk(sj, 0, &dec->chunk)
  Chunk(ctx, base, sj, 28, 1, rest);   // UngetChunk(sj, 1, &rest)
  ctx.r3.u64 = sj;
  sub_82424200(ctx, base);  // as the macroblock decoder ends: the next start code looked at
  // The slice's results as Sofdec leaves them: no errors, the picture done after its last slice.
  St32(base, dec + kDecSliceErrors, 0);
  const uint32_t mbs = Ld32(base, dec + kDecMbCount);
  St32(base, dec + kDecLastMb, last ? mbs : mbs - 1);
  St32(base, out + 0, 0);
  St32(base, out + 4, 0);
  St32(base, out + 8, 0);
  St32(base, out + 12, 0xFFFFFFFFu);
  St32(base, out + 16, 0xFFFFFFFFu);
  St32(base, out + 20, last ? 1u : 0u);
}

// sub_82EA4F08's one-by-one path (from loc_82EA4FA8; the thread pool is not used), each slice through TakeSlice. The
// guest calls get the frame at ctx.r1 (the hook's): peek at +80 (8 bytes), out at +96 (24), the rest's chunk at +128.
uint64_t SliceLoop(PPCContext &ctx, uint8_t *base, Movie &m, uint32_t dec, uint32_t sj, int mode) {
  const uint32_t frame = ctx.r1.u32;
  const uint32_t peek = frame + 80, out = frame + 96, rest = frame + 128;
  int32_t errors = 0;
  uint32_t last_code = 257;
  St16(base, dec + kDecSliceCount, 0);
  if (Ld32(base, dec + kDecStop) != 0)
    return 0;
  for (;;) {
    ctx.r3.u64 = dec;
    ctx.r4.u64 = ~0ull;  // li r4,-1
    ctx.r5.u64 = sj;
    sub_823B0AC0(ctx, base);
    if (ctx.r3.u32 != 0) {  // loc_82EA509C: the error path's result
      ctx.r4.u64 = ctx.r3.u64;
      ctx.r3.u64 = dec;
      sub_82481580(ctx, base);
      return ctx.r3.u64;
    }
    Chunk(ctx, base, sj, 24, 1, peek);  // a look at the next bytes: GetChunk, then UngetChunk
    Chunk(ctx, base, sj, 28, 1, peek);
    if (int32_t(Ld32(base, peek + 4)) < 4)
      break;
    ctx.r3.u64 = Ld32(base, peek);
    sub_8247D060(ctx, base);
    if (!(ctx.r3.u32 & 1))
      break;
    const uint32_t code = uint32_t(base[Ld32(base, peek) + 3]) | 256u;
    if (last_code > code) {  // loc_82EA50AC: a slice out of order
      St32(base, dec + kDecCounterA, Ld32(base, dec + kDecCounterA) + 1);
      break;
    }
    St16(base, dec + kDecSliceCount, uint16_t(Ld16(base, dec + kDecSliceCount) + 1));
    last_code = code;
    TakeSlice(ctx, base, m, dec, sj, out, rest, mode);
    errors += int32_t(Ld32(base, out + 8));
    if (Ld32(base, out + 20) != 0)
      break;
    if (Ld32(base, dec + kDecStop) != 0)
      return 0;
  }
  // loc_82EA50B8
  if (Ld32(base, dec + kDecLastMb) != Ld32(base, dec + kDecMbCount))
    St32(base, dec + kDecCounterA, Ld32(base, dec + kDecCounterA) + 1);
  if (errors)
    St32(base, dec + kDecCounterA, Ld32(base, dec + kDecCounterA) + uint32_t(errors));
  return 0;
}

}  // namespace

// The picture's slices.
REX_HOOK_RAW(sub_82EA4F08) {
  const int mode = REXCVAR_GET(sasrt_usm_ffmpeg);
  if (mode == 0) {
    __imp__sub_82EA4F08(ctx, base);
    return;
  }
  const uint32_t dec = ctx.r3.u32, sj = ctx.r4.u32;
  Movie &m = MovieFor(dec);
  std::lock_guard lock(m.mutex);
  m.bytes.clear();
  m.slices = 0;
  m.header_found = false;
  m.unterminated = false;
  static std::atomic<bool> said{false};
  if (!said.exchange(true))
    REXLOG_INFO("[usm] the movies' MPEG video: {} (sasrt_usm_ffmpeg {}, planes {})",
                mode == 1 ? "FFmpeg on the host" : "Sofdec and FFmpeg, compared", mode, PlaneOrder());
  const uint32_t r1 = ctx.r1.u32;
  ctx.r1.u64 = uint64_t(r1 - 176);  // the original's frame size: the loop's chunk, out and rest in it
  const uint64_t result = SliceLoop(ctx, base, m, dec, sj, mode);
  ctx.r1.u64 = r1;
  FinishPicture(m, base, dec, mode);
  ctx.r3.u64 = result;
}
