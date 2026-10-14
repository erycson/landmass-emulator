# Aplica o Client Patch numa instalação do LandMass.
# Uso: powershell -ExecutionPolicy Bypass -File aplicar.ps1 -Cliente "C:\caminho\LandMass"
# O que faz:
#   - Copia D3D8.dll e dgVoodoo.conf (janela sem borda; VRAM 1024).
#   - No system\LandMass.ini: Use16bit=False, Use16bitTextures=False e TextureDetail*=UltraHigh.
#   - Guarda os arquivos originais como *.antes-patch na primeira aplicação.
param([Parameter(Mandatory)][string]$Cliente)

$ErrorActionPreference = 'Stop'
$sys = Join-Path $Cliente 'system'
$ini = Join-Path $sys 'LandMass.ini'
if (-not (Test-Path $ini)) { throw "LandMass.ini não encontrado em $sys" }

foreach ($f in 'LandMass.ini', 'D3D8.dll', 'dgVoodoo.conf') {
    $p = Join-Path $sys $f
    if ((Test-Path $p) -and -not (Test-Path "$p.antes-patch")) { Copy-Item $p "$p.antes-patch" }
}

Copy-Item (Join-Path $PSScriptRoot 'system\D3D8.dll'), (Join-Path $PSScriptRoot 'system\dgVoodoo.conf') $sys -Force

$t = [IO.File]::ReadAllText($ini)
$t = [regex]::Replace($t, '(?m)^Use16bit=\w+', 'Use16bit=False')
$t = [regex]::Replace($t, '(?m)^Use16bitTextures=\w+', 'Use16bitTextures=False')
$t = [regex]::Replace($t, '(?m)^(TextureDetail\w+)=\w+', '$1=UltraHigh')
[IO.File]::WriteAllText($ini, $t)

Write-Host "Patch aplicado em $sys"
