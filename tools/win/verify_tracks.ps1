# Verify mode (sasrt_cpu_verify: every fast path checked against the original on every use) on chosen tracks with the
# console's settings (boot_test.ps1 -SwitchConfig), then the summary of each run: the [verify] line, the direct state and
# vertex containment reports, and any DIFFERENCE / lost-record line.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\win\verify_tracks.ps1 [-Tracks 0.0,3.0] [-Seconds 240]
param(
    [string]$Tracks = '0.0,3.0',
    [int]$Seconds = 240,
    [string]$UserData = 'out\pc\user_100'
)
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$env:REX_USER_DATA_ROOT = (Resolve-Path (Join-Path $root $UserData)).Path
foreach ($t in ($Tracks -split ',')) {
    $cup, $slot = $t.Split('.') | ForEach-Object { [int]$_ }
    $steps = @('55=A', '62=START', '66=A', '70=A', '73=RIGHT', '75=RIGHT', '77=RIGHT', '79=A')
    for ($k = 0; $k -lt $cup; ++$k) { $steps += ('{0:0.0}=RIGHT' -f (81.0 + 0.6 * $k)) }
    $steps += '83.5=A'
    if ($slot -eq 1 -or $slot -eq 3) { $steps += '85.5=RIGHT' }
    if ($slot -ge 2) { $steps += '86.3=DOWN' }
    $steps += @('87.5=A', '91.5=A', '95.5=A', '99.5=A', '103.5=A', '107=A', '110+300=RT')
    $start = Get-Date
    & (Join-Path $PSScriptRoot 'boot_test.ps1') -SwitchConfig -Set 'sasrt_cpu_verify=true' -InputScript ($steps -join '; ') `
        -Seconds $Seconds -Tail 0 2>&1 | Out-String -Width 300 | Select-Object -First 1
    $L = Get-ChildItem (Join-Path $root 'out\pc\logs\sasrt_*.log') | Where-Object { $_.LastWriteTime -ge $start } |
        Sort-Object LastWriteTime | Select-Object -Last 1
    "== track $t, log $($L.Name)"
    foreach ($pattern in '\[verify\] checks done', 'direct state \(cumulative\)', 'direct flush \(sasrt_cpu_direct_flush',
                         'vertex containment', 'EDRAM draw memo', '\[api\] native records') {
        $line = (Select-String -Path $L.FullName -Pattern $pattern | Select-Object -Last 1).Line
        if ($line) { $line.Substring([math]::Max(0, $line.IndexOf('] [', 40) + 2)) }
    }
    # Every DIFFERENCE line ([native], [hot], [api], ...) and lost records.
    Select-String -CaseSensitive -Path $L.FullName -Pattern 'DIFFERENCE(?! line)|not found \(marker' | Select-Object -First 5 |
        ForEach-Object { $_.Line.Substring([math]::Max(0, $_.Line.IndexOf('] [', 40) + 2)) }
}
