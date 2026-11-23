# Driving the user's Switch from the PC: sys-botbase and sys-ftpd (a guide for the other ports)

Written 2026-11-11 by the sasrt-nx (Sonic & All-Stars Racing Transformed) session at the user's request, for the Viva
Piñata and Blur sessions. The tools came from rr6-nx (credit the Ridge Racer 6 port); sasrt-nx's copies are in
`D:\sonic transformed\sasrt-nx\tools\` (`switch_remote.py`, `console_run.py`, `console_race.py`). Copy them into your
port's `tools/` and change the names listed in section 5.

## 1. What runs on the console

The user runs two sysmodules under Atmosphere:
- **sys-botbase** (masagrator's fork), TCP **6000**: controller input, screenshots, title id, memory reads.
- **sys-ftpd-light**, TCP **5000**, anonymous: the SD card.

The console's LAN address is in `out/switch_host.txt` (first line; 192.168.1.197 lately). Both are outbound connections
from the PC; nothing on the PC listens. If neither port answers but ping does, the console is asleep: only the user can
wake it.

## 2. The user's rules (all of them apply; they are the user's, not suggestions)

1. **On the SD card, touch only your port's own folder** (`/switch/<port>`). `switch_remote.py` checks every FTP path
   against `SD_ROOT` and refuses anything outside it. **Never touch `/atmosphere`** over FTP.
2. **The Album is read-only**: `album-ls` and `album-get` only, nothing written or deleted there.
3. **Before pressing A on the Home menu, take a screenshot and check that your game's tile is the selected one** (its
   title shows above it). Never move the Home cursor blind; if something else is selected, stop and tell the user.
   After launching, check the running title id before sending timed inputs; a wrong title stops the run.
4. **Close the game with HOME, X, A** (`close_game` / `console_race.py close`). `killGame` leaves the system's error
   dialog.
5. **No clock or boost changes by you.** The user sets clocks (handheld 1020 / 460.8 / 1600 MHz lately; sometimes max
   for slow checks). Check the profile's `clocks:` line before trusting a performance number.
6. **One session drives the console at a time.** The sessions share it by asking each other over SendMessage ("is the
   console free?", wait for "free", say when you are done). The user's standing permission (2026-11-08): no need to ask
   the user before a console run, but do coordinate with the other sessions. Leave the console on the Home menu.
7. **Guard / verify / dense-check runs go to the emulator (Ryujinx) or the PC, not the console**: they make the game
   crawl. The console is for performance races, PGO training races and picture checks.
8. **No screenshots while measuring performance**: `pixelPeek` stalls the game ~250 ms (those are the "10 s stutters"
   SASRT chased for a while). One screenshot early in the race to confirm you are racing is fine; leave it out of the
   measured windows.

## 3. The tools

```
python tools/switch_remote.py shot [OUT.jpg]        the screen (pixelPeek; a few seconds)
python tools/switch_remote.py click A [B ...]       taps; hold BTN [ms]; chord A B X Y [ms]; stick L|R X Y [ms] (-1..1, y up)
python tools/switch_remote.py title                 getTitleID (empty / 0 on the Home menu)
python tools/switch_remote.py ls [PATH]             FTP, inside /switch/<port> only; get REMOTE [LOCAL]; put LOCAL REMOTE; rm REMOTE
python tools/switch_remote.py album-ls / album-get  the Album, read only
python tools/switch_remote.py raw "CMD ..."         a sys-botbase command from an allow-list (no memory writes, no files)
python tools/console_race.py OUT launch             one A on Home (after you read a screenshot), waits for your title id
python tools/console_race.py OUT menus [S]          mashes PLUS for 15 s, then holds A 250 ms every 2 s for S seconds, a shot every 8 s
python tools/console_race.py OUT drive [S ...]      holds ZR for S seconds (shots every 10 s: not for performance runs)
python tools/console_race.py OUT close              HOME, X, A; checks the Home menu
python tools/console_run.py NAME --logs-only        fetches the newest <port>_*.log and logs/rex/ into out/console_runs/NAME
```

sys-botbase protocol notes (if you write your own client): ASCII lines ending `\r\n`, replies end `\n`; send
`configure echoCommands 0` first; `click A`, `press ZR` / `release ZR`, `setStick LEFT x y` (-32767..32767, y up;
`setStick LEFT 0 0` releases); `getTitleID` (take the LAST word of the reply; 0 on Home); `pixelPeek` returns a hex
JPEG (give it a 30 s timeout); `detachController` makes the next press attach a new virtual controller (needed after the
console slept: presses were ignored until then). Buttons: A B X Y L R ZL ZR PLUS MINUS HOME CAPTURE DUP DDOWN DLEFT
DRIGHT LSTICK RSTICK. Never use the memory-write commands.

## 4. A performance race, the way SASRT does it

```
python tools/switch_remote.py shot out/console_runs/RUN/00_home.jpg     # read it: your tile selected?
python tools/console_race.py out/console_runs/RUN launch
# wait ~40 s after launch: menu presses sent earlier were lost (the game was still booting)
python tools/console_race.py out/console_runs/RUN menus 76   # SASRT: 76 s of A (40 ran out in loading: 2026-11-19)
python drive_quiet.py out/console_runs/RUN 200        # ZR held, re-pressed every 10 s, ONE shot at 20 s, no others
python tools/console_race.py out/console_runs/RUN close
python tools/console_run.py RUN --logs-only
```

`drive_quiet.py` is a 20-line script (sasrt-nx's is in its session scratchpad; easy to rewrite): connect, check the title
id, `press ZR`, loop: sleep 10 s, re-send `press ZR`, take one `shot` at 20 s, then stop. Chain the steps in one
background shell command so nothing waits on you between them.

Upload an NRO or toml first with `put` (`console_run.put(host, local, 'sasrt.nro')`): ~70-130 s for a 70-120 MB NRO.

## 5. Lessons (each one cost a run)

- **Git Bash paths**: set `MSYS_NO_PATHCONV=1` so card paths like `/switch/...` reach Python unchanged, but then
  **pass local paths to Windows Python as `C:/...` or `D:/...`, never `/c/...`** (Python cannot open `/c/...`; a race
  once sat idle at the start line because the drive script's path was mangled).
- **sys-ftpd-light runs out of sockets** after a couple of transfers that close their data connection (`451` on PASV for
  ~40 s). `switch_remote.ftp_get_many` keeps one session and reads known sizes (~2.5 MB/s, no failures). `console_run`'s
  fetch may stop at `logs/rex: 451` or `[WinError 10054]` after the main log: fetch the profile you need on its own with
  `get` a few seconds later.
- **`450 failed to open file`**: the game still has its log open. Fetch logs after closing the game.
- **Profile numbering**: the SDK's `rex_profile_NNN.log` is numbered one below the session log (`<port>_NNN.log`),
  because the profiler starts before the log exists. Stack sampling needs an empty `stacks_profile.flag` in
  `/switch/<port>/logs/rex/` (the toml key does not work).
- **Menus in handheld**: clicks were missed on the character select; hold A 250 ms instead. Mash PLUS for the title
  screen, then A, then hold ZR in the race.
- **The console sleeps** if left alone long enough; sys-botbase and FTP then time out while ping still answers. Tell the
  user; after it wakes, the first presses may need `detachController`.
- **PGO training on the console**: the instrumented NRO writes `pgo/<port>_pgo_N.stream` next to the NRO when the game
  closes; fetch the newest one (`ls pgo`). The counts are execution counts, so training in Ryujinx is equally valid and
  saves console time (Blur does it there).
- **Keep every run's NRO, toml and screenshots** in `out/console_runs/RUN/`: comparing builds later needs them, and the
  map / ELF of the same build is needed to symbolise its profile.
- **Restore the shipping toml on the card** after a test toml, and leave the console on the Home menu for the next
  session.

## 6. What to change when you copy the tools

- `switch_remote.py`: `SD_ROOT` (`/switch/<port>`).
- `console_run.py`: your forwarder's **title id** (`SASRT_TITLE`; read it once with `switch_remote.py title` while your
  game runs; with 0 the script refuses to launch), the log name pattern (`sasrt_*.log`), the toml/NRO names.
- The host: `--host`, an environment variable, or `out/switch_host.txt`.
