# Lays out the Switch SD card folder in out\nx\sdcard\switch\sasrt-nx: the NRO (it must be the optimised codegen), its
# settings (app\sasrt_switch.toml as sasrt.toml), the testing notes and the shader package; the NRO's map goes to
# out\nx\sdcard_sasrt.map. The game files are yours and stay out of the repository:
#   -IncludeGame              adds the game_root folder as it is, plus out\pc\dlc (the DLC packages, if extracted);
#   -IncludeGame -Pack        adds it as the asset cache instead (assets\game_root.nxpack + .nxidx, built here with
#                             tools\build_asset_pack.py when missing or older than the folder).
# The loose folder is the default for this game: it is 22 files (no thousands of small opens to save), and its pack is
# 4.7 GB, over the 4 GiB file limit of FAT32 cards (the largest single file, 3.1 GB, fits). -Pack is for exFAT cards.
# By hand:
#   sdmc:/switch/sasrt-nx/game_root/   <- assets\game_root
#   sdmc:/switch/sasrt-nx/dlc/         <- out\pc\dlc (optional)
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\win\package_switch.ps1 [-IncludeGame [-Pack]]
param([switch]$IncludeGame, [switch]$Pack)
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$dest = Join-Path $root 'out\nx\sdcard\switch\sasrt-nx'
New-Item -ItemType Directory -Force $dest | Out-Null
$nro = Join-Path $root 'out\nx\sasrt.nro'
if (-not (Test-Path $nro)) { throw "no NRO at ${nro}: run tools\win\build_switch_package.ps1 first" }
# One NRO, the optimised codegen (the user's rule of 2026-10-06; docs/enhancements.md, "Build-time"): a classic build is
# for diagnosis on the PC only and never goes in the SD folder.
python (Join-Path $root 'tools\check_switch_build.py') --flavour-only $nro
if ($LASTEXITCODE -ne 0) { throw "$nro is not the optimised codegen: rebuild with tools\win\build_switch_package.ps1" }
Copy-Item -Force $nro (Join-Path $dest 'sasrt.nro')
# The map of the packaged NRO, for its console CPU profile (tools\switch_hot_functions.py --map): kept outside the SD
# folder and replaced only with the NRO, so a later build does not leave the NRO on the card without its map.
Copy-Item -Force (Join-Path $root 'out\nx\sasrt.map') (Join-Path $root 'out\nx\sdcard_sasrt.map')
# The second NRO of the former codegen A/B pair, from an earlier package.
Remove-Item -Force (Join-Path $dest 'sasrt_optimised.nro') -ErrorAction SilentlyContinue
Copy-Item -Force (Join-Path $root 'app\sasrt_switch.toml') (Join-Path $dest 'sasrt.toml')
Copy-Item -Force (Join-Path $root 'docs\switch-testing.md') (Join-Path $dest 'README.md')
# Premade enhancement configurations (all off, CPU off, verify, ...): docs/enhancements.md. The generated configs of an
# earlier package are removed first, so one that no longer exists cannot stay behind with outdated keys (sa2-nx's
# finding); every config is written again just below.
Remove-Item -Force (Join-Path $dest 'configs\*.toml') -ErrorAction SilentlyContinue
python (Join-Path $root 'tools\make_enhancement_configs.py') --out (Join-Path $dest 'configs') | Out-Null
# sasrt-nx (2026-10-21): the console tests of Renut's deko3d renderer (sasrt_renut_*.toml; the script says what each is).
python (Join-Path $root 'tools\make_renut_test_configs.py') --out (Join-Path $dest 'configs') | Out-Null
# The profiler is switched by the configuration (switch_profile_stacks and masseffect_gpu_marks_categories: on in
# sasrt.toml and every config but sasrt_cpu_verify.toml). An earlier package's logs/rex/stacks_profile.flag would turn
# the CPU sampler on in verify mode too, so it is not made any more and an old one is removed.
Remove-Item -Force (Join-Path $dest 'logs\rex\stacks_profile.flag') -ErrorAction SilentlyContinue
foreach ($f in 'sasrt_shaders.mesp', 'sasrt_shaders.mesp.idx') {
    Copy-Item -Force (Join-Path $root "out\shaders\$f") (Join-Path $dest $f)
}
# The native deko3d renderer's DKSH cache (configs\sasrt_renderer_deko3d.toml; tools\deko3d_variant_cache.py), read
# next to the NRO: without it the console compiles every shader variant with uam at its first draw.
$dksh = Join-Path $root 'out\deko3d_shaders\deko3d_shaders.bin'
if (Test-Path $dksh) { Copy-Item -Force $dksh (Join-Path $dest 'deko3d_shaders.bin') }
if ($IncludeGame) {
    if (-not $Pack) {
        robocopy (Join-Path $root 'assets\game_root') (Join-Path $dest 'game_root') /E /NFL /NDL /NJH /NJS | Out-Null
        foreach ($f in 'game_root.nxpack', 'game_root.nxidx') {
            Remove-Item -Force (Join-Path $dest $f) -ErrorAction SilentlyContinue
        }
    } else {
        & python (Join-Path $root 'tools\build_asset_pack.py') (Join-Path $root 'assets\game_root') --if-stale
        if ($LASTEXITCODE) { throw 'asset pack build failed' }
        foreach ($f in 'game_root.nxpack', 'game_root.nxidx') {
            Copy-Item -Force (Join-Path $root "assets\$f") (Join-Path $dest $f)
        }
        # A loose folder from an earlier package is no longer read (the pack wins): drop it from the staging copy.
        if (Test-Path (Join-Path $dest 'game_root')) { Remove-Item -Recurse -Force (Join-Path $dest 'game_root') }
    }
    if (Test-Path (Join-Path $root 'out\pc\dlc')) {
        robocopy (Join-Path $root 'out\pc\dlc') (Join-Path $dest 'dlc') /E /NFL /NDL /NJH /NJS | Out-Null
    }
}
Get-ChildItem $dest | Select-Object Name, Length
