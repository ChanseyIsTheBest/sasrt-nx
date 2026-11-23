# Rebuilds the native renderer's shader package from everything dumped so far, the way docs/sasrt-notes.md
# ("Shader package") describes, and installs it next to sasrt.exe:
#
#   1. tools/make_vertex_variants.py: containers for the vertex shaders Direct3D rewrote for a vertex declaration
#      (from the discovery dumps, MASSEFFECT_SHADER_DISCOVERY);
#   2. tools/wrap_discovered.py: Direct3D's own shaders, which have no container anywhere;
#   3. tools/build_shader_library.sh: XenosRecomp + DXC + me_pack_shaders over the dumped containers
#      (out\pc\shaders: sasrt_dump_shaders and its memory scan), the extra ones and the two above.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\win\rebuild_shader_package.ps1 [-Log out\shader_build.log]
param([string]$Log = 'out\shader_build.log')
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $root
$raw = @('out/pc/shaders_discovery', 'out/pc/shaders_discovery_tracks') | Where-Object { Test-Path $_ }
"== variants" | Out-File -Encoding utf8 $Log
python tools/make_vertex_variants.py --raw @raw --containers out/pc/shaders --out out/pc/shaders_variants_made 2>&1 |
    Out-File -Append -Encoding utf8 $Log
"== wrapped" | Out-File -Append -Encoding utf8 $Log
python tools/wrap_discovered.py --raw @raw --containers out/pc/shaders out/pc/shaders_extra out/pc/shaders_variants_made/repaired --out out/pc/shaders_wrapped 2>&1 |
    Out-File -Append -Encoding utf8 $Log
"== package" | Out-File -Append -Encoding utf8 $Log
$bash = 'C:\devkitPro\msys2\usr\bin\bash.exe'
& $bash -lc "cd '$($root.Replace('\', '/'))' && bash tools/build_shader_library.sh out/pc/shaders out/pc/shaders_extra out/pc/shaders_variants_made/repaired out/pc/shaders_wrapped" 2>&1 |
    Out-File -Append -Encoding utf8 $Log
if (Test-Path 'out\shaders\sasrt_shaders.mesp') {
    Copy-Item -Force 'out\shaders\sasrt_shaders.mesp', 'out\shaders\sasrt_shaders.mesp.idx' 'out\pc\'
    "installed: $((Get-Item 'out\pc\sasrt_shaders.mesp').Length) bytes" | Out-File -Append -Encoding utf8 $Log
} else {
    'no package built' | Out-File -Append -Encoding utf8 $Log
}
'done' | Out-File -Append -Encoding utf8 $Log
