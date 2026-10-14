# Aplica o Client Patch numa instalação do LandMass.
# Uso: powershell -ExecutionPolicy Bypass -File aplicar.ps1 -Cliente "C:\caminho\LandMass" [-Largura 2560 -Altura 1080]
# O que faz:
#   - Copia D3D8.dll e dgVoodoo.conf (janela sem borda; VRAM 1024).
#   - No system\LandMass.ini: Use16bit=False, Use16bitTextures=False e TextureDetail*=UltraHigh.
#   - Widescreen: partida na resolução da tela (padrão: monitor principal), menus em 4:3 da mesma
#     altura e FOV com a mesma visão vertical do 4:3 (Hor+) no User.ini.
#   - Guarda os arquivos originais como *.antes-patch na primeira aplicação.
param(
    [Parameter(Mandatory)][string]$Cliente,
    [int]$Largura = 0,
    [int]$Altura = 0
)

$ErrorActionPreference = 'Stop'
$sys = Join-Path $Cliente 'system'
$ini = Join-Path $sys 'LandMass.ini'
$user = Join-Path $sys 'User.ini'
$conf = Join-Path $sys 'dgVoodoo.conf'
if (-not (Test-Path $ini)) { throw "LandMass.ini não encontrado em $sys" }

if ($Largura -le 0 -or $Altura -le 0) {
    # Tamanho lógico (com a escala do Windows), o mesmo que o jogo vê por não ser DPI-aware.
    Add-Type -AssemblyName System.Windows.Forms
    $tela = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $Largura = $tela.Width
    $Altura = $tela.Height
}
$menuX = [int][Math]::Round($Altura * 4 / 3)
# Hor+: FOV horizontal que mantém a visão vertical do FOV 90 em 4:3.
$fov = 2 * [Math]::Atan([Math]::Tan([Math]::PI / 4) * ($Largura / $Altura) * 3 / 4) * 180 / [Math]::PI
$fovTxt = $fov.ToString('0.000000', [Globalization.CultureInfo]::InvariantCulture)

foreach ($f in 'LandMass.ini', 'User.ini', 'D3D8.dll', 'dgVoodoo.conf') {
    $p = Join-Path $sys $f
    if ((Test-Path $p) -and -not (Test-Path "$p.antes-patch")) { Copy-Item $p "$p.antes-patch" }
}

Copy-Item (Join-Path $PSScriptRoot 'system\D3D8.dll'), (Join-Path $PSScriptRoot 'system\dgVoodoo.conf') $sys -Force

$t = [IO.File]::ReadAllText($conf)
$t = [regex]::Replace($t, '(?m)^(ExtraEnumeratedResolutions\s*=).*$', "`$1 ${Largura}x${Altura}, ${menuX}x${Altura}")
[IO.File]::WriteAllText($conf, $t)

$t = [IO.File]::ReadAllText($ini)
$t = [regex]::Replace($t, '(?m)^Use16bit=\w+', 'Use16bit=False')
$t = [regex]::Replace($t, '(?m)^Use16bitTextures=\w+', 'Use16bitTextures=False')
$t = [regex]::Replace($t, '(?m)^(TextureDetail\w+)=\w+', '$1=UltraHigh')
$t = [regex]::Replace($t, '(?m)^FullscreenViewportX=\d+', "FullscreenViewportX=$Largura")
$t = [regex]::Replace($t, '(?m)^FullscreenViewportY=\d+', "FullscreenViewportY=$Altura")
$t = [regex]::Replace($t, '(?m)^MenuViewportX=\d+', "MenuViewportX=$menuX")
$t = [regex]::Replace($t, '(?m)^MenuViewportY=\d+', "MenuViewportY=$Altura")
[IO.File]::WriteAllText($ini, $t)

if (Test-Path $user) {
    $t = [IO.File]::ReadAllText($user)
    $t = [regex]::Replace($t, '(?m)^(DesiredFOV|DefaultFOV|FOVAngle)=[\d.]+', "`$1=$fovTxt")
    [IO.File]::WriteAllText($user, $t)
}

Write-Host "Patch aplicado em $sys (partida ${Largura}x${Altura}, menus ${menuX}x${Altura}, FOV $($fov.ToString('0.0', [Globalization.CultureInfo]::InvariantCulture)))"
