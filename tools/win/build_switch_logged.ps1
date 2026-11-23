# Runs tools\win\build_switch.ps1 with its output in a log file, then writes <log>.done with the exit code and the
# minutes it took (for unattended builds: a background shell can poll for the .done file).
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\win\build_switch_logged.ps1 out\nx_build.log [-Jobs 8] [-Reconfigure] [-Final]
param(
    [Parameter(Mandatory = $true)][string]$Log,
    [int]$Jobs = 8,
    [switch]$Reconfigure,
    [switch]$Final  # with LTO (final builds only, the user's rule of 2026-10-19)
)
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not [System.IO.Path]::IsPathRooted($Log)) { $Log = Join-Path $root $Log }
$done = "$Log.done"
if (Test-Path $done) { Remove-Item -Force $done }
$started = Get-Date
$arguments = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $PSScriptRoot 'build_switch.ps1'), '-Jobs', "$Jobs")
if ($Reconfigure) { $arguments += '-Reconfigure' }
if ($Final) { $arguments += '-Final' }
# UTF-8 (a plain *> redirection writes UTF-16 in Windows PowerShell, which grep cannot follow).
& powershell @arguments 2>&1 | ForEach-Object { "$_" } | Out-File -Encoding utf8 $Log
$code = $LASTEXITCODE
$minutes = [math]::Round(((Get-Date) - $started).TotalMinutes, 1)
"exit=$code minutes=$minutes" | Set-Content -Encoding ascii $done
"exit=$code minutes=$minutes"
