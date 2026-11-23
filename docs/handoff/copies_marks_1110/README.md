# Machine copies of functions with atomics (SASRT, 2026-11-10 evening)

For RR6 (the ultimate base) and the Blur port (the user: "did you improve the machine copy generation? If you did send
it to rr6 for the ultimate base and send it to blur session"). Tool-level change, every port with katamari-nx's /
banjo-nx's `tools/localize_native.py` and the bulk list can take it.

## What changed

`tools/localize_native.py` refused every function with a guest atomic: the lwarx / stwcx. pairs (the generator writes a
reservation load into the function's local `reserved`, then `REX_GUEST_CAS` on the same word), `sync` / `lwsync`
fences (`std::atomic_thread_fence`) and `log2f`. In SASRT's handheld race that was **3,741 of the 7,367 samples of
generated code** (the game's lock-free queues and ref counts are everywhere: Main XThread, SlRenderer, the worker
threads). The refusal is there for the guard: its logged forms run a call on copies of the registers, roll the memory
back and run it again, and an atomic operation in shared memory must not be done twice.

Now a copy keeps those statements as they are (the running form, `Fast`, does the same atomic operations on the same
guest words; the registers are in locals as for every copy) and each reservation load, compare-and-swap and fence is
preceded by `if (s.Open()) return;`:
- `Fast` (and `Counting`): `Open()` is a constant false, the line folds away;
- `Logged` and the `o_` forms (the guard): the run stops before the first atomic, and that call is not compared, the
  same path as a call outside the copy.

`log2f` is pure and allowed. `SASRT_LOCALIZE_ATOMICS=0` in the environment refuses them again (the old behaviour).
`INDEX_FORMAT` goes 8 -> 9 (the cached index is rebuilt).

`files/localize_native_atomics.patch`: made on the ultimate base's own `tools/localize_native.py` (4 hunks; it also
applies to blur-nx's, checked: `patch -p1 --dry-run -l` from the repository root). Both trees' `banjo_hot_common.h`
already give `Open()` to every policy.

## How to use it

1. `patch -p1 -l < localize_native_atomics.patch`
2. Remake the bulk list from your console profiles so the newly fitting functions go in:
   `python tools/switch_hot_bulk.py PROFILE ELF [...] --write app/src/cpu/hot/localized_bulk.txt --merge --min-samples 1`
   (SASRT: 1,172 -> 1,871 copies; left out only the app's own hooks, 5 tiny leaves, 2 raw guest accesses, 2 time-base
   reads, 1 threaded dispatch, 1 MMIO: about 90 % of the generated-code samples now in copies.)
3. The post-codegen steps (the localizer runs inside them), then the build.
4. **A new PGO profile.** Adding names to the bulk list changes the post-codegen analyses (the lists name functions
   as address-taken): SASRT's tree changed in 177 files, and every function changed since the PGO session keeps no
   profile. SASRT's first race of the new build was slower (Main XThread +16-20 % a frame) for that reason, the
   copies switched off by their keys included (cp2). **And clean the build folder before the `use` build**: Ninja does
   not track the `.gcda` files, so a folder already built with PGO `use` relinks the old objects with the new profile
   unused (`cmake --build <folder> --target clean` first).

## Evidence (SASRT, the console, handheld 1020/460/1600)

- The dense guard (`banjo_hot_guard_calls = 4000`, `banjo_hot_guard_period = 64`), one session through the menus and
  the race start: **3,275,697 calls compared with the recompiled originals, 0 differences** (15 differed once and not
  when repeated: other threads' writes between the two runs, the guard's own rule); 1,513 of the 1,869 bulk copies
  reached; 158 copies contain the atomic forms. 0 GPU fence timeouts, nothing visible.
- The per-thread share of plain generated code fell: Main XThread 25 % -> 10 %, SlRenderer 19 -> 13 %, SlAnimManager
  11 -> 2 %, SlParticleThread 45 -> 9 %.
- The speed: being measured tonight on a retrained PGO profile (the first numbers were on the stale profile, see 4.);
  a follow-up message gives them.

## For a port whose `tools/switch_hot_bulk.py` reads the link map (katamari-nx's form, SASRT's)

Under PGO + LTO the map names a hot function `hot.__imp__sub_X` and every object is an `ltrans` file, so the tool saw no
generated function at all (SASRT's bulk list had not grown since the first PGO build). SASRT's fix in
`demangled_kind`: strip `hot.` / `unlikely.` / `startup.` / `exit.` from the name, and count a `sub_X` name in an
ltrans object as generated (the app's hooks are still left out by `localize_native.Hooks`). The base's and Blur's tool
read an unstripped ELF with `nm`, where neither happens.
