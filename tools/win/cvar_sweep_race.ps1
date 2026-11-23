# Runs the native renderer into the first race once per cvar override and scores one recorded stretch of it, to find
# which renderer switch causes a race-only defect. The score is the share of recorded frames whose lower middle is
# mostly the sea's cyan: the frames where the restored depth was lost and the water plane covers the scene (a correct
# race frame shows the track there).
#
#   powershell -File tools\win\cvar_sweep_race.ps1 -Cvars "masseffect_native_skip_invisibles=false,..."
# (one comma-separated string: powershell -File would split a list into separate arguments)
param(
    [int]$At = 128,
    [int]$Frames = 60,
    [int]$Every = 5,
    [string]$InputScript = 'tools\win\input\race.txt',
    [string]$Cvars = '',  # empty: the baseline run only
    [string]$Baseline = 'baseline',
    [switch]$NoBaseline
)
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $root
$runs = @()
if (-not $NoBaseline) { $runs += $Baseline }
$runs += ($Cvars -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
$classify = @'
import sys, numpy as np
raw = sys.argv[1]
w, h, fps, count = open(raw[:-5] + '.txt').read().split()
w, h, count = int(w), int(h), int(count)
f = np.fromfile(raw, np.uint8).reshape(-1, h, w, 4)[:count, :, :, :3].astype(np.int32)
b = f[:, h * 2 // 3:, w // 4: w * 3 // 4]
sea = ((b[..., 1] > b[..., 0] + 40) & (b[..., 2] > b[..., 0] + 40)).mean(axis=(1, 2))
tags = ''.join('S' if s > 0.6 else '.' for s in sea)
print(f'sea frames {int((sea > 0.6).sum())}/{count}  {tags}')
'@
$classifyPath = Join-Path $root 'out\classify_race.py'
Set-Content -Path $classifyPath -Value $classify -Encoding ascii
foreach ($run in $runs) {
    $env:REX_MASSEFFECT_RENDERER_NATIVE = 'true'
    $names = @()
    if ($run -ne $Baseline) {
        # One run may set several cvars: name=value;name=value
        foreach ($item in ($run -split ';')) {
            $name, $value = $item.Split('=', 2)
            Set-Item -Path "env:REX_$($name.ToUpper())" -Value $value
            $names += $name
        }
    }
    powershell -NoProfile -ExecutionPolicy Bypass -File tools\win\boot_test.ps1 -InputScript $InputScript -VideoAt $At -VideoFrames $Frames -VideoEvery $Every -Tail 0 | Out-Null
    foreach ($name in $names) { Remove-Item -Path "env:REX_$($name.ToUpper())" -ErrorAction SilentlyContinue }
    $env:REX_MASSEFFECT_RENDERER_NATIVE = $null
    $raw = Join-Path $root "out\pc\captures\video_${At}s.rgba"
    $stats = & python $classifyPath $raw
    '{0,-60} {1}' -f $run, $stats
}
