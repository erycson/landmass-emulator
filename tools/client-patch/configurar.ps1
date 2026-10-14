# Assistente do Client Patch: faz as perguntas e chama o aplicar.ps1 com as opções escolhidas.
# Uso: dois cliques no configurar.bat (ou powershell -ExecutionPolicy Bypass -File configurar.ps1).
$ErrorActionPreference = 'Stop'

function Perguntar([string]$Texto, [string]$Padrao) {
    $r = Read-Host "$Texto [$Padrao]"
    if ($r) { $r.Trim().Trim('"') } else { $Padrao }
}

function SimNao([string]$Texto, [bool]$Padrao) {
    $op = if ($Padrao) { 'S/n' } else { 's/N' }
    while ($true) {
        $r = (Read-Host "$Texto ($op)").Trim().ToLower()
        if (-not $r) { return $Padrao }
        if ($r -in 's', 'sim', 'y') { return $true }
        if ($r -in 'n', 'nao', 'não') { return $false }
    }
}

function PedirPasta([string]$Texto, [string]$Padrao, [scriptblock]$Valida, [string]$Erro) {
    while ($true) {
        $p = Perguntar $Texto $Padrao
        if ($p -and (& $Valida $p)) { return $p }
        Write-Host $Erro
    }
}

Write-Host "`n=== LandMass: configurar o cliente ===`n"

$padrao = if (Test-Path 'C:\LandMass\system\LandMass.exe') { 'C:\LandMass' } else { '' }
$opcoes = @{
    Cliente = PedirPasta 'Pasta do jogo (a que tem a pasta system)' $padrao { param($p) Test-Path (Join-Path $p 'system\LandMass.exe') } 'LandMass.exe não encontrado em <pasta>\system.'
}

Write-Host "`n1. Servidor: o endereço que o administrador passou (IP ou IP:porta)."
$ip = Perguntar 'IP do servidor (Enter para não mudar)' ''
if ($ip) { $opcoes.Servidor = $ip }

Write-Host "`n2. Armas e bots: vêm do servidor. Não há nada a mudar no cliente."

Write-Host "`n3. Memória: o jogo passa a usar até 4 GB (evita travar sem memória em mapas grandes)."
if (SimNao 'Ativar 4GB?' $true) { $opcoes.Memoria4GB = $true }

Write-Host "`n4. Jogar sozinho contra bots: libera o botão Iniciar sem outro jogador na sala."
Write-Host '   Só funciona se o servidor tiver os bots ligados; com 2 ou mais pessoas na sala não precisa.'
if (SimNao 'Liberar o botão Iniciar sozinho?' $false) { $opcoes.IniciarSozinho = $true }

Write-Host "`n5. Vídeo (Windows 10/11): dgVoodoo2, widescreen na resolução da tela e texturas no máximo."
Write-Host '   Baixe em https://github.com/dege-diosg/dgVoodoo2/releases e extraia o zip numa pasta.'
if (SimNao 'Configurar o vídeo?' $false) {
    $opcoes.DgVoodoo = PedirPasta 'Pasta extraída do dgVoodoo2' '' { param($p) (Test-Path (Join-Path $p 'MS\x86\D3D8.dll')) -or (Test-Path (Join-Path $p 'D3D8.dll')) } 'D3D8.dll não encontrado nessa pasta (procuro em MS\x86).'
}

Write-Host ''
& (Join-Path $PSScriptRoot 'aplicar.ps1') @opcoes
Write-Host "`nPronto."
if ($opcoes.Servidor) { Write-Host 'Para jogar: system\jogar.bat (entra com usuário e senha).' }
