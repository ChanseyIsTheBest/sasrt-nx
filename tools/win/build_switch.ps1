# Builds the Nintendo Switch NRO: out\nx\sasrt.nro (devkitA64 GCC + libnx, static NVK from the Mesa Horizon SDK).
# The generated code must already exist (tools\codegen.ps1 with the PC SDK): a cross build cannot run rexglue.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\win\build_switch.ps1 [-Jobs 8] [-Reconfigure] [-Final]
# NVK_SDK (environment) overrides the Mesa SDK folder (it must contain lib\libvulkan.a).
# -Final: with link-time optimisation (SASRT_SWITCH_LTO). The user's rule of 2026-10-19: LTO for final builds only;
# every other build is without it (each build sets the option, so the cache follows the flag).
param(
    [int]$Jobs = 8,
    [switch]$Reconfigure,
    [switch]$Final,
    # sasrt-nx (2026-11-09): PGO (docs/pgo-lto.md): -Pgo generate builds the instrumented NRO in out\nx-pgo-gen, -Pgo use
    # the optimised one in out\nx-pgo-use (with -Final: LTO too). -Build names another folder.
    [string]$Pgo = '',
    [string]$Build = '',
    # sasrt-nx (2026-11-10, machine-copy idea 27): -Final (the shipping build) leaves the localized copies' guard forms out
    # (SASRT_HOT_GUARD_FORMS OFF: no guard, every copy called directly); -GuardForms keeps them (a guard / verify build).
    [switch]$GuardForms,
    # sasrt-nx (2026-11-11, the user: "go ahead with the plan"): the machine copies in place of the generated functions
    # (CMake SASRT_HOT_IN_PLACE: no hooks, no guard), with their own PGO profile folder (pgo-inplace/) and, without
    # -Build, their own build folders (out\nx-inplace-gen for -Pgo generate, out\nx-inplace otherwise).
    [switch]$InPlace,
    # sasrt-nx (2026-11-13, Blur's CG-13 A/B): CMake BLUR_FPCR_ONE_MODE ON (all guest float code in the flush mode; NOT
    # bit-exact), with -InPlace in its own build folders (out\nx-onemode-gen, out\nx-onemode) and profile (pgo-onemode/).
    [switch]$OneMode,
    # sasrt-nx (2026-11-13): CG-13 is ON by default in this port (the user's choice); -BitExact builds without it
    # (BLUR_FPCR_ONE_MODE OFF), for an A/B against the default.
    [switch]$BitExact,
    # sasrt-nx (2026-11-22, the web installer): -ReleaseShaders builds the release NRO (CMake BANJO_RENUT_RELEASE_SHADERS:
    # app/out/renut_switch_release from tools/renut_release_shaders.py --only, the page makes deko3d_glsl.bin); without
    # it every translated shader is built in, as always
    [switch]$ReleaseShaders
)
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $PSScriptRoot 'env.ps1')  # VS CMake and Ninja on PATH (the compilers come from the toolchain file)
$nvk = if ($env:NVK_SDK) { $env:NVK_SDK } else {
    'C:/devkitPro/mesa-switch-main-nfsmw-source/mesa-switch-main/mesa-unified-install/opt/devkitpro/portlibs/switch' }
