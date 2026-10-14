# Monta o servidor de partida do LandMass a partir de uma instalação do cliente.
# Uso: powershell -ExecutionPolicy Bypass -File aplicar.ps1 -Cliente "C:\LandMass" -Destino "D:\servidor-partida"
#   -Destino pode ser a própria pasta do cliente (patch no lugar) ou uma pasta nova (cópia).
# O que faz:
#   1. Copia o cliente para -Destino, sem o que o servidor não usa (música, capturas, logs, launcher,
#      patcher, dgVoodoo e backups).
#   2. Patch de 2 bytes em system\Core.dll: o -server chega ao motor (sem janela nem renderização).
#   3. Patch de 1 byte em system\LandMass.exe: cada partida roda no próprio processo e grava o próprio log.
#   4. Copia o LMEmu.u (pacote só de servidor do emulador) para system\, e o LMEmuRoutes.ini (rotas
#      dos bots) se ele estiver em tools\server-patch\system\.
# Cada patch confere os bytes originais antes de gravar e guarda o original como *.orig.
param(
    [Parameter(Mandatory)][string]$Cliente,
    [Parameter(Mandatory)][string]$Destino
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path (Join-Path $Cliente 'system\LandMass.exe'))) { throw "LandMass.exe não encontrado em $Cliente\system" }

$origem = (Resolve-Path $Cliente).Path
New-Item -ItemType Directory -Force $Destino | Out-Null
$destino = (Resolve-Path $Destino).Path

if ($origem -ne $destino) {
    robocopy $origem $destino /E /NFL /NDL /NJH /NJS /NP `
        /XD music ScreenShots `
        /XF *.log *.dmp *.bak* *.antes-patch Launcher.exe Patcher.exe end.exe autorun.inf D3D8.dll dgVoodoo.conf Running.ini | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy falhou ($LASTEXITCODE)" }
}

function Set-Bytes([string]$Arquivo, [int]$Offset, [byte[]]$Antes, [byte[]]$Depois) {
    $b = [IO.File]::ReadAllBytes($Arquivo)
    $atual = $b[$Offset..($Offset + $Antes.Length - 1)]
    if (-not (Compare-Object $atual $Depois -SyncWindow 0)) { Write-Host "$Arquivo já tem o patch"; return }
    if (Compare-Object $atual $Antes -SyncWindow 0) {
        throw ("{0}: bytes em 0x{1:X} são {2}, esperado {3}. Versão do cliente diferente?" -f $Arquivo, $Offset, ($atual | % { $_.ToString('X2') }) -join ' ', ($Antes | % { $_.ToString('X2') }) -join ' ')
    }
    if (-not (Test-Path "$Arquivo.orig")) { Copy-Item $Arquivo "$Arquivo.orig" }
    for ($i = 0; $i -lt $Depois.Length; $i++) { $b[$Offset + $i] = $Depois[$i] }
    [IO.File]::WriteAllBytes($Arquivo, $b)
    Write-Host ("{0}: patch em 0x{1:X}" -f $Arquivo, $Offset)
}

$sys = Join-Path $destino 'system'
# appInit: o je que descarta a linha de comando vira nop nop.
Set-Bytes (Join-Path $sys 'Core.dll') 0x3F9C6 ([byte[]](0x74, 0x0E)) ([byte[]](0x90, 0x90))
# Classe de janela "WLog" vira "XLog": a segunda instância não repassa a linha de comando à primeira.
Set-Bytes (Join-Path $sys 'LandMass.exe') 0x209E4 ([byte[]](0x57)) ([byte[]](0x58))

Copy-Item (Join-Path $PSScriptRoot 'system\LMEmu.u') $sys -Force
# Rotas dos bots (gravadas pelo tools/routes/rotas.py a partir do LMEmuBake): só se o arquivo existir.
Get-ChildItem (Join-Path $PSScriptRoot 'system') -Filter 'LMEmuRoutes.ini' | Copy-Item -Destination $sys -Force
Write-Host "Servidor de partida pronto em $destino. No emulador: match_server_dir = `"$sys`""
