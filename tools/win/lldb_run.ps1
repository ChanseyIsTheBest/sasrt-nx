# sasrt-nx (2026-11-08): the PC build under lldb (LLVM's, D:\sonic transformed\_tools\llvm) with boot_test.ps1's
# environment (-SwitchConfig's keys as REX_<KEY>, the input script, muted and minimised): on a crash it writes the
# stopped thread's backtrace and every thread's top frames to the output file, then stops the process.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\win\lldb_run.ps1 [-SwitchConfig] [-InputScript f] [-Seconds 120] [-Out out\lldb.txt]
param(
    [switch]$SwitchConfig,
    [string]$InputScript = '',
    [int]$Seconds = 120,
    [string]$Out = 'out\lldb.txt',
    [string]$Set = ''
)
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$overrides = [ordered]@{}
if ($SwitchConfig) {
    foreach ($line in Get-Content (Join-Path $root 'app\sasrt_switch.toml')) {
        if ($line -match '^\s*([a-z0-9_]+)\s*=\s*("?)([^"#]*?)\2\s*(#.*)?$') {
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
    $env:REX_SASRT_INPUT_SCRIPT = if (Test-Path $InputScript) { (Get-Content $InputScript -Raw).Trim() } else { $InputScript }
}
$env:REX_AUDIO_MUTE = 'true'
$env:REX_WINDOW_START_MINIMIZED = 'true'
$lldb = Join-Path $root '..\_tools\llvm\bin\lldb.exe'
$dir = Join-Path $root 'out\pc'
$outPath = Join-Path $root $Out
$cmds = Join-Path $root 'out\lldb_cmds.txt'
@('run', 'thread backtrace -c 40', 'thread backtrace all -c 6', 'process kill', 'quit') | Set-Content -Encoding ascii $cmds
$p = Start-Process -FilePath $lldb -WorkingDirectory $dir -PassThru -WindowStyle Minimized `
    -RedirectStandardOutput $outPath -RedirectStandardError ($outPath + '.err') `
    -ArgumentList @('-b', '-k', '"thread backtrace -c 40"', '-k', '"thread backtrace all -c 6"', '-k', '"process kill"', '-o', 'run', '--', 'sasrt.exe')
if (-not $p.WaitForExit($Seconds * 1000)) {
    # No crash in time: stop this run's processes only (lldb and its sasrt.exe child).
    Get-CimInstance Win32_Process -Filter "Name='sasrt.exe'" | Where-Object { $_.ParentProcessId -eq $p.Id } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    "no crash in $Seconds s"
}
foreach ($k in $overrides.Keys) { Set-Item -Path ("env:REX_" + $k.ToUpper()) -Value '' }
"lldb output: $outPath"
