# Builds the Switch NRO and lays out the SD card folder. One NRO, the optimised codegen: the user's rule of 2026-10-06
# (no classic / optimised A/B pair any more; build-time changes go into this build, and features are compared through
# sasrt.toml keys and the premade configs). Steps, each logged to out\switch_build.log (the last line is "done <time>"
# or the step that failed):
#   1. codegen (tools\codegen.ps1), only when app\generated is not the optimised flavour or -Codegen asks for it; the
#      PC tree then needs a rebuild too (cmake --build out\pc): the generator rewrote its sources;
#   2. the NRO: out\nx\sasrt.nro + sasrt.map (build_switch_logged.ps1, its output in out\nx_build.log);
#   3. tools\check_switch_build.py: the build names the optimised codegen, no branch-to-self in a recompiled function
#      other than the game's own halts (a guest poll GCC hoisted out of its loop hangs the console), and the NVK SDK's
#      Vulkan driver;
#   4. the SD folder (package_switch.ps1 -IncludeGame), only when the checks pass.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\win\build_switch_package.ps1 [-Jobs 8] [-Codegen] [-Final]
# -Final: with LTO (SASRT_SWITCH_LTO; the user's rule of 2026-10-19: final builds only, test builds without)
param([int]$Jobs = 8, [switch]$Codegen, [switch]$Final)
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$log = Join-Path $root 'out\switch_build.log'
function Log([string]$line) { $line | Out-File -Append -Encoding utf8 $log }
"started $(Get-Date -Format s)" | Out-File -Encoding utf8 $log
$flavorFile = Join-Path $root 'app\generated\codegen_flavor.txt'
$flavor = if (Test-Path $flavorFile) { (Get-Content -Raw $flavorFile).Trim() } else { 'none' }
if ($Codegen -or $flavor -ne 'optimised codegen') {
    Log "== codegen (app\generated was: $flavor) $(Get-Date -Format s)"
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'tools\codegen.ps1') -Flavor optimised 2>&1 |
        Select-Object -Last 5 | ForEach-Object { Log "$_" }
    if ($LASTEXITCODE -ne 0) { Log 'codegen failed (out\codegen.log)'; exit 1 }
}
Log "== switch build $(Get-Date -Format s)"
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'build_switch_logged.ps1') 'out\nx_build.log' -Jobs $Jobs @(if ($Final) { '-Final' }) 2>&1 |
    ForEach-Object { Log "$_" }
if (-not ((Get-Content (Join-Path $root 'out\nx_build.log.done')) -match 'exit=0')) {
    Log 'switch build failed (out\nx_build.log)'
    exit 1
}
Log "== checks $(Get-Date -Format s)"
python (Join-Path $root 'tools\check_switch_build.py') (Join-Path $root 'out\nx\sasrt') 2>&1 | ForEach-Object { Log "$_" }
if ($LASTEXITCODE -ne 0) { Log 'checks failed: the SD folder was left as it was'; exit 1 }
Log "== package $(Get-Date -Format s)"
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'package_switch.ps1') -IncludeGame 2>&1 |
    Select-Object -Last 12 | ForEach-Object { Log "$_" }
if ($LASTEXITCODE -ne 0) { Log 'package failed'; exit 1 }
Log "done $(Get-Date -Format s)"
