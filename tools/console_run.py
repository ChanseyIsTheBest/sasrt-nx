#!/usr/bin/env python3
"""sasrt-nx (2026-11-08, from rr6-nx's tools/console_run.py of 2026-11-05, credit the Ridge Racer 6 port): one test run
on the console, unattended, through tools/switch_remote.py's sys-botbase and ftp. Only with the user's word.

    python tools/console_run.py NAME [--toml FILE] [--nro FILE] [--put LOCAL=REMOTE ...] [--no-launch] [--no-kill]
                                [--script "T:ACTION,T:ACTION,..."] [--script-file FILE] [--until SECONDS]
                                [--logs-only]

Closes nothing by itself: a launch needs the home menu with this game's icon selected (read a screenshot first,
tools/switch_remote.py shot). Uploads the toml as sasrt.toml (and the NRO as sasrt.nro if given), presses A once, then
at T seconds after the game was seen running runs each ACTION: `shot`, `click A`, `press ZR`, `release ZR`,
`stick L x y`, `chord A B X Y` (the shadow dump's press). At --until it closes the game (HOME, X, A), fetches the
newest sasrt_*.log and logs/rex/* and writes everything to out/console_runs/NAME, with shots named by their second
and a sheet of them. Every card path goes through switch_remote.sd_path, so the user's rule about the SD card holds.
SASRT_TITLE is read once with `tools/switch_remote.py title` while the user has the game running; until it is set
this script refuses to launch.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import switch_remote as sr  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')

# This game's forwarder on the user's console: 0 until read once (getTitleID while it runs); a launch is refused at 0.
SASRT_TITLE = 0x05B2275AF7F68000  # the forwarder on the user's console, read 2026-11-08


def put(host, local, remote):
    began = time.time()
    sr.ftp_put_file(host, local, sr.sd_path(remote))
    print('put %s -> %s (%.1f MB in %.0f s)' % (os.path.basename(local), remote, os.path.getsize(local) / 1048576.0,
                                               time.time() - began))


def fetch_logs(host, out):
    """The newest sasrt_*.log, and logs/rex (the profiler's) whole: a connection per file (sys-ftpd-light's 451s)."""
    got = []
    sizes = sr.ftp_sizes(host, sr.sd_path('logs'))
    logs = sorted(n for n in sizes if n.startswith('sasrt_') and n.endswith('.log'))
    for n in logs[-1:]:
        sr.ftp_get_file(host, sr.sd_path('logs/' + n), os.path.join(out, n))
        print('log', n, os.path.getsize(os.path.join(out, n)), 'bytes')
        got.append(n)
    try:
        rex = sr.ftp_sizes(host, sr.sd_path('logs/rex'))
        os.makedirs(os.path.join(out, 'rex'), exist_ok=True)
        for n in sorted(rex):
            sr.ftp_get_file(host, sr.sd_path('logs/rex/' + n), os.path.join(out, 'rex', n))
            got.append('rex/' + n)
    except Exception as e:
        print('logs/rex:', e)
    return got


def title_of(bot):
    """The running title's id, 0 on the home menu."""
    # killGame answers "ok", which can arrive ahead of this answer: the last word of the reply is the one asked for.
    words = bot.ask('getTitleID', timeout=8.0).split()
    t = words[-1] if words else ''
    return int(t, 16) if t and all(c in '0123456789abcdefABCDEF' for c in t) else 0


def running(bot):
    return title_of(bot) != 0


def close_game(bot):
    """The normal way, HOME, X, A: killGame leaves the system's 'closed because an error occurred' dialog (the user,
    2026-11-05), which then needs A. killGame only as the fallback."""
    for btn in ('ZR', 'A', 'B', 'X', 'Y'):  # whatever the timeline left held (the accelerator, the dump chord)
        bot.send('release ' + btn)
    bot.send('setStick LEFT 0 0')
    time.sleep(0.3)
    bot.send('click HOME')
    time.sleep(2.5)
    bot.send('click X')
    time.sleep(1.5)
    bot.send('click A')
    for _ in range(24):
        time.sleep(0.5)
        if not running(bot):
            time.sleep(1.5)
            return 'closed'
    print('normal close failed: killGame, then A for its dialog')
    bot.ask('killGame', timeout=15.0)
    time.sleep(4)
    bot.send('click A')
    time.sleep(2)
    return 'killed'


