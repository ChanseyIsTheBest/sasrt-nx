# PC A/B of the native replacements batch (sasrt_cpu_natives on / off): the same race twice with the PC profiler, then
# the busy share of each game thread and the CPU time per thread from logs/pc_profile.log (windows of the race only).
# The ring thread limits the PC's frame rate on the heavy tracks, so this compares CPU time, not fps; the console
# decides (x86 and ARM costs differ).
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\win\natives_ab.ps1 [-Track 2.3] [-Seconds 230]
param(
    [string]$Track = '2.3',
    [int]$Seconds = 230,
    [string]$UserData = 'out\pc\user_100'
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
foreach ($natives in @('true', 'false')) {
    $env:REX_SASRT_CPU_NATIVES = $natives
    Remove-Item -Force $profile -ErrorAction SilentlyContinue
    & (Join-Path $root 'tools\win\boot_test.ps1') -InputScript ($steps -join '; ') -Seconds $Seconds -Tail 0 2>&1 |
        Out-String -Width 300 | Select-Object -First 1
    $copy = Join-Path $root "out\pc\logs\pc_profile_natives_$natives.log"
    Copy-Item -Force $profile $copy
    "== sasrt_cpu_natives = $natives ($copy)"
    # Windows 12+ are the race (the first ~11 are boot, menus and loading).
    python (Join-Path $root 'tools\thread_busy.py') $copy --from-window 12
}
$env:REX_SASRT_CPU_NATIVES = $null
$env:REX_SASRT_PC_PROFILE_S = $null
$env:REX_MASSEFFECT_RENDERER_NATIVE = $null
