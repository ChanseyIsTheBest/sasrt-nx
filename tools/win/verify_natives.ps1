# Verify mode on the native replacements (app/src/hot): races on chosen tracks with sasrt_cpu_verify = true (every
# call of a guarded native is checked against the recompiled original, the renderer's self-checks too) and a summary
# of the [hot] lines of each run: hooks on, checks without difference, DIFFERENCE lines, frame rate.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\win\verify_natives.ps1 [-Tracks 2.3,0.0] [-Seconds 240]
param(
    [string[]]$Tracks = @('2.3', '0.0'),
    [int]$Seconds = 240,
    [string]$UserData = 'out\pc\user_100'
)
$Tracks = @($Tracks | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$env:REX_USER_DATA_ROOT = (Resolve-Path (Join-Path $root $UserData)).Path
$env:REX_MASSEFFECT_RENDERER_NATIVE = 'true'
$env:REX_SASRT_CPU_VERIFY = 'true'
foreach ($t in $Tracks) {
    $cup, $track = $t.Split('.') | ForEach-Object { [int]$_ }
    $steps = @('55=A', '62=START', '66=A', '70=A', '73=RIGHT', '75=RIGHT', '77=RIGHT', '79=A')
    for ($k = 0; $k -lt $cup; ++$k) { $steps += ('{0:0.0}=RIGHT' -f (81.0 + 0.6 * $k)) }
    $steps += '83.5=A'
    if ($track -eq 1 -or $track -eq 3) { $steps += '85.5=RIGHT' }
    if ($track -ge 2) { $steps += '86.3=DOWN' }
    $steps += @('87.5=A', '91.5=A', '95.5=A', '99.5=A', '103.5=A', '107=A', '110+300=RT')
    $start = Get-Date
    & (Join-Path $root 'tools\win\boot_test.ps1') -InputScript ($steps -join '; ') -Seconds $Seconds -Tail 0 2>&1 |
        Out-String -Width 300 | Select-Object -First 1
    $L = Get-ChildItem (Join-Path $root 'out\pc\logs\*.log') | Where-Object { $_.LastWriteTime -ge $start } |
        Sort-Object LastWriteTime | Select-Object -Last 1
    "== track $t, log $($L.Name)"
    "hooks on: " + (Select-String -Path $L.FullName -Pattern '\[hot\] .*native replacement ON').Count +
        ", checks without difference reported: " + (Select-String -Path $L.FullName -Pattern 'checks, no difference').Count +
        ", DIFFERENCE lines: " + (Select-String -Path $L.FullName -Pattern '\[hot\] DIFFERENCE').Count
    Select-String -Path $L.FullName -Pattern '\[hot\] DIFFERENCE' | ForEach-Object { $_.Line.Substring($_.Line.IndexOf('[hot]')) }
    "swaps/10s: " + ((Select-String -Path $L.FullName -Pattern '10\.0 s: ([0-9]+) Swaps' -AllMatches |
        ForEach-Object { $_.Matches[0].Groups[1].Value }) -join ' ')
    "uses: " + ((Select-String -Path $L.FullName -Pattern '\[enh\] uses in the last' | Select-Object -Last 1).Line -replace '.*\[enh\] ', '')
}
$env:REX_SASRT_CPU_VERIFY = $null
$env:REX_MASSEFFECT_RENDERER_NATIVE = $null