def launch(bot):
    """One A on the icon a screenshot has just shown selected (read it first, tools/switch_remote.py shot): no cursor
    moves, no second press (the Ridge Racer session's blind launches opened the eShop and another game). Only this
    game's own title id starts the timeline; the time it was seen running counts as the start."""
    if not SASRT_TITLE:
        print('SASRT_TITLE is 0: read it once with tools/switch_remote.py title while the game runs; no launch')
        return None
    bot.send('click A')
    began = time.time()
    # sasrt-nx (2026-11-10): 30 s, not 10: in handheld at stock clocks the title id showed up after more than 10 s and
    # the run stopped with the game starting.
    for _ in range(60):
        time.sleep(0.5)
        t = title_of(bot)
        if t == SASRT_TITLE:
            print('launched sasrt')
            return began
        if t:
            print('WRONG TITLE %016X running: stopping, no more presses' % t)
            return None
    print('the game did not start: stopping, no more presses')
    return None


def sheet(out, shots):
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return
    if not shots:
        return
    cols = min(4, len(shots))
    rows = (len(shots) + cols - 1) // cols
    w, h = 480, 270
    img = Image.new('RGB', (cols * w, rows * h))
    for i, (t, path) in enumerate(shots):
        tile = Image.open(path).convert('RGB').resize((w, h))
        ImageDraw.Draw(tile).text((4, 4), '%d s' % t, fill=(255, 255, 0))
        img.paste(tile, ((i % cols) * w, (i // cols) * h))
    img.save(os.path.join(out, 'sheet.jpg'), quality=85)


def main():
    a = argparse.ArgumentParser()
    a.add_argument('name')
    a.add_argument('--toml')
    a.add_argument('--nro')
    a.add_argument('--put', action='append', default=[])
    a.add_argument('--script', default='')
    a.add_argument('--script-file', help='the --script text in a file (long timelines)')
    a.add_argument('--until', type=float, default=120)
    a.add_argument('--no-launch', action='store_true')
    a.add_argument('--no-kill', action='store_true')
    a.add_argument('--logs-only', action='store_true', help='fetch the logs and stop (no presses at all)')
    a.add_argument('--host', help='the console (else SASRT_SWITCH_HOST, else out/switch_host.txt)')
    args = a.parse_args()
    host = args.host or sr.host_of([])
    out = os.path.join(ROOT, 'out', 'console_runs', args.name)
    os.makedirs(out, exist_ok=True)
    if args.logs_only:
        print('fetched', fetch_logs(host, out))
        print('out', os.path.normpath(out))
        return

    bot = sr.Bot(host, timeout=15)
    running_now = title_of(bot)
    if not args.no_launch and running_now:
        # No close here: a launch needs a screenshot of the home menu read first, and another game is not this tool's to close.
        print('a game is running (%016X): stopping, nothing sent' % running_now)
        bot.close()
        sys.exit(1)
    if args.no_launch and running_now != SASRT_TITLE:
        print('sasrt is not running (%016X): stopping, nothing sent' % running_now)
        bot.close()
        sys.exit(1)
    if args.toml:
        put(host, args.toml, 'sasrt.toml')
    if args.nro:
        put(host, args.nro, 'sasrt.nro')
    for spec in args.put:
        local, remote = spec.split('=', 1)
        put(host, local, remote)

    steps = []
    text = open(args.script_file, encoding='utf-8').read() if args.script_file else args.script
    for item in filter(None, (s.strip() for s in text.split(','))):
        t, action = item.split(':', 1)
        steps.append((float(t), action.strip()))
    steps.sort(key=lambda s: s[0])

    if not args.no_launch:
        start = launch(bot)
        if start is None:
            bot.close()
            sys.exit(1)
    else:
        start = time.time()
    print('started', time.strftime('%H:%M:%S'))
    shots = []
    for t, action in steps:
        if t > args.until:
            break
        wait = start + t - time.time()
        if wait > 0:
            time.sleep(wait)
        try:
            if action == 'shot':
                path = os.path.join(out, 'shot_%04d.jpg' % t if t == int(t) else 'shot_%07.2f.jpg' % t)
                bot.shot(path)
                shots.append((t, path))
            elif action.startswith('stick '):
                _, which, x, y = action.split()
                bot.send('setStick %s %d %d' % ('LEFT' if which.upper().startswith('L') else 'RIGHT',
                                                int(float(x) * 32767), int(float(y) * 32767)))
            elif action.startswith('chord '):
                bot.chord(action.split()[1:], 300)
            else:
                bot.send(action)
        except (OSError, ValueError) as e:
            print('step', t, action, 'failed:', e)
    wait = start + args.until - time.time()
    if wait > 0:
        time.sleep(wait)
    alive = False
    try:
        alive = title_of(bot) == SASRT_TITLE
    except OSError as e:
        print('botbase:', e)
    print('game running at the end:', alive, '; finished', time.strftime('%H:%M:%S'))
    if alive and not args.no_kill:
        print('closing:', close_game(bot))
    bot.close()
    sheet(out, shots)
    if not args.no_kill:
        try:
            fetch_logs(host, out)
        except (OSError, EOFError) as e:
            print('log fetch stopped:', e)
    print('out', os.path.normpath(out))


if __name__ == '__main__':
    main()
