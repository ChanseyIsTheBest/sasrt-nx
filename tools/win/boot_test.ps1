# Starts the PC build for a few seconds, stops it, and prints the end of its newest log plus what it reached.
# With -VideoAt N it also records a video from N seconds on (sasrt_video_s) and makes the MP4 (tools/make_video.sh).
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\win\boot_test.ps1 [-Seconds 45] [-Exe out\pc\sasrt.exe]
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\win\boot_test.ps1 -VideoAt 10 -VideoFrames 600
# -VideoEvery N keeps one game frame in N (sasrt_video_every): minutes of footage at a few hundred MB.
# -InputScript <file or script> feeds scripted controller presses (sasrt_input_script; tools\win\input\race.txt goes
# from the boot through Career > World Tour into the first race and holds the accelerator). -Trace logs the game's
# Direct3D calls every 5 s (sasrt_d3d_trace: the frame rate is the D3DDevice_Swap count / 5).
# -SwitchConfig runs with the console's settings: every key of app\sasrt_switch.toml as REX_<KEY> (the environment beats
# the PC's sasrt.toml; the asset-pack and log keys stay the PC's). -Set 'key=value;key=value' adds or overrides keys.
param(
    [int]$Seconds = 45,
    [string]$InputScript = '',
    [switch]$Trace,
    [string]$Exe = 'out\pc\sasrt.exe',
    [int]$Tail = 40,
    [int]$VideoAt = 0,
    [int]$VideoFrames = 300,
    [int]$VideoEvery = 1,
    [int]$VideoFps = 20,
    [switch]$SwitchConfig,
    [string]$Set = '',
    [switch]$NoMp4,
    # -RenderDoc: under RenderDoc (banjo-nx's portable 1.46), captures in out\rdc (sasrt_renderdoc_capture_s picks the frame).
    [switch]$RenderDoc
)
$overrides = [ordered]@{}
if ($SwitchConfig) {
    $toml = Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path 'app\sasrt_switch.toml'
    foreach ($line in Get-Content $toml) {
        if ($line -match '^\s*([a-z0-9_]+)\s*=\s*("?)([^"#]*?)\2\s*(#.*)?$') {
            # renut_gpu_backend: the console's is deko3d, which the PC has not (the PC keeps its own, D3D12).
            if (@('asset_pack', 'asset_pack_build', 'sasrt_shader_misses', 'log_level', 'renut_gpu_backend') -notcontains $Matches[1]) {
                $overrides[$Matches[1]] = $Matches[3]
            }
        }
    }
}
foreach ($pair in ($Set -split ';')) {
    if ($pair -match '^\s*([a-z0-9_]+)\s*=\s*(.*?)\s*$') { $overrides[$Matches[1]] = $Matches[2] }
}
foreach ($k in $overrides.Keys) { Set-Item -Path ("env:REX_" + $k.ToUpper()) -Value $overrides[$k] }
if ($InputScript) {
    $script = if (Test-Path $InputScript) { (Get-Content $InputScript -Raw).Trim() } else { $InputScript }
    $env:REX_SASRT_INPUT_SCRIPT = $script
}
if ($Trace) { $env:REX_SASRT_D3D_TRACE = 'true' }
if ($VideoAt -gt 0) {
    $env:REX_SASRT_VIDEO_S = "$VideoAt"
    $env:REX_SASRT_VIDEO_FRAMES = "$VideoFrames"
    $env:REX_SASRT_VIDEO_EVERY = "$VideoEvery"
    # Room for the recording and for writing it out before the run is stopped. The game presents 30 frames a second
    # at most and about 25 with the emulated GPU: count 20 (-VideoFps; 28 is safe for the native renderer).
    $Seconds = [math]::Max($Seconds, $VideoAt + [int][math]::Ceiling($VideoFrames * $VideoEvery / [double]$VideoFps) + 15)
}
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$exePath = (Resolve-Path (Join-Path $root $Exe)).Path
$dir = Split-Path $exePath
# Recordings in captures\ are kept: a video at a second already recorded would overwrite them, so the run refuses.
if ($VideoAt -gt 0) {
    $taken = Get-ChildItem (Join-Path $dir 'captures') -Filter "video_${VideoAt}s.*" -ErrorAction SilentlyContinue
    if ($taken) {
        "refused: captures\video_${VideoAt}s.* exists ($($taken.Name -join ', ')); pick another -VideoAt"
        exit 1
    }
}
# A test instance left over from an interrupted run keeps the exe locked (the next link fails with "permission
# denied") and competes for the GPU: stop instances of this very executable only (other trees are left alone).
Get-CimInstance Win32_Process -Filter "Name='$(Split-Path $exePath -Leaf)'" -ErrorAction SilentlyContinue |
    Where-Object { $_.ExecutablePath -eq $exePath } | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        Wait-Process -Id $_.ProcessId -Timeout 20 -ErrorAction SilentlyContinue
    }
