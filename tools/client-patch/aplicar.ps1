# Aplica o Client Patch numa instalação do LandMass. Para perguntas passo a passo, use configurar.bat.
# Uso: powershell -ExecutionPolicy Bypass -File aplicar.ps1 -Cliente "C:\LandMass" [-Servidor 203.0.113.10] [-Memoria4GB] [-IniciarSozinho] [-DgVoodoo "C:\Downloads\dgVoodoo2_87_5" [-Largura 2560 -Altura 1080]]
# O que faz (cada parte só com a opção dela):
#   -Servidor IP[:porta]: grava system\jogar.bat (tela de login do jogo) e troca o login_server dos jogar_*.bat.
#   -Memoria4GB: liga LARGE_ADDRESS_AWARE no LandMass.exe (até 4 GB de memória em Windows 64 bits).
#   -IniciarSozinho: patch de 3 bytes no XInterface.u (botão de iniciar sem outro jogador pronto).
#   -DgVoodoo: copia o D3D8.dll do dgVoodoo2 (MS\x86 da pasta extraída, ou a pasta que já tem o D3D8.dll)
#     e o dgVoodoo.conf; no LandMass.ini, cores de 32 bits e texturas UltraHigh; widescreen com partida na
#     resolução da tela, menus em 4:3 da mesma altura e FOV Hor+ no User.ini.
#   Guarda os originais como *.orig (binários) ou *.antes-patch (configuração) na primeira aplicação.
param(
    [Parameter(Mandatory)][string]$Cliente,
    [string]$Servidor = '',
    [switch]$Memoria4GB,
    [switch]$IniciarSozinho,
    [string]$DgVoodoo = '',
    [int]$Largura = 0,
    [int]$Altura = 0
)

$ErrorActionPreference = 'Stop'
$sys = Join-Path $Cliente 'system'
if (-not (Test-Path (Join-Path $sys 'LandMass.exe'))) { throw "LandMass.exe não encontrado em $sys" }
$VERSAO = 1245776779

function Backup([string]$Arquivo, [string]$Sufixo) {
    if ((Test-Path $Arquivo) -and -not (Test-Path "$Arquivo$Sufixo")) { Copy-Item $Arquivo "$Arquivo$Sufixo" }
}

function Set-Bytes([string]$Arquivo, [int]$Offset, [byte[]]$Antes, [byte[]]$Depois) {
    $b = [IO.File]::ReadAllBytes($Arquivo)
    $atual = $b[$Offset..($Offset + $Antes.Length - 1)]
    if (-not (Compare-Object $atual $Depois -SyncWindow 0)) { Write-Host "$Arquivo já tem o patch"; return }
    if (Compare-Object $atual $Antes -SyncWindow 0) {
        throw ("{0}: bytes em 0x{1:X} diferentes do esperado. Versão do cliente diferente?" -f $Arquivo, $Offset)
    }
    Backup $Arquivo '.orig'
    for ($i = 0; $i -lt $Depois.Length; $i++) { $b[$Offset + $i] = $Depois[$i] }
    [IO.File]::WriteAllBytes($Arquivo, $b)
    Write-Host ("{0}: patch em 0x{1:X}" -f $Arquivo, $Offset)
}

if ($Servidor) {
    if ($Servidor -notmatch ':') { $Servidor = "${Servidor}:7313" }
    # login_num=DEVELOPERGUID antes de version= abre a tela de usuário e senha do jogo (D240).
    $bat = "@echo off`r`ncd /d `"%~dp0`"`r`nstart `"`" LandMass.exe login_num=DEVELOPERGUID?version=${VERSAO}?login_server=$Servidor`r`n"
    [IO.File]::WriteAllText((Join-Path $sys 'jogar.bat'), $bat, [Text.Encoding]::ASCII)
    Get-ChildItem $sys -Filter 'jogar_*.bat' | ForEach-Object {
        $t = [IO.File]::ReadAllText($_.FullName)
        [IO.File]::WriteAllText($_.FullName, [regex]::Replace($t, 'login_server=[^?\s]+', "login_server=$Servidor"), [Text.Encoding]::ASCII)
    }
    Write-Host "Servidor $Servidor gravado em system\jogar.bat"
}

if ($Memoria4GB) {
    $exe = Join-Path $sys 'LandMass.exe'
    $b = [IO.File]::ReadAllBytes($exe)
    $pe = [BitConverter]::ToInt32($b, 0x3C)
    $off = $pe + 4 + 18  # Characteristics do cabeçalho COFF
    if ($b[$off] -band 0x20) { Write-Host "$exe já tem 4GB" }
    else {
        Backup $exe '.orig'
        $b[$off] = $b[$off] -bor 0x20
        [IO.File]::WriteAllBytes($exe, $b)
        Write-Host "${exe}: 4GB ligado"
    }
}

# LM_RoomPlayerListPanel.IsReadyToStart: o primeiro "07 52 00" (JumpIfNot) vira "04 27 0B"
# (return true; nothing). O dono inicia sem outro jogador pronto; o servidor só aceita com bots ligados (D224).
if ($IniciarSozinho) { Set-Bytes (Join-Path $sys 'XInterface.u') 0xE70BC ([byte[]](0x07, 0x52, 0x00, 0x84)) ([byte[]](0x04, 0x27, 0x0B, 0x84)) }

if (-not $DgVoodoo) { return }

$ini = Join-Path $sys 'LandMass.ini'
$user = Join-Path $sys 'User.ini'
$conf = Join-Path $sys 'dgVoodoo.conf'
if (-not (Test-Path $ini)) { throw "LandMass.ini não encontrado em $sys" }
# O dgVoodoo2 não vem no repositório: pasta extraída do zip oficial, ou uma pasta que já tem o D3D8.dll.
$dll = Join-Path $DgVoodoo 'MS\x86\D3D8.dll'
if (-not (Test-Path $dll)) { $dll = Join-Path $DgVoodoo 'D3D8.dll' }
if (-not (Test-Path $dll)) { throw "D3D8.dll do dgVoodoo2 não encontrado em $DgVoodoo. Baixe o dgVoodoo2 e passe a pasta extraída (veja o README.md)." }

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

foreach ($f in 'LandMass.ini', 'User.ini', 'D3D8.dll', 'dgVoodoo.conf') { Backup (Join-Path $sys $f) '.antes-patch' }

if ((Resolve-Path $dll).Path -ne (Join-Path (Resolve-Path $sys).Path 'D3D8.dll')) { Copy-Item $dll $sys -Force }
Copy-Item (Join-Path $PSScriptRoot 'system\dgVoodoo.conf') $sys -Force

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

Write-Host "Vídeo aplicado em $sys (partida ${Largura}x${Altura}, menus ${menuX}x${Altura}, FOV $($fov.ToString('0.0', [Globalization.CultureInfo]::InvariantCulture)))"
