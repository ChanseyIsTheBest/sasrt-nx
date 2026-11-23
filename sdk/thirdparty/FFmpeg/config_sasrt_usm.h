/* sasrt-nx (2026-11-19, the user: "can we please have a native ffpmeg decoder for the videos in the game like this port
 * please https://github.com/recomp-nx/tw2de_nx"; credit tw2de_nx, its config_switch_aarch64.h of 2026-11-12): the
 * game's USM movies (CRI Sofdec, MPEG-1 video) decoded natively (app/src/cpu/sasrt_usm_ffmpeg.cpp). The MPEG-1/2
 * decoders and what configure selects for them (mpegvideo_select: blockdsp h264chroma hpeldsp idctdsp me_cmp mpeg_er
 * videodsp; me_cmp_select: fdctdsp idctdsp pixblockdsp; mpeg_er_select: error_resilience). config.h includes it after
 * each platform's header (every platform: the PC tests it too). */
#undef CONFIG_MPEG1VIDEO_DECODER
#define CONFIG_MPEG1VIDEO_DECODER 1
#undef CONFIG_MPEG2VIDEO_DECODER
#define CONFIG_MPEG2VIDEO_DECODER 1
#undef CONFIG_MPEGVIDEO
#define CONFIG_MPEGVIDEO 1
#undef CONFIG_BLOCKDSP
#define CONFIG_BLOCKDSP 1
#undef CONFIG_H264CHROMA
#define CONFIG_H264CHROMA 1
#undef CONFIG_HPELDSP
#define CONFIG_HPELDSP 1
#undef CONFIG_IDCTDSP
#define CONFIG_IDCTDSP 1
#undef CONFIG_ME_CMP
#define CONFIG_ME_CMP 1
#undef CONFIG_MPEG_ER
#define CONFIG_MPEG_ER 1
#undef CONFIG_ERROR_RESILIENCE
#define CONFIG_ERROR_RESILIENCE 1
#undef CONFIG_VIDEODSP
#define CONFIG_VIDEODSP 1
#undef CONFIG_FDCTDSP
#define CONFIG_FDCTDSP 1
#undef CONFIG_PIXBLOCKDSP
#define CONFIG_PIXBLOCKDSP 1
