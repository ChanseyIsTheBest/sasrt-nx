# Builds the Switch A/B pair: the optimised codegen flavour first (out\nx\ab\sasrt_optimised.nro + .map), then the
# classic one (out\nx\ab\sasrt.nro + .map), leaving app\generated classic like the PC tree; then lays out the SD card
# folder (package_switch.ps1 -IncludeGame). Each step's output goes to out\switch_ab.log; the last line is "done" or
# the step that failed. The PC tree needs a rebuild afterwards (cmake --build out\pc): the generator rewrote its
# sources.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\win\build_switch_ab.ps1 [-Jobs 8]
#
# SUPERSEDED 2026-10-06: the SD card gets one NRO now, the optimised codegen (the user's rule; no classic / optimised A/B
# pair). Use tools\win\build_switch_package.ps1. This script stops at once (it would leave app\generated classic, and
# package_switch.ps1 refuses a classic NRO); kept only until it is deleted by hand.
param([int]$Jobs = 8)
Write-Error 'build_switch_ab.ps1 is superseded: use tools\win\build_switch_package.ps1 (one NRO, optimised codegen)'
exit 1
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$log = Join-Path $root 'out\switch_ab.log'
"started $(Get-Date -Format s)" | Out-File -Encoding utf8 $log
$nx = Join-Path $root 'out\nx'
New-Item -ItemType Directory -Force (Join-Path $nx 'ab') | Out-Null
foreach ($flavor in @('optimised', 'classic')) {
    "== codegen $flavor $(Get-Date -Format s)" | Out-File -Append -Encoding utf8 $log
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'tools\codegen.ps1') -Flavor $flavor 2>&1 |
        Select-Object -Last 5 | Out-File -Append -Encoding utf8 $log
    if ($LASTEXITCODE -ne 0) { "codegen $flavor failed" | Out-File -Append -Encoding utf8 $log; exit 1 }
    "== switch build $flavor $(Get-Date -Format s)" | Out-File -Append -Encoding utf8 $log
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'build_switch_logged.ps1') "out\nx_build_$flavor.log" -Jobs $Jobs 2>&1 |
        Out-File -Append -Encoding utf8 $log
    if (-not ((Get-Content (Join-Path $root "out\nx_build_$flavor.log.done")) -match 'exit=0')) {
        "switch build $flavor failed (out\nx_build_$flavor.log)" | Out-File -Append -Encoding utf8 $log
        exit 1
    }
    # Branch-to-self instructions (tools/find_self_loops.py): guest polls GCC hoisted out of their loop hang the console;
    # the classic build has 4 in recompiled functions (genuine guest halts), the optimised one must not have more.
    python (Join-Path $root 'tools\find_self_loops.py') (Join-Path $nx 'sasrt') 2>&1 | Select-Object -First 1 |
        ForEach-Object { "self loops ($flavor): $_" } | Out-File -Append -Encoding utf8 $log
    # Which Mesa the NRO carries: the NVK SDK's (nfsmw, 26.2.2) and not the generic portlibs driver (26.2.1).
    python -c "import re,sys; m=re.search(rb'Mesa 26[0-9.]+ \(git-[0-9a-f]+\)', open(sys.argv[1],'rb').read()); print('driver: '+(m.group(0).decode() if m else 'no Mesa string'))" (Join-Path $nx 'sasrt') |
        ForEach-Object { "$_ ($flavor)" } | Out-File -Append -Encoding utf8 $log
    $name = if ($flavor -eq 'classic') { 'sasrt' } else { 'sasrt_optimised' }
    Copy-Item -Force (Join-Path $nx 'sasrt.nro') (Join-Path $nx "ab\$name.nro")
    Copy-Item -Force (Join-Path $nx 'sasrt.map') (Join-Path $nx "ab\$name.map")
    "kept ab\$name.nro ($((Get-Item (Join-Path $nx "ab\$name.nro")).Length) bytes)" | Out-File -Append -Encoding utf8 $log
}
"== package $(Get-Date -Format s)" | Out-File -Append -Encoding utf8 $log
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'package_switch.ps1') -IncludeGame 2>&1 |
    Select-Object -Last 8 | Out-File -Append -Encoding utf8 $log
"done $(Get-Date -Format s)" | Out-File -Append -Encoding utf8 $log
