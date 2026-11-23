# sasrt-nx (2026-11-11): build_switch.ps1 -InPlace and pgo_cycle.ps1 -InPlace (the in-place copies' folders and profile).
R = 'D:/sonic transformed/sasrt-nx/'


def patch(rel, edits, mark):
    p = R + rel
    b = open(p, 'rb').read()
    bom = b.startswith(b'\xef\xbb\xbf')
    crlf = b'\r\n' in b
    s = b.decode('utf-8-sig').replace('\r\n', '\n')
    if mark in s:
        print('already patched:', rel)
        return
    for o, n in edits:
        assert s.count(o) == 1, (rel, o[:70], s.count(o))
        s = s.replace(o, n)
    out = (s.replace('\n', '\r\n') if crlf else s).encode('utf-8')
    open(p, 'wb').write((b'\xef\xbb\xbf' if bom else b'') + out)
    print('patched:', rel)


patch('tools/win/build_switch.ps1', [
    (r'''    [switch]$GuardForms
)''', r'''    [switch]$GuardForms,
    # sasrt-nx (2026-11-11, the user: "go ahead with the plan"): the machine copies in place of the generated functions
    # (CMake SASRT_HOT_IN_PLACE: no hooks, no guard), with their own PGO profile folder (pgo-inplace/) and, without
    # -Build, their own build folders (out\nx-inplace-gen for -Pgo generate, out\nx-inplace otherwise).
    [switch]$InPlace
)'''),
    (r'''$folder = if ($Build) { $Build } elseif ($Pgo -eq 'generate')''',
     r'''$folder = if ($Build) { $Build } elseif ($InPlace -and $Pgo -eq 'generate') { 'out\nx-inplace-gen' } elseif ($InPlace) { 'out\nx-inplace' } elseif ($Pgo -eq 'generate')'''),
    (r'''Write-Output "sasrt: Switch build in $folder, LTO $lto''', r'''# sasrt-nx (2026-11-11): the copies in place, and their profile folder
$inplaceOpt = if ($InPlace) { 'ON' } else { 'OFF' }
$cachedInPlace = Select-String -Path (Join-Path $build 'CMakeCache.txt') -Pattern '^SASRT_HOT_IN_PLACE:BOOL=(.*)$' |
    ForEach-Object { $_.Matches[0].Groups[1].Value } | Select-Object -First 1
if ("$cachedInPlace" -ne $inplaceOpt) {
    & cmake "-DSASRT_HOT_IN_PLACE=$inplaceOpt" $build
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
}
if ($Pgo -and $InPlace) {
    $pgoDir = (Join-Path $root 'pgo-inplace').Replace('\', '/')
    $cachedPgoDir = Select-String -Path (Join-Path $build 'CMakeCache.txt') -Pattern '^SASRT_PGO_DIR:PATH=(.*)$' |
        ForEach-Object { $_.Matches[0].Groups[1].Value } | Select-Object -First 1
    if ("$cachedPgoDir" -ne $pgoDir) {
        & cmake "-DSASRT_PGO_DIR=$pgoDir" $build
        if ($LASTEXITCODE) { exit $LASTEXITCODE }
    }
}
Write-Output "sasrt: Switch build in $folder, in place $inplaceOpt, LTO $lto'''),
], 'SASRT_HOT_IN_PLACE')

patch('tools/win/pgo_cycle.ps1', [
    (r'''    [string]$Streams = ''
)''', r'''    [string]$Streams = '',
    # sasrt-nx (2026-11-11): the in-place copies' cycle (build_switch.ps1 -InPlace: out\nx-inplace-gen, out\nx-inplace,
    # the profile in pgo-inplace/)
    [switch]$InPlace
)'''),
    (r'''    & $build -Pgo generate -Build out\nx-pgo-gen
    exit $LASTEXITCODE''', r'''    if ($InPlace) { & $build -Pgo generate -Build out\nx-inplace-gen -InPlace } else { & $build -Pgo generate -Build out\nx-pgo-gen }
    exit $LASTEXITCODE'''),
    (r'''$pgo = Join-Path $root 'pgo'
''', r'''$pgo = Join-Path $root $(if ($InPlace) { 'pgo-inplace' } else { 'pgo' })
'''),
    (r'''& python (Join-Path $root 'tools\pgo_merge.py') $Streams''', r'''& python (Join-Path $root 'tools\pgo_merge.py') $Streams $pgo'''),
    (r'''$folder = Join-Path $root 'out\nx'
''', r'''$folder = Join-Path $root $(if ($InPlace) { 'out\nx-inplace' } else { 'out\nx' })
'''),
    (r'''& $build -Pgo use -Final -Build out\nx
exit $LASTEXITCODE''', r'''if ($InPlace) { & $build -Pgo use -Final -Build out\nx-inplace -InPlace } else { & $build -Pgo use -Final -Build out\nx }
exit $LASTEXITCODE'''),
], 'pgo-inplace')