$started = Get-Date
# Test runs are always muted and minimized (environment beats sasrt.toml), so they never take over the desktop.
$env:REX_AUDIO_MUTE = 'true'
$env:REX_WINDOW_START_MINIMIZED = 'true'
if ($RenderDoc) {
    $rdc = 'D:\Banjo kazooie port\tools\RenderDoc_1.46_64\renderdoccmd.exe'
    New-Item -ItemType Directory -Force (Join-Path $root 'out\rdc') | Out-Null
    # sasrt-nx (2026-10-20): RenderDoc's Vulkan layer from its portable folder, for this process only (no system
    # registration; without it Vulkan captures ended "failed"), as tools\win\ryujinx_run.ps1 captures Ryujinx.
    $env:VK_ADD_LAYER_PATH = Split-Path $rdc
    $env:VK_INSTANCE_LAYERS = 'VK_LAYER_RENDERDOC_Capture'
    $env:ENABLE_VULKAN_RENDERDOC_CAPTURE = '1'
    $p = Start-Process -FilePath $rdc -WorkingDirectory $dir -PassThru -WindowStyle Minimized -ArgumentList @(
        'capture', '-c', ('"' + (Join-Path $root 'out\rdc\sasrt') + '"'), '-w', '-d', ('"' + $dir + '"'), ('"' + $exePath + '"'))
} else {
    $p = Start-Process -FilePath $exePath -WorkingDirectory $dir -PassThru -WindowStyle Minimized
}
$p.WaitForExit($Seconds * 1000) | Out-Null
if ($p.HasExited) {
    '{0} exited after {1:n1} s with code 0x{2:X8}' -f (Split-Path $exePath -Leaf), ((Get-Date) - $started).TotalSeconds, $p.ExitCode
} else {
    $p.Refresh()
    $status = 'still running after {0} s: cpu {1:n1} s, working set {2} MB; stopped' -f $Seconds, $p.TotalProcessorTime.TotalSeconds, [math]::Round($p.WorkingSet64 / 1MB)
    # Stop it BEFORE printing anything: a caller that pipes this script into Select-Object -First N closes the pipe
    # after its first line, which ends this script there and would leave the game running.
    # Under RenderDoc the game is renderdoccmd's child: stopped by its path first.
    Get-CimInstance Win32_Process -Filter "Name='$(Split-Path $exePath -Leaf)'" -ErrorAction SilentlyContinue |
        Where-Object { $_.ExecutablePath -eq $exePath } | ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            Wait-Process -Id $_.ProcessId -Timeout 20 -ErrorAction SilentlyContinue
        }
    Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    # Wait until it is really gone: a process still tearing down keeps sasrt.exe locked and the next link fails.
    if (-not $p.WaitForExit(20000)) { $status += " (warning: process $($p.Id) did not exit within 20 s)" }
    $status
}
$log = Get-ChildItem (Join-Path $dir 'logs') -Filter *.log -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -ge $started.AddSeconds(-2) } | Sort-Object LastWriteTime | Select-Object -Last 1
if ($log) {
    "== $($log.FullName) ($($log.Length) bytes)"
    Get-Content $log.FullName -Tail $Tail
} else {
    'no log written'
}
Remove-Item env:REX_SASRT_INPUT_SCRIPT, env:REX_SASRT_D3D_TRACE -ErrorAction SilentlyContinue
foreach ($k in $overrides.Keys) { Set-Item -Path ("env:REX_" + $k.ToUpper()) -Value '' }
if ($VideoAt -gt 0) {
    Remove-Item env:REX_SASRT_VIDEO_S, env:REX_SASRT_VIDEO_FRAMES, env:REX_SASRT_VIDEO_EVERY -ErrorAction SilentlyContinue
    $raw = Join-Path $dir "captures\video_${VideoAt}s.rgba"
    if ($NoMp4) {
        "raw capture kept: $raw"
    } elseif ((Test-Path $raw) -and (Get-Item $raw).LastWriteTime -ge $started) {
        $bash = 'C:\devkitPro\msys2\usr\bin\bash.exe'
        if (-not (Test-Path $bash)) { $bash = 'bash' }
        & $bash (Join-Path $root 'tools/make_video.sh').Replace('\', '/') $raw.Replace('\', '/')
    } else {
        "no video written to $raw (see the log for [capture] lines)"
    }
}
