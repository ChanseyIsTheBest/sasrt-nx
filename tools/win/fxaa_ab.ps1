# A/B of one renderer key: the same Ocean View Single Race twice with the native renderer, the key false then true,
# each with a 1280x720 capture from the countdown (the car stands still on the grid, so the first frames of both runs
# show the same image) into the race; then tools/speck_score.py on both. Made for sasrt_native_texture_exp_bias
# (FXAA 360's specks), hence the name.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\win\fxaa_ab.ps1 [-Key sasrt_native_texture_integer]
# Captures: out\pc\captures\<name>_false.rgba and <name>_true.rgba (name: fxaa_bias for the default key, else the key).
param(
    [string]$Key = 'sasrt_native_texture_exp_bias',
    [string]$UserData = 'out\pc\user_100'
)
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$cap = Join-Path $root 'out\pc\captures'
$name = if ($Key -eq 'sasrt_native_texture_exp_bias') { 'fxaa_bias' } else { $Key }
$variable = 'REX_' + $Key.ToUpperInvariant()
$env:REX_USER_DATA_ROOT = (Resolve-Path (Join-Path $root $UserData)).Path
$env:REX_SASRT_VIDEO_HALF = 'false'
$env:REX_MASSEFFECT_RENDERER_NATIVE = 'true'
$script = '55=A; 62=START; 66=A; 70=A; 73=RIGHT; 75=RIGHT; 77=RIGHT; 79=A; 83.5=A; 87.5=A; 91.5=A; 95.5=A; 99.5=A; 103.5=A; 107=A; 113+300=RT'
foreach ($value in @('false', 'true')) {
    Set-Item -Path "env:$variable" -Value $value
    & (Join-Path $root 'tools\win\boot_test.ps1') -InputScript $script -Seconds 60 -VideoAt 106 -VideoFrames 200 -VideoEvery 3 -VideoFps 28 -Tail 0 2>&1 |
        Out-String -Width 300 | Select-Object -First 1
    $raw = Join-Path $cap 'video_106s.rgba'
    if (Test-Path $raw) {
        Move-Item -Force $raw (Join-Path $cap "${name}_$value.rgba")
        Move-Item -Force (Join-Path $cap 'video_106s.txt') (Join-Path $cap "${name}_$value.txt")
        Remove-Item -Force (Join-Path $cap 'video_106s.mp4'), (Join-Path $cap 'video_106s.sheet.png') -ErrorAction SilentlyContinue
    }
    $log = Get-ChildItem (Join-Path $root 'out\pc\logs\*.log') | Sort-Object LastWriteTime | Select-Object -Last 1
    "$Key $value, log $($log.Name): " + ((Select-String -Path $log.FullName -Pattern 'texture exponent bias|integer texture format' |
        ForEach-Object { $_.Line.Substring($_.Line.IndexOf('[native]')) }) -join ' / ')
}
Remove-Item -Path "env:$variable" -ErrorAction SilentlyContinue
$env:REX_MASSEFFECT_RENDERER_NATIVE = $null
foreach ($value in @('false', 'true')) {
    python (Join-Path $root 'tools\speck_score.py') (Join-Path $cap "${name}_$value.rgba") --quiet
}