# devkitPro's installer exports DEVKITPRO as an MSYS path (/opt/devkitpro) that Windows CMake cannot open.
$devkitpro = if ($env:DEVKITPRO -and (Test-Path $env:DEVKITPRO)) { $env:DEVKITPRO } else { 'C:/devkitPro' }
# CMake's compiler checks (try_compile) read the toolchain file again without the cache, i.e. from the environment:
# export the Windows path there too, or they look for /opt/devkitpro/libnx/switch.specs.
$env:DEVKITPRO = $devkitpro
$folder = if ($Build) { $Build } elseif ($OneMode -and $Pgo -eq 'generate') { 'out\nx-onemode-gen' } elseif ($OneMode) { 'out\nx-onemode' } elseif ($InPlace -and $Pgo -eq 'generate') { 'out\nx-inplace-gen' } elseif ($InPlace) { 'out\nx-inplace' } elseif ($Pgo -eq 'generate') { 'out\nx-pgo-gen' } elseif ($Pgo -eq 'use') { 'out\nx-pgo-use' } else { 'out\nx' }
$build = Join-Path $root $folder
$glslang = Join-Path $root 'out\glslang\StandAlone\glslangValidator.exe'  # host tool: SPIR-V is portable
if ($Reconfigure -or -not (Test-Path (Join-Path $build 'CMakeCache.txt'))) {
    & cmake -S (Join-Path $root 'app') -B $build -G Ninja -DCMAKE_BUILD_TYPE=Release `
        "-DCMAKE_TOOLCHAIN_FILE=$root\tools\switch\cmake\switch-devkitA64.cmake" `
        "-DREXGLUE_SWITCH_NVK_SDK=$nvk" "-DSASRT_GLSLANG_VALIDATOR=$glslang" "-DDEVKITPRO=$devkitpro" `
        "-DCMAKE_MAKE_PROGRAM=$((Get-Command ninja).Source)"
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
}
# LTO only with -Final: set the option when the cache holds the other value (a re-configure, then the build compiles
# everything again in the other form).
$lto = if ($Final) { 'ON' } else { 'OFF' }
$cached = Select-String -Path (Join-Path $build 'CMakeCache.txt') -Pattern '^SASRT_SWITCH_LTO:BOOL=(.*)$' |
    ForEach-Object { $_.Matches[0].Groups[1].Value } | Select-Object -First 1
if ($cached -ne $lto) {
    & cmake "-DSASRT_SWITCH_LTO=$lto" $build
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
}
$cachedPgo = Select-String -Path (Join-Path $build 'CMakeCache.txt') -Pattern '^SASRT_PGO:STRING=(.*)$' |
    ForEach-Object { $_.Matches[0].Groups[1].Value } | Select-Object -First 1
if ("$cachedPgo" -ne $Pgo) {
    & cmake "-DSASRT_PGO=$Pgo" $build
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
}
$forms = if ($Final -and -not $GuardForms) { 'OFF' } else { 'ON' }
$cachedForms = Select-String -Path (Join-Path $build 'CMakeCache.txt') -Pattern '^SASRT_HOT_GUARD_FORMS:BOOL=(.*)$' |
    ForEach-Object { $_.Matches[0].Groups[1].Value } | Select-Object -First 1
if ("$cachedForms" -ne $forms) {
    & cmake "-DSASRT_HOT_GUARD_FORMS=$forms" $build
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
}
# sasrt-nx (2026-11-11): the copies in place, and their profile folder
$inplaceOpt = if ($InPlace) { 'ON' } else { 'OFF' }
$cachedInPlace = Select-String -Path (Join-Path $build 'CMakeCache.txt') -Pattern '^SASRT_HOT_IN_PLACE:BOOL=(.*)$' |
    ForEach-Object { $_.Matches[0].Groups[1].Value } | Select-Object -First 1
if ("$cachedInPlace" -ne $inplaceOpt) {
    & cmake "-DSASRT_HOT_IN_PLACE=$inplaceOpt" $build
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
}
# sasrt-nx (2026-11-13): CG-13's switch, set either way (a folder keeps what it was configured with)
$oneModeOpt = if ($BitExact) { 'OFF' } else { 'ON' }  # sasrt-nx (2026-11-13): ON by default here (-OneMode: its own folders)
$cachedOneMode = Select-String -Path (Join-Path $build 'CMakeCache.txt') -Pattern '^BLUR_FPCR_ONE_MODE:BOOL=(.*)$' |
    ForEach-Object { $_.Matches[0].Groups[1].Value } | Select-Object -First 1
if ("$cachedOneMode" -ne $oneModeOpt) {
    & cmake "-DBLUR_FPCR_ONE_MODE=$oneModeOpt" $build
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
}
# sasrt-nx (2026-11-22): the release's shader set, set either way
$releaseOpt = if ($ReleaseShaders) { 'ON' } else { 'OFF' }
$cachedRelease = Select-String -Path (Join-Path $build 'CMakeCache.txt') -Pattern '^BANJO_RENUT_RELEASE_SHADERS:BOOL=(.*)$' |
    ForEach-Object { $_.Matches[0].Groups[1].Value } | Select-Object -First 1
if ("$cachedRelease" -ne $releaseOpt) {
    & cmake "-DBANJO_RENUT_RELEASE_SHADERS=$releaseOpt" $build
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
}
if ($Pgo -and $InPlace) {
    $pgoDir = (Join-Path $root $(if ($OneMode) { 'pgo-onemode' } else { 'pgo-inplace' })).Replace('\', '/')
    $cachedPgoDir = Select-String -Path (Join-Path $build 'CMakeCache.txt') -Pattern '^SASRT_PGO_DIR:PATH=(.*)$' |
        ForEach-Object { $_.Matches[0].Groups[1].Value } | Select-Object -First 1
    if ("$cachedPgoDir" -ne $pgoDir) {
        & cmake "-DSASRT_PGO_DIR=$pgoDir" $build
        if ($LASTEXITCODE) { exit $LASTEXITCODE }
    }
}
Write-Output "sasrt: Switch build in $folder, in place $inplaceOpt, one flush mode $oneModeOpt, LTO $lto, PGO '$Pgo', guard forms $forms, release shaders $releaseOpt (cache before: LTO $cached, PGO '$cachedPgo', guard forms '$cachedForms')"
# The LTO link (SASRT_SWITCH_LTO) runs its LTRANS partitions through `make` when lto-wrapper finds one, in parallel
# (-flto=N); without one it compiles all 512 serially (about 20 minutes here). devkitPro's MSYS2 make, appended to the
# end of PATH so it shadows nothing.
$msysBin = Join-Path $devkitpro 'msys2\usr\bin'
if ((Test-Path (Join-Path $msysBin 'make.exe')) -and -not (Get-Command make -ErrorAction SilentlyContinue)) {
    $env:PATH = "$env:PATH;$msysBin"
}
& cmake --build $build -j $Jobs
exit $LASTEXITCODE
