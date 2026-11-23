# Runs the Switch NRO in banjo-nx's patched Ryujinx (github ChanseyIsTheBest/ryujinx) with this port's own data folder
# (D:\New folder\ryu-data\sasrt: config, keys, firmware, SD card, logs; several ports' instances may run at once), for
# a number of seconds, then stops this run's process only (by its id, never by name: the other ports' runs go on).
# The NRO and a toml (app\sasrt_switch.toml plus -Set keys) go to the SD folder first; the game files there are a
# junction to assets\game_root (never a copy). Starts minimised and muted (the fork's default).
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\win\ryujinx_run.ps1 -Name first -Seconds 240 `
#       -Set 'sasrt_renderer=renut;renut_gpu_backend=deko3d' [-InputScript tools\win\input\race_ryujinx.txt]
# Afterwards: the SD folder's newest log is copied to out\ryujinx\<Name>.log, Ryujinx's own to out\ryujinx\<Name>_ryu.log.
param(
    [string]$Name = 'run',
    [int]$Seconds = 240,
    [string]$Set = '',
    [string]$Nro = '',
    [string]$InputScript = '',
    # sasrt-nx (2026-11-20, split-screen runs): players 2-4's scripts (sasrt_input_script_p2..p4), files or scripts.
    [string]$InputScriptP2 = '',
    [string]$InputScriptP3 = '',
    [string]$InputScriptP4 = '',
    # -RenderDoc: Ryujinx under RenderDoc (banjo-nx's portable 1.46; its Vulkan back end is captured), captures in
    # out\rdc\ryu_*; tools\rdc_trigger.py (inside qrenderdoc) takes them by target control at set times.
    [switch]$RenderDoc,
    # -Visible (sasrt-nx, 2026-10-20; the user's permission per run): a normal window (RYUBING_INTERACTIVE=1, which
    # also unmutes the fork: pass audio_mute=true in -Set). RenderDoc captures Ryujinx only while it presents.
    [switch]$Visible
)
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$data = 'D:\New folder\ryu-data\sasrt'
$sd = Join-Path $data 'sdcard\switch\sasrt-nx'
$exe = 'D:\New folder\Ryubing-src\ryubing\build\Ryujinx.exe'
$out = Join-Path $root 'out\ryujinx'
New-Item -ItemType Directory -Force $sd, $out | Out-Null
if (-not $Nro) { $Nro = Join-Path $root 'out\nx\sasrt.nro' }
Copy-Item -Force $Nro (Join-Path $sd 'sasrt.nro')
# The deko3d DKSH cache built with the NRO's shaders (tools/deko3d_variant_cache.py), when newer than the SD's copy (which
# the game appends its own compiles to): an older one holds shaders built for another layout of the shared constants
# and descriptor words (2026-10-20: all-black frames in runs deko31/32 until it was copied).
$dksh = Join-Path $root 'out\deko3d_shaders\deko3d_shaders.bin'
$sdDksh = Join-Path $sd 'deko3d_shaders.bin'
if ((Test-Path $dksh) -and (-not (Test-Path $sdDksh) -or (Get-Item $dksh).LastWriteTime -gt (Get-Item $sdDksh).LastWriteTime -or
        (Get-Item $Nro).LastWriteTime -gt (Get-Item $sdDksh).LastWriteTime)) {
    Copy-Item -Force $dksh $sdDksh
}
if (-not (Test-Path (Join-Path $sd 'game_root'))) {
    New-Item -ItemType Junction -Path (Join-Path $sd 'game_root') -Target (Join-Path $root 'assets\game_root') | Out-Null
}
# The toml: the console's settings plus the run's keys.
$toml = Get-Content -Raw (Join-Path $root 'app\sasrt_switch.toml')
foreach ($pair in ($Set -split ';')) {
    if ($pair -match '^\s*([a-z0-9_]+)\s*=\s*(.*?)\s*$') {
        $k = $Matches[1]; $v = $Matches[2]
        if ($v -notmatch '^(true|false|-?[0-9.]+|".*")$') { $v = '"' + $v + '"' }
        $line = "$k = $v"
        if ($toml -match "(?m)^$k\s*=.*$") { $toml = $toml -replace "(?m)^$k\s*=.*$", $line }
        else { $toml = $toml.TrimEnd() + "`n" + $line + "`n" }
    }
}
# -InputScript <file or script>: sasrt_input_script (its presses are separated by ';', which -Set splits on).
if ($InputScript) {
    $script = if (Test-Path $InputScript) { (Get-Content $InputScript -Raw).Trim() } else { $InputScript }
    $toml = ($toml -replace '(?m)^sasrt_input_script\s*=.*$', '').TrimEnd() + "`nsasrt_input_script = `"$script`"`n"
}
foreach ($pp in @(@('sasrt_input_script_p2', $InputScriptP2), @('sasrt_input_script_p3', $InputScriptP3),
                  @('sasrt_input_script_p4', $InputScriptP4))) {
    if ($pp[1]) {
        $script = if (Test-Path $pp[1]) { (Get-Content $pp[1] -Raw).Trim() } else { $pp[1] }
        $toml = ($toml -replace ('(?m)^' + $pp[0] + '\s*=.*$'), '').TrimEnd() + "`n" + $pp[0] + " = `"$script`"`n"
    }
}
[System.IO.File]::WriteAllText((Join-Path $sd 'sasrt.toml'), $toml)
$started = Get-Date
$env:DOTNET_ROOT = 'D:\New folder\dotnet10'
$env:RYUJINX_HOMEBREW_SHADER_CACHE_ID = '0500000053415352'
$style = if ($Visible) { 'Normal' } else { 'Minimized' }
if ($Visible) { $env:RYUBING_INTERACTIVE = '1' } else { Remove-Item Env:RYUBING_INTERACTIVE -ErrorAction SilentlyContinue }
if ($RenderDoc) {
    # RenderDoc's Vulkan layer from its portable folder, for this process only (no system registration).
    $env:VK_ADD_LAYER_PATH = 'D:\Banjo kazooie port\tools\RenderDoc_1.46_64'
    $env:VK_INSTANCE_LAYERS = 'VK_LAYER_RENDERDOC_Capture'
    $env:ENABLE_VULKAN_RENDERDOC_CAPTURE = '1'
}
$nroArg = '"' + (Join-Path $sd 'sasrt.nro') + '"'
if ($RenderDoc -and $Visible) {
    # sasrt-nx (2026-10-20): RenderDoc as the Vulkan layer alone (the environment above), as banjo-nx captures Ryujinx:
    # under renderdoccmd, which hooks every API, the visible window's Avalonia compositor (D3D through ANGLE) crashed
    # at its first frame. Captures are taken by target control (tools/rdc_trigger.py) and land in RenderDoc's temp folder.
    $p = Start-Process -FilePath $exe -ArgumentList @('-r', ('"' + $data + '"'), $nroArg) -WindowStyle $style -PassThru `
        -RedirectStandardOutput (Join-Path $out "${Name}_stdout.txt") -RedirectStandardError (Join-Path $out "${Name}_stderr.txt")
} elseif ($RenderDoc) {
    $rdc = 'D:\Banjo kazooie port\tools\RenderDoc_1.46_64\renderdoccmd.exe'
    New-Item -ItemType Directory -Force (Join-Path $root 'out\rdc') | Out-Null
    $p = Start-Process -FilePath $rdc -WindowStyle Minimized -PassThru -ArgumentList @('capture', '-w', '-c',
        ('"' + (Join-Path $root "out\rdc\ryu_$Name") + '"'), ('"' + $exe + '"'), '-r', ('"' + $data + '"'), $nroArg) `
        -RedirectStandardOutput (Join-Path $out "${Name}_stdout.txt") -RedirectStandardError (Join-Path $out "${Name}_stderr.txt")
} else {
    $p = Start-Process -FilePath $exe -ArgumentList @('-r', ('"' + $data + '"'), $nroArg) -WindowStyle $style -PassThru `
        -RedirectStandardOutput (Join-Path $out "${Name}_stdout.txt") -RedirectStandardError (Join-Path $out "${Name}_stderr.txt")
}
if ($p.WaitForExit($Seconds * 1000)) {
    '{0}: Ryujinx exited by itself after {1:n1} s (code {2})' -f $Name, ((Get-Date) - $started).TotalSeconds, $p.ExitCode
} else {
    # Under RenderDoc, Ryujinx is renderdoccmd's child: this port's instance only (its data folder on the command line).
    if ($RenderDoc -and -not $Visible) {
        Get-CimInstance Win32_Process -Filter "Name='Ryujinx.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -like "*$data`"*" -and $_.ParentProcessId -eq $p.Id } | ForEach-Object {
                Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
                Wait-Process -Id $_.ProcessId -Timeout 20 -ErrorAction SilentlyContinue
            }
    }
    Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    $p.WaitForExit(20000) | Out-Null
    '{0}: stopped after {1} s' -f $Name, $Seconds
}
$log = Get-ChildItem (Join-Path $sd 'logs') -Filter *.log -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -ge $started } | Sort-Object LastWriteTime | Select-Object -Last 1
if ($log) { Copy-Item $log.FullName (Join-Path $out "$Name.log"); "game log: out\ryujinx\$Name.log ($($log.Length) bytes)" }
else { 'no game log written' }
$ryu = Get-ChildItem (Join-Path $data 'Logs') -Filter *.log -ErrorAction SilentlyContinue | Sort-Object LastWriteTime |
    Select-Object -Last 1
if ($ryu) { Copy-Item $ryu.FullName (Join-Path $out "${Name}_ryu.log") }
