# Translates the game (default.xex) to C++ with the host code generator. It builds nothing: build the generator first
# (tools\win\run.ps1 out\host_build.log "cmake --build out/host --target rexglue").
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\codegen.ps1 [-Flavor optimised|classic]
#
# Input:   assets\game_root\default.xex   (tools\god_extract.py or tools\extract_iso.py puts it there)
#          app\sasrt_manifest.toml        (project, game paths, includes)
# Output:  app\generated\                 (C++ of the game and generated\rexglue.cmake; not committed)
#          out\codegen.log                (log of the generator)
#
# -Flavor: the codegen flavour (docs/enhancements.md, "Build-time").
#   optimised (default)  what the PC and the Switch build: app\codegen_flavor.toml = app\perf_overrides.toml (registers
#                        as locals, ...), then tools\pch_no_volatile.py, tools\thunk_calls.py, tools\direct_calls.py and
#                        tools\loop_barriers.py run on the generated code. The SD card gets this one NRO only (the
#                        user's rule of 2026-10-06: no A/B pair of flavours; compare features with sasrt.toml keys).
#   classic              app\codegen_flavor.toml stays empty: the generator's plain output. For diagnosis on the PC
#                        only (is a problem the codegen's?); tools\win\package_switch.ps1 refuses a classic NRO.
# Both write app\generated\codegen_flavor.txt, which the build puts in the first "[enhancements]" log line.
# The PC build re-runs the generator by itself when an input changes; app/CMakeLists.txt appends tools/post_codegen.py
# to that command, so the flavour's steps survive it (the Switch cross build never runs the generator).
param(
    [string]$Rexglue = '',
    [ValidateSet('optimised', 'classic')][string]$Flavor = 'optimised'
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$app = Join-Path $root 'app'
if (-not $Rexglue) {
    $Rexglue = Get-ChildItem (Join-Path $root 'sdk\out') -Recurse -Filter rexglue.exe -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
}
if (-not $Rexglue -or -not (Test-Path $Rexglue)) { throw 'rexglue.exe not found; build it first (see the header)' }
$xex = Join-Path $root 'assets\game_root\default.xex'
if (-not (Test-Path $xex)) { throw "$xex not found; extract your game with tools\god_extract.py first" }

New-Item -ItemType Directory -Force (Join-Path $root 'out') | Out-Null
$flavorToml = Join-Path $app 'codegen_flavor.toml'
if ($Flavor -eq 'optimised') {
    $text = "# optimised codegen: written by tools\codegen.ps1 -Flavor optimised from perf_overrides.toml.`n" +
            (Get-Content -Raw (Join-Path $app 'perf_overrides.toml'))
} else {
    $text = "# classic codegen, for diagnosis on the PC only: no extra options (tools\codegen.ps1 -Flavor classic writes this`n" +
            "# file; the default, -Flavor optimised, copies perf_overrides.toml here). Included by sasrt_manifest.toml.`n"
}
[System.IO.File]::WriteAllText($flavorToml, $text.Replace("`r`n", "`n"))
$log = Join-Path $root 'out\codegen.log'
Write-Host "== codegen ($Flavor) with $Rexglue"
Push-Location $app
try {
    $env:REX_MAX_JUMP_TABLE_ENTRIES = '1024'
    # The loaded image, for the post-codegen steps that read it (tools\ro_constants.py: constants of .rdata;
    # tools\flush_mode_flow.py --image: functions whose address is nowhere in the image). sa2-nx's.
    $env:REXGLUE_DUMP_IMAGE = Join-Path $root 'out\default_image.bin'
    & $env:ComSpec /c "`"$Rexglue`" codegen --ignore-stamp sasrt_manifest.toml > `"$log`" 2>&1"
    $code = $LASTEXITCODE
} finally { Pop-Location }
Get-Content $log -Tail 30
if ($code -ne 0) { throw "codegen failed (exit $code), see out\codegen.log" }

# The flavour's post-codegen steps: the same script the build appends to its own codegen command (app/CMakeLists.txt),
# so a codegen the build re-runs keeps them too.
$env:REXSDK_DIR = Join-Path $root 'sdk'
python (Join-Path $root 'tools\post_codegen.py')
if ($LASTEXITCODE -ne 0) { throw 'tools\post_codegen.py failed' }
Write-Host "done ($Flavor codegen): $app\generated"
