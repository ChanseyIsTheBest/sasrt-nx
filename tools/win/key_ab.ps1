# PC A/B of one boolean key: the same scripted race twice (the key off, then on) with the PC profiler, then the busy
# share and CPU time of each thread (tools/thread_busy.py, race windows only) and the ring thread's own timer
# ("[native] ring thread: ..." lines of the race). The PC shares its GPU with other work: compare CPU time, and repeat.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\win\key_ab.ps1 -Key sasrt_cpu_direct_state [-Track 2.3]
#                                                       [-Seconds 230] [-Order off,on]
#
# -InRun (futari-nx's method): one run instead of two, the keys switched off and on together every -PeriodMs at a Swap
# by the ring thread (sasrt_ab_keys, sasrt_ab_period_ms); the "[ab]" lines give each phase's Swaps per second, ring
# work per Swap and per draw, ring cycles per draw and the whole process's CPU per Swap. Other work on the PC then
# weighs on both phases alike. Only the port's own keys (SASRT_ENHANCEMENT), on at start.
param(
    [Parameter(Mandatory = $true)][string]$Key,
    [string]$Track = '2.3',
    [int]$Seconds = 230,
    [string]$Order = 'off,on',
    [switch]$SwitchConfig,  # the console's settings (boot_test.ps1 -SwitchConfig), the key on top
    [string]$UserData = 'out\pc\user_100',
    [switch]$InRun,
    [int]$PeriodMs = 2000
)
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$env:REX_USER_DATA_ROOT = (Resolve-Path (Join-Path $root $UserData)).Path
$env:REX_MASSEFFECT_RENDERER_NATIVE = 'true'
$env:REX_SASRT_PC_PROFILE_S = '10'
$cup, $slot = $Track.Split('.') | ForEach-Object { [int]$_ }
$steps = @('55=A', '62=START', '66=A', '70=A', '73=RIGHT', '75=RIGHT', '77=RIGHT', '79=A')
for ($k = 0; $k -lt $cup; ++$k) { $steps += ('{0:0.0}=RIGHT' -f (81.0 + 0.6 * $k)) }
$steps += '83.5=A'
if ($slot -eq 1 -or $slot -eq 3) { $steps += '85.5=RIGHT' }
if ($slot -ge 2) { $steps += '86.3=DOWN' }
$steps += @('87.5=A', '91.5=A', '95.5=A', '99.5=A', '103.5=A', '107=A', '110+300=RT')
$profile = Join-Path $root 'out\pc\logs\pc_profile.log'
# -Key can name several boolean keys separated by ';' (all off, then all on): the A/B of a whole set.
$keys = @($Key -split ';' | Where-Object { $_ })
$label = if ($keys.Count -gt 1) { "set_of_$($keys.Count)" } else { $Key }
if ($InRun) {
    $env:REX_SASRT_AB_KEYS = ($keys -join ';')
    $env:REX_SASRT_AB_PERIOD_MS = "$PeriodMs"
    Remove-Item -Force $profile -ErrorAction SilentlyContinue
    $start = Get-Date
    & (Join-Path $root 'tools\win\boot_test.ps1') -InputScript ($steps -join '; ') -Seconds $Seconds -Tail 0 `
        -SwitchConfig:$SwitchConfig 2>&1 | Out-String -Width 300 | Select-Object -First 1
    $copy = Join-Path $root "out\pc\logs\pc_profile_${label}_inrun.log"
    Copy-Item -Force $profile $copy
    $L = Get-ChildItem (Join-Path $root 'out\pc\logs\sasrt_*.log') | Where-Object { $_.LastWriteTime -ge $start } |
        Sort-Object LastWriteTime | Select-Object -Last 1
    "== in-run A/B of $Key, every $PeriodMs ms ($($L.Name), $copy)"
    Select-String -Path $L.FullName -Pattern '\[ab\] cumulative' | Select-Object -Last 1 |
        ForEach-Object { $_.Line.Substring($_.Line.IndexOf('[ab]')) }
    # The race: report windows 11 on (the A/B starts at the first Swap; the race at about 110 s).
    python (Join-Path $root 'tools\ab_summary.py') $L.FullName --from-window 11
    python (Join-Path $root 'tools\thread_busy.py') $copy --from-window 12
    $env:REX_SASRT_AB_KEYS = $null
    $env:REX_SASRT_AB_PERIOD_MS = $null
    $env:REX_SASRT_PC_PROFILE_S = $null
    $env:REX_MASSEFFECT_RENDERER_NATIVE = $null
    exit 0
}
foreach ($side in ($Order -split ',')) {
    $value = if ($side -eq 'on') { 'true' } else { 'false' }
    foreach ($k in $keys) { Set-Item -Path ("env:REX_" + $k.ToUpper()) -Value $value }
    Remove-Item -Force $profile -ErrorAction SilentlyContinue
    $start = Get-Date
    & (Join-Path $root 'tools\win\boot_test.ps1') -InputScript ($steps -join '; ') -Seconds $Seconds -Tail 0 `
        -SwitchConfig:$SwitchConfig -Set (($keys | ForEach-Object { "$_=$value" }) -join ';') 2>&1 |
        Out-String -Width 300 | Select-Object -First 1
    $copy = Join-Path $root "out\pc\logs\pc_profile_${label}_$side.log"
    Copy-Item -Force $profile $copy
    $L = Get-ChildItem (Join-Path $root 'out\pc\logs\sasrt_*.log') | Where-Object { $_.LastWriteTime -ge $start } |
        Sort-Object LastWriteTime | Select-Object -Last 1
    "== $Key = $side ($($L.Name), $copy)"
    "swaps per 10 s (race): " + ((Select-String -Path $L.FullName -Pattern '10\.0 s: ([0-9]+) Swaps' -AllMatches |
        Select-Object -Skip 11 | ForEach-Object { $_.Matches[0].Groups[1].Value }) -join ' ')
    # Windows 12+ are the race (the first ~11 are boot, menus and loading).
    python (Join-Path $root 'tools\thread_busy.py') $copy --from-window 12
    Select-String -Path $L.FullName -Pattern '\[native\] ring thread: ' | Select-Object -Skip 11 |
        ForEach-Object { $_.Line.Substring($_.Line.IndexOf('ring thread:')) }
}
foreach ($k in $keys) { Set-Item -Path ("env:REX_" + $k.ToUpper()) -Value '' }
$env:REX_SASRT_PC_PROFILE_S = $null
$env:REX_MASSEFFECT_RENDERER_NATIVE = $null
