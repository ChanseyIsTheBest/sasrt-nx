#!/usr/bin/env python3
"""sasrt-nx (2026-11-08): one console race in phases, through tools/switch_remote.py's sys-botbase; each phase is run on
its own so its screenshots can be read before the next (the user's rules: docs/switch-testing.md, "Driving the console
from the PC"). Every console run needs the user's word.

    python tools/console_race.py OUT launch          one A on the home menu (a screenshot must have shown this game's
                                                     tile selected), then waits for this game's title id
    python tools/console_race.py OUT menus [S]       mashes PLUS for 15 s, then A (the Switch's B with the Xbox layout,
                                                     the default since 2026-11-19: SASRT_CONFIRM) for S seconds
                                                     (default 40; 76 reaches the race), a shot
                                                     every 8 s (the user, 2026-11-08: "mash START for a bit and then A")
    python tools/console_race.py OUT race [N] [GAP]  holds ZR, presses A+B+X+Y N times (default 8) GAP s apart (15),
                                                     a shot 4 s after each
    python tools/console_race.py OUT drive [S [A B [C D X Y]]] holds ZR for S seconds (60) with a shot every 10 s,
                                                     no chord (between A and B seconds: shots back to back;
                                                     between C and D: the left stick held at X, Y)
    python tools/console_race.py OUT close           releases everything, HOME, X, A; checks the home menu
OUT is the run's folder (out/console_runs/NAME); shots go there. The host is out/switch_host.txt (switch_remote).
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import console_run as cr  # noqa: E402
import switch_remote as sr  # noqa: E402

# sasrt-nx (2026-11-19): the Switch button that accepts in the game's menus. input_xbox_layout is on by default since
# 2026-11-19 (the user's choice): face buttons by position, so the bottom button (the Switch's B) is the game's A. A
# toml with input_xbox_layout = false needs SASRT_CONFIRM=A.
CONFIRM = os.environ.get('SASRT_CONFIRM', 'B').upper()


def shot(bot, out, name):
    path = os.path.join(out, name + '.jpg')
    try:
        bot.shot(path)
        print(time.strftime('%H:%M:%S'), 'shot', path, flush=True)
    except (OSError, ValueError) as e:
        print('shot failed:', e, flush=True)


def main():
    out, phase, rest = sys.argv[1], sys.argv[2], sys.argv[3:]
    os.makedirs(out, exist_ok=True)
    bot = sr.Bot(sr.host_of([]), timeout=20)
    try:
        title = cr.title_of(bot)
        if phase == 'launch':
            if title:
                sys.exit('a title is running (%016X): nothing sent' % title)
            began = cr.launch(bot)
            if began is None:
                sys.exit(1)
            print(time.strftime('%H:%M:%S'), 'running', flush=True)
            return
        if title != cr.SASRT_TITLE:
            sys.exit('this game is not running (%016X): nothing sent' % title)
        if phase == 'menus':
            secs = float(rest[0]) if rest else 40.0
            end = time.time() + 15
            while time.time() < end:
                bot.send('click PLUS')
                time.sleep(1.5)
            shot(bot, out, 'menus_plus')
            t0 = time.time()
            last = t0
            while time.time() < t0 + secs:
                # sasrt-nx (2026-11-10): held 250 ms, not clicked: in handheld the character select missed the clicks
                bot.send('press ' + CONFIRM)
                time.sleep(0.25)
                bot.send('release ' + CONFIRM)
                time.sleep(1.75)
                if time.time() - last > 8:
                    shot(bot, out, 'menus_a_%03d' % (time.time() - t0))
                    last = time.time()
        elif phase == 'race':
            n = int(rest[0]) if rest else 8
            gap = float(rest[1]) if len(rest) > 1 else 15.0
            bot.send('press ZR')
            t0 = time.time()
            for i in range(n):
                wait = t0 + 2 + i * gap - time.time()
                if wait > 0:
                    time.sleep(wait)
                bot.chord(['A', 'B', 'X', 'Y'], 300)
                bot.send('press ZR')
                print(time.strftime('%H:%M:%S'), 'chord', i + 1, flush=True)
                time.sleep(4)
                shot(bot, out, 'race_w%02d' % i)
                bot.send('press ZR')
        elif phase == 'drive':
            secs = float(rest[0]) if rest else 60.0
            # sasrt-nx (2026-11-09): optional DENSE_FROM DENSE_TO (seconds): shots back to back in that window (the
            # loop section, to look at an artifact), every 10 s elsewhere
            dense = (float(rest[1]), float(rest[2])) if len(rest) > 2 else None
            # sasrt-nx (2026-11-09, the user: "driving up left on lap 2 should help you see it"): optional STICK_FROM
            # STICK_TO X Y: the left stick held at (X, Y) in -1..1 (y up) in that window of the drive, centred after.
            steer = (float(rest[3]), float(rest[4]), float(rest[5]), float(rest[6])) if len(rest) > 6 else None
            steering = False
            bot.send('press ZR')
            t0 = time.time()
            while time.time() < t0 + secs:
                now = time.time() - t0
                if steer:
                    want = steer[0] <= now < steer[1]
                    if want != steering:
                        x, y = (steer[2], steer[3]) if want else (0.0, 0.0)
                        bot.send('setStick LEFT %d %d' % (int(x * 32767), int(y * 32767)))
                        steering = want
                        print(time.strftime('%H:%M:%S'), 'stick', 'held' if want else 'centred', flush=True)
                in_dense = bool(dense and dense[0] <= now < dense[1])
                if not in_dense:
                    time.sleep(10 if not steer else 2)
                    if steer and int(now) % 10 >= 2:
                        bot.send('press ZR')
                        continue
                # tenths in the dense window: two shots never share a name
                shot(bot, out, ('drive_%05.1f' if in_dense else 'drive_%03d') % (time.time() - t0))
                bot.send('press ZR')
            if steering:
                bot.send('setStick LEFT 0 0')
        elif phase == 'close':
            print(time.strftime('%H:%M:%S'), 'closing:', cr.close_game(bot), flush=True)
            time.sleep(1)
            print('title now', repr(bot.ask('getTitleID', timeout=8)), flush=True)
            shot(bot, out, 'home_after_close')
        else:
            sys.exit('unknown phase ' + phase)
    finally:
        bot.close()


if __name__ == '__main__':
    main()
