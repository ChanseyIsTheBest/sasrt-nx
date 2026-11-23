# sasrt-nx (2026-11-19): a local split-screen race for N players (2-4) with the four-pad sys-botbase, from the Home menu
# with SASRT's tile selected (checked by the caller). Xbox layout on: a virtual pad's B is the game's A.
#   python split_race.py N OUT [drive_seconds] [capture_at] [steer_s]
import os
import sys
import time

sys.path.insert(0, 'D:/sonic transformed/sasrt-nx/tools')
import console_run as cr  # noqa: E402
import switch_remote as sr  # noqa: E402

n = int(sys.argv[1])
out = sys.argv[2]
drive = float(sys.argv[3]) if len(sys.argv) > 3 else 70.0
captures = [float(v) for v in sys.argv[4].split(',')] if len(sys.argv) > 4 and sys.argv[4] not in ('', '0') else []  # seconds into the drive: hold CAPTURE (the last ~10 s to the Album)
steer_s = float(sys.argv[5]) if len(sys.argv) > 5 else 0.0  # the sticks swap sides every steer_s seconds (0: straight)
os.makedirs(out, exist_ok=True)
b = sr.Bot(sr.host_of([]), timeout=30)


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def shot(name):
    b.shot(os.path.join(out, name + '.jpg'))
    log('shot', name)


def tap(btn, pad=1, ms=250):
    b.send('pad %d' % pad)
    b.send('press ' + btn)
    time.sleep(ms / 1000.0)
    b.send('release ' + btn)
    b.send('pad 1')


try:
    if cr.title_of(b) != 0:
        sys.exit('a title is running: nothing sent')
    # 2026-11-20: the virtual pad attached afresh (the console in hand made the handheld controller the active one and
    # the first A went nowhere), and A pressed again while nothing runs (it does not move the Home menu's cursor).
    b.send('detachController')
    time.sleep(1.0)
    t0 = time.time()
    for attempt in range(3):
        tap('A')  # Home: start the selected tile (the Home menu is by letter)
        t1 = time.time()
        while time.time() < t1 + 10 and cr.title_of(b) == 0:
            time.sleep(1)
        if cr.title_of(b) != 0:
            break
        log('A at Home: nothing started yet, again')
    while time.time() < t0 + 60 and cr.title_of(b) != cr.SASRT_TITLE:
        time.sleep(1)
    if cr.title_of(b) != cr.SASRT_TITLE:
        sys.exit('SASRT did not start')
    log('running')
    time.sleep(45)
    for _ in range(8):
        tap('PLUS', ms=120)
        time.sleep(1.5)
    # The autosave warning comes when the title is done, at no fixed time: each screen is compared with a reference
    # (the warning's dialog, the main menu's bar) and the press made again until the main menu is there.
    from PIL import Image
    import numpy as np
    refs = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'split_refs')

    def gray(path, box):
        return np.asarray(Image.open(path).convert('L').crop(box).resize((64, 32)), float)

    W_BOX, M_BOX = (340, 180, 940, 480), (80, 520, 1200, 700)
    warn_ref, main_ref = gray(os.path.join(refs, 'warning.jpg'), W_BOX), gray(os.path.join(refs, 'main.jpg'), M_BOX)
    at_main = False
    for attempt in range(20):
        time.sleep(3)
        name = 's01_%02d' % attempt
        shot(name)
        path = os.path.join(out, name + '.jpg')
        w = np.abs(gray(path, W_BOX) - warn_ref).mean()
        m = np.abs(gray(path, M_BOX) - main_ref).mean()
        log('screen: warning %.1f, main menu %.1f' % (w, m))
        if w < 10:
            tap('B')  # OKAY
        elif m < 22:
            at_main = True
            break
        else:
            tap('PLUS', ms=120)  # the title, or a screen before it
    if not at_main:
        sys.exit('the main menu never came')
    shot('s01b_main')
    for p in range(2, n + 1):
        tap('PLUS', pad=p)
        time.sleep(1.5)
    shot('s02_main_joined')
    tap('DRIGHT', ms=200)
    time.sleep(0.8)
    tap('DRIGHT', ms=200)
    time.sleep(0.8)
    tap('B')  # Custom Game
    time.sleep(4)
    tap('B')  # Local
    time.sleep(5)
    shot('s03_mode')
    tap('B')  # Race
    time.sleep(5)
    tap('B')  # the first cup
    time.sleep(4)
    tap('B')  # Ocean View
    time.sleep(5)
    tap('B')  # Medium
    time.sleep(5)
    shot('s04_lobby')
    tap('B')  # character select
    time.sleep(4)
    shot('s05_chars')
    for p in range(1, n + 1):
        tap('B', pad=p)  # random
        time.sleep(1)
    time.sleep(3)
    tap('PLUS')  # start
    time.sleep(25)
    shot('s06_intro')
    for p in range(1, n + 1):
        tap('B', pad=p)  # continue
        time.sleep(0.5)
    time.sleep(2)
    shot('s07_countdown')  # 2026-11-20: every view sees the same scenery here (view_bright.py compares them)
    # 2026-11-20 (the user: "4 player race at start not moving at all"): SPLIT_STILL=1 holds nothing and steers nothing:
    # every view stays on the start line (the same frames for an A/B's halves); SPLIT_NO_SHOTS=1 takes no shots (stalls).
    still = os.environ.get('SPLIT_STILL', '') == '1'
    if still:
        steer_s = 0.0
    for p in range(1, n + 1):
        if still:
            break
        b.send('pad %d' % p)
        b.send('press ZR')
    b.send('pad 1')
    t1 = time.time()
    log('ZR held on', 0 if still else n, 'pads')
    # Steering (the user: "move the sticks"): the pads turn opposite ways, swapping every steer_s seconds, so the
    # views' cameras part (a view drawing the other camera's world shows at once).
    shots = [] if captures else [(2, 'r02'), (8, 'r08'), (20, 'r20'), (35, 'r35'), (55, 'r55')]  # no stalls in a video
    shot_every = float(os.environ.get('SPLIT_SHOT_EVERY', '0'))  # 2026-11-20: a shot every N s of the drive instead
    if shot_every > 0:
        shots = [(t, 'p%03d' % int(t)) for t in [2 + shot_every * k for k in range(int(drive / shot_every))]]
    if os.environ.get('SPLIT_NO_SHOTS', '') == '1':
        shots = [(5, 'r05')]  # one, early
    next_steer, sign = 0.0, 1
    while time.time() < t1 + drive:
        now = time.time() - t1
        if steer_s > 0 and now >= next_steer:
            for p in range(1, n + 1):
                b.send('pad %d' % p)
                b.send('setStick LEFT %d 0' % (sign * (1 if p % 2 else -1) * 26000))
            b.send('pad 1')
            sign = -sign
            next_steer = now + steer_s
        if shots and now >= shots[0][0]:
            shot(shots.pop(0)[1])
            log('drive', round(now, 1))
        if captures and now >= captures[0]:
            captures.pop(0)
            b.send('pad 1')
            b.send('press CAPTURE')
            time.sleep(1.5)
            b.send('release CAPTURE')
            log('CAPTURE held: the last 30 s to the Album')
        time.sleep(0.25)
    for p in range(1, n + 1):
        b.send('pad %d' % p)
        b.send('setStick LEFT 0 0')
    b.send('pad 1')
    for p in range(1, n + 1):
        b.send('pad %d' % p)
        b.send('release ZR')
    b.send('pad 1')
    log('drive done')
finally:
    b.close()
