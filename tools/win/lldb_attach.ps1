# sasrt-nx (2026-11-08): starts the PC build as boot_test.ps1 does (-SwitchConfig's keys, the input script, muted and
# minimised) and attaches LLVM's lldb to it at once; on a crash the backtraces go to the output file. Stops only this
# run's process.
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\win\lldb_attach.ps1 [-SwitchConfig] [-InputScript f] [-Seconds 60] [-Out out\lldb.txt]
param(
    [switch]$SwitchConfig,
    [string]$InputScript = '',
    [int]$Seconds = 60,
    [string]$Out = 'out\lldb.txt'
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
foreach ($k in $overrides.Keys) { Set-Item -Path ("env:REX_" + $k.ToUpper()) -Value $overrides[$k] }
if ($InputScript) {
    $env:REX_SASRT_INPUT_SCRIPT = if (Test-Path $InputScript) { (Get-Content $InputScript -Raw).Trim() } else { $InputScript }
}
$env:REX_AUDIO_MUTE = 'true'
$env:REX_WINDOW_START_MINIMIZED = 'true'
$dir = Join-Path $root 'out\pc'
$game = Start-Process -FilePath (Join-Path $dir 'sasrt.exe') -WorkingDirectory $dir -PassThru -WindowStyle Minimized
$lldb = Join-Path $root '..\_tools\llvm\bin\lldb.exe'
$outPath = Join-Path $root $Out
$dbg = Start-Process -FilePath $lldb -WorkingDirectory $dir -PassThru -WindowStyle Minimized `
    -RedirectStandardOutput $outPath -RedirectStandardError ($outPath + '.err') `
    -ArgumentList @('-b', '-p', "$($game.Id)", '-o', 'continue', '-k', '"thread backtrace -c 40"', '-k', '"thread backtrace all -c 5"', '-k', '"process kill"')
if (-not $dbg.WaitForExit($Seconds * 1000)) {
    Stop-Process -Id $game.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $dbg.Id -Force -ErrorAction SilentlyContinue
    "no crash in $Seconds s"
}
Stop-Process -Id $game.Id -Force -ErrorAction SilentlyContinue
foreach ($k in $overrides.Keys) { Set-Item -Path ("env:REX_" + $k.ToUpper()) -Value '' }
"lldb output: $outPath"
