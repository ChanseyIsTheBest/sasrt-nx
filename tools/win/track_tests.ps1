# Renderer tests on many tracks: Career > Single Race > cup > track > difficulty > character > race against the AI,
# holding the accelerator. Needs a save with the tracks unlocked (the 100% save: -UserData points at a user data
# root that holds it).
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\win\track_tests.ps1 -Mode harvest [-Tracks 0.0,0.1,...]
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\win\track_tests.ps1 -Mode test -Tracks 0.3,1.0 [-Renderers native,emu]
#
# A track is <cup>.<track>: cup 0-4 is the top row of the cup grid (Dragon Cup first), track 0-3 the 2x2 panel
# (0 top left, 1 top right, 2 bottom left, 3 bottom right).
#
# harvest: native renderer, no capture, until the track is loaded and the race has started, with the shader dumps on
#   (sasrt_dump_shaders + sasrt_dump_shaders_scan_s: every shader object the loaded track holds is written to
#   out\pc\shaders; MASSEFFECT_SHADER_DISCOVERY: the raw microcode of what the package could not identify goes to
#   out\pc\shaders_discovery_tracks). Then rebuild the package (docs/sasrt-notes.md, "Shader package").
# test: a 1280x720 capture of about 60 s of racing with each renderer, in out\pc\captures\tracks\ as
#   t<cup><track>_<renderer>.rgba (+ .txt and a contact sheet .png); summary.txt collects each run's log figures.
param(
    [ValidateSet('harvest', 'test')][string]$Mode = 'test',
    [string[]]$Tracks = @('0.0', '0.1', '0.2', '0.3', '1.0', '1.1', '1.2', '1.3', '2.0', '2.1', '2.2', '2.3',
                          '3.0', '3.1', '3.2', '3.3', '4.0', '4.1', '4.2', '4.3'),
    [string[]]$Renderers = @('native', 'emu'),
    [string]$UserData = 'out\pc\user_100',
    [int]$Frames = 150,
    [int]$Every = 12
)
# Through "powershell -File" a list arrives as one string ("0.0,0.3"): split it here.
$Tracks = @($Tracks | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
$Renderers = @($Renderers | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$cap = Join-Path $root 'out\pc\captures'
$dest = Join-Path $cap 'tracks'
New-Item -ItemType Directory -Force $dest | Out-Null
$summary = Join-Path $dest "summary_$Mode.txt"
$sheet = Join-Path $root 'tools\capture_sheet.py'
$env:REX_USER_DATA_ROOT = (Resolve-Path (Join-Path $root $UserData)).Path
$env:REX_SASRT_VIDEO_HALF = 'false'
if ($Mode -eq 'harvest') {
    $Renderers = @('native')
    $env:REX_SASRT_DUMP_SHADERS = 'true'
    $env:REX_SASRT_DUMP_SHADERS_SCAN_S = '10'
    $env:MASSEFFECT_SHADER_DISCOVERY = Join-Path $root 'out\pc\shaders_discovery_tracks'
}
foreach ($t in $Tracks) {
    $cup, $track = $t.Split('.') | ForEach-Object { [int]$_ }
    # Boot to Career > Single Race (as in race.txt, then three to the right), the cup (RIGHT x cup), the track,
    # difficulty, character, mod; A on the bonus chance and once more (skips the intro); then the accelerator.
    $steps = @('55=A', '62=START', '66=A', '70=A', '73=RIGHT', '75=RIGHT', '77=RIGHT', '79=A')
    for ($k = 0; $k -lt $cup; ++$k) { $steps += ('{0:0.0}=RIGHT' -f (81.0 + 0.6 * $k)) }
    $steps += '83.5=A'
    if ($track -eq 1 -or $track -eq 3) { $steps += '85.5=RIGHT' }
    if ($track -ge 2) { $steps += '86.3=DOWN' }
    $steps += @('87.5=A', '91.5=A', '95.5=A', '99.5=A', '103.5=A', '107=A', '110+300=RT')
    $script = $steps -join '; '
    foreach ($r in $Renderers) {
        if ($r -eq 'native') { $env:REX_MASSEFFECT_RENDERER_NATIVE = 'true' } else { $env:REX_MASSEFFECT_RENDERER_NATIVE = $null }
        $name = "t$cup${track}_$r"
        $start = Get-Date
        $before = (Get-ChildItem (Join-Path $root 'out\pc\shaders') -ErrorAction SilentlyContinue).Count
        if ($Mode -eq 'harvest') {
            $out = & (Join-Path $root 'tools\win\boot_test.ps1') -InputScript $script -Seconds 135 -Tail 0 2>&1 | Out-String -Width 300
        } else {
            # The native renderer holds 30 frames a second, the emulated GPU 20-25 (the run lasts until the capture
            # is surely complete).
            $fps = if ($r -eq 'native') { 28 } else { 20 }
            $out = & (Join-Path $root 'tools\win\boot_test.ps1') -InputScript $script -Seconds 60 -VideoAt 108 -VideoFrames $Frames -VideoEvery $Every -VideoFps $fps -Tail 0 2>&1 | Out-String -Width 300
        }
        $log = Get-ChildItem (Join-Path $root 'out\pc\logs\*.log') | Where-Object { $_.LastWriteTime -ge $start } |
            Sort-Object LastWriteTime | Select-Object -Last 1
        $raw = Join-Path $cap 'video_108s.rgba'
        if ($Mode -eq 'test' -and (Test-Path $raw)) {
            Move-Item -Force $raw (Join-Path $dest "$name.rgba")
            Move-Item -Force (Join-Path $cap 'video_108s.txt') (Join-Path $dest "$name.txt")
            Remove-Item -Force (Join-Path $cap 'video_108s.mp4'), (Join-Path $cap 'video_108s.sheet.png') -ErrorAction SilentlyContinue
            python $sheet (Join-Path $dest "$name.rgba") (Join-Path $dest "$name.png") 10 6 320 | Out-Null
        }
        $lines = @("== $name ($script)", ($out -split "`n" | Select-Object -First 1))
        if ($log) {
            $lines += "log: $($log.Name)"
            $swaps = Select-String -Path $log.FullName -Pattern '([0-9]+) Swaps' -AllMatches |
                ForEach-Object { $_.Matches[0].Groups[1].Value }
            $lines += "swaps per report: $($swaps -join ' ')"
            $ur = Select-String -Path $log.FullName -Pattern '/ ([0-9]+) not; native: [0-9]+ drawn, ([0-9]+) rejected' -AllMatches |
                ForEach-Object { $_.Matches[0].Groups[1].Value + '/' + $_.Matches[0].Groups[2].Value }
            if ($ur) { $lines += "unidentified/rejected: $($ur -join ' ')" }
            $scan = Select-String -Path $log.FullName -Pattern '\[shaders\] scan: ([0-9]+) shader objects in memory, ([0-9]+) new' -AllMatches |
                ForEach-Object { $_.Matches[0].Groups[1].Value + '+' + $_.Matches[0].Groups[2].Value }
            if ($scan) { $lines += "scan (objects+new): $($scan -join ' ')" }
            $lines += 'errors: ' + (Select-String -Path $log.FullName -Pattern '\[error\]|\[critical\]' -CaseSensitive).Count +
                ', shader files: ' + $before + ' -> ' + (Get-ChildItem (Join-Path $root 'out\pc\shaders')).Count
        }
        $lines | Add-Content -Path $summary -Encoding utf8
    }
}
$env:REX_MASSEFFECT_RENDERER_NATIVE = $null
$env:REX_SASRT_DUMP_SHADERS = $null
$env:REX_SASRT_DUMP_SHADERS_SCAN_S = $null
$env:MASSEFFECT_SHADER_DISCOVERY = $null
'done' | Add-Content -Path $summary -Encoding utf8
