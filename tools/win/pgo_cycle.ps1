# sasrt-nx (2026-11-10, machine-copy idea 28): the PGO session in two commands (docs/pgo-lto.md's three steps), with the
# two traps of 2026-11-10 built in:
#   - a profile merged into a pgo/ that already holds one adds the counts twice: the old profile is moved aside first;
#   - a folder already built with -Pgo use relinks its old objects with a new profile unused (Ninja does not track the
#     .gcda files): the optimised folder is cleaned before its build.
# Any change to the copies' list or the post-codegen steps changes generated files, and a function changed since the
# session keeps no profile: run the cycle again after such a change.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\win\pgo_cycle.ps1 -Step generate
#       the instrumented NRO in out\nx-pgo-gen (incremental). Copy it to the card and play ONE normal race (the user's
#       rule: a normal run, not more than 5 minutes); the session writes pgo/sasrt_pgo_<N>.stream next to the NRO.
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\win\pgo_cycle.ps1 -Step use -Streams <folder>
#       <folder> holds that session's stream only (fetched from the card). pgo/ is moved to pgo_<date-time>/, the stream
#       merged into a new pgo/, out\nx cleaned and built with -Pgo use -Final (about an hour).
param(
    [Parameter(Mandatory = $true)][ValidateSet('generate', 'use')][string]$Step,
    [string]$Streams = '',
    # sasrt-nx (2026-11-11): the in-place copies' cycle (build_switch.ps1 -InPlace: out\nx-inplace-gen, out\nx-inplace,
    # the profile in pgo-inplace/)
    [switch]$InPlace,
    # sasrt-nx (2026-11-13, Blur's CG-13 A/B): the in-place cycle with BLUR_FPCR_ONE_MODE ON (out\nx-onemode-gen,
    # out\nx-onemode, the profile in pgo-onemode/). Implies -InPlace.
    [switch]$OneMode
)
if ($OneMode) { $InPlace = $true }
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $PSScriptRoot 'env.ps1')  # CMake and Ninja on PATH (the clean step below)
$build = Join-Path $PSScriptRoot 'build_switch.ps1'
if ($Step -eq 'generate') {
    if ($OneMode) { & $build -Pgo generate -Build out\nx-onemode-gen -InPlace -OneMode } elseif ($InPlace) { & $build -Pgo generate -Build out\nx-inplace-gen -InPlace } else { & $build -Pgo generate -Build out\nx-pgo-gen }
    exit $LASTEXITCODE
}
if (-not $Streams -or -not (Test-Path $Streams)) {
    Write-Error 'pgo_cycle: -Streams <folder with the session stream> is required for -Step use'
    exit 1
}
$pgo = Join-Path $root $(if ($OneMode) { 'pgo-onemode' } elseif ($InPlace) { 'pgo-inplace' } else { 'pgo' })
# (The batch's audit, finding 10: the streams must not be in the profile folder, which is moved aside below.)
if ((Resolve-Path $Streams).Path.StartsWith($pgo, [System.StringComparison]::OrdinalIgnoreCase)) {
    Write-Error 'pgo_cycle: -Streams must not be the pgo folder or inside it (it is moved aside): copy the stream elsewhere'
    exit 1
}
if ((Test-Path $pgo) -and (Get-ChildItem $pgo -Filter *.gcda -ErrorAction SilentlyContinue)) {
    $aside = Join-Path $root ('pgo_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
    Move-Item $pgo $aside
    Write-Output "pgo_cycle: the previous profile moved to $aside"
}
New-Item -ItemType Directory -Force $pgo | Out-Null
# sasrt-nx (2026-11-13): one stream, not older than the instrumented NRO (pgo_merge.py; cycle B's stale stream)
$genNro = Join-Path $root $(if ($OneMode) { 'out\nx-onemode-gen\sasrt.nro' } elseif ($InPlace) { 'out\nx-inplace-gen\sasrt.nro' } else { 'out\nx-pgo-gen\sasrt.nro' })
& python (Join-Path $root 'tools\pgo_merge.py') $Streams $pgo --gen-build $genNro
if ($LASTEXITCODE) { exit $LASTEXITCODE }
$folder = Join-Path $root $(if ($OneMode) { 'out\nx-onemode' } elseif ($InPlace) { 'out\nx-inplace' } else { 'out\nx' })
if (Test-Path (Join-Path $folder 'build.ninja')) {
    & cmake --build $folder --target clean
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
}
if ($OneMode) { & $build -Pgo use -Final -Build out\nx-onemode -InPlace -OneMode } elseif ($InPlace) { & $build -Pgo use -Final -Build out\nx-inplace -InPlace } else { & $build -Pgo use -Final -Build out\nx }
exit $LASTEXITCODE
