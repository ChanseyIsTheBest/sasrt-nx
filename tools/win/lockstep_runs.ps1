# Lockstep captures (sa2-nx's method) of the same scripted race under different settings, then the pixel comparison
# of each against the first (tools/lockstep_compare.py: every frame of one run looked up among all frames of the other).
# vblank_per_swap = true with vblank_per_swap_count = 2 (this game presents every second vblank): every run gives the
# game two vblanks per frame, whatever the PC's speed. The menus are driven by the clock as usual; the accelerator is
# held from the loading screen on, so every run starts the race with the same input.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\win\lockstep_runs.ps1
#       -Runs 'base:sasrt_cpu_enhancements=false|base2:sasrt_cpu_enhancements=false|on:' [-Track 0.0] [-VideoAt 150]
#       [-Frames 1200] [-Full]
# Each run is <label>:<key=value;key=value> on top of app\sasrt_switch.toml (boot_test.ps1 -SwitchConfig). Captures go
# to out\pc\captures\lockstep_<label>.rgba (+ .txt, .frames); delete them when done (about 1.1 GB each at half size).
param(
    [Parameter(Mandatory = $true)][string]$Runs,
    [string]$Track = '0.0',
    [int]$VideoAt = 150,
    [int]$Frames = 1200,
    [switch]$Full,
    [string]$InputScript = '',
    [string]$UserData = 'out\pc\user_100'
)
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$env:REX_USER_DATA_ROOT = (Resolve-Path (Join-Path $root $UserData)).Path
$cup, $slot = $Track.Split('.') | ForEach-Object { [int]$_ }
$steps = @('55=A', '62=START', '66=A', '70=A', '73=RIGHT', '75=RIGHT', '77=RIGHT', '79=A')
for ($k = 0; $k -lt $cup; ++$k) { $steps += ('{0:0.0}=RIGHT' -f (81.0 + 0.6 * $k)) }
$steps += '83.5=A'
if ($slot -eq 1 -or $slot -eq 3) { $steps += '85.5=RIGHT' }
if ($slot -ge 2) { $steps += '86.3=DOWN' }
$steps += @('87.5=A', '91.5=A', '95.5=A', '99.5=A', '103.5=A', '107=A', '108+400=RT')
# -InputScript replaces the clock-driven menus (frame-timed presses, "f1365+5f=A; ...": the same input on the same game
# frames in every run).
if ($InputScript) { $steps = @($InputScript) }
$captures = Join-Path $root 'out\pc\captures'
$labels = @()
foreach ($run in ($Runs -split '\|')) {
    $label, $settings = $run.Split(':', 2)
    $set = "vblank_per_swap=true;vblank_per_swap_count=2;sasrt_video_half=$(if ($Full) { 'false' } else { 'true' })"
    if ($settings) { $set += ";$settings" }
    "== $label ($settings)"
    & (Join-Path $PSScriptRoot 'boot_test.ps1') -SwitchConfig -Set $set -InputScript ($steps -join '; ') -VideoAt $VideoAt `
        -VideoFrames $Frames -VideoFps 25 -NoMp4 -Tail 0 2>&1 | Out-String -Width 300 | Select-Object -First 1
    foreach ($ext in 'rgba', 'txt', 'frames') {
        $from = Join-Path $captures "video_${VideoAt}s.$ext"
        if (Test-Path $from) { Move-Item -Force $from (Join-Path $captures "lockstep_$label.$ext") }
    }
    $L = Get-ChildItem (Join-Path $root 'out\pc\logs\sasrt_*.log') | Sort-Object LastWriteTime | Select-Object -Last 1
    "log $($L.Name): " + ((Select-String -Path $L.FullName -Pattern '\[capture\] video' | Select-Object -Last 1).Line -replace '.*\[capture\] ', '')
    $labels += $label
}
foreach ($label in $labels | Select-Object -Skip 1) {
    "== $($labels[0]) vs $label"
    python (Join-Path $root 'tools\lockstep_compare.py') (Join-Path $captures "lockstep_$($labels[0]).rgba") `
        (Join-Path $captures "lockstep_$label.rgba") --out (Join-Path $captures "lockstep_$($labels[0])_vs_$label.png")
}
