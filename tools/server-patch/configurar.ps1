# Assistente do servidor: pergunta IP, partidas (armas e equipamento), bots e Launcher, grava o
# config.toml na raiz do emulador, monta o servidor de partida (aplicar.ps1) e cria o iniciar-servidor.bat.
# Uso: dois cliques no configurar.bat (ou powershell -ExecutionPolicy Bypass -File configurar.ps1).
# Pode rodar de novo: as respostas atuais aparecem como padrão.
$ErrorActionPreference = 'Stop'
$raiz = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$cfg = Join-Path $raiz 'config.toml'
$segredo = Join-Path $raiz 'data\secrets\match_login_num.txt'

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

# Chave de topo do TOML (antes do [[channels]]); comentada conta como ausente.
function Get-Toml([string]$Chave) {
    $m = [regex]::Match($script:toml, "(?m)^$Chave\s*=\s*(.+?)\s*$")
    if ($m.Success) { $m.Groups[1].Value.Trim('"') } else { '' }
}

# Valor já no formato TOML ('"texto"' ou número); $null comenta a chave.
function Set-Toml([string]$Chave, $Valor) {
    $linha = if ($null -eq $Valor) { "# $Chave =" } else { "$Chave = $Valor" }
    $re = [regex]"(?m)^#?\s*$Chave\s*=.*$"
    if ($re.IsMatch($script:toml)) { $script:toml = $re.Replace($script:toml, $linha, 1) }
    else { $script:toml = $script:toml.Replace('[[channels]]', "$linha`n`n[[channels]]") }
}

function Texto([string]$Valor) { '"' + $Valor.Replace('\', '/') + '"' }

function Emu([string[]]$Argumentos) {
    # O config exige o login_num com match_server_dir; antes de a conta 'servidor' existir, vale um provisório.
    if (Test-Path $segredo) { $env:LANDMASS_MATCH_LOGIN_NUM_FILE = $segredo } else { $env:LANDMASS_MATCH_LOGIN_NUM = 'provisorio' }
    Push-Location $raiz
    try {
        & uv run landmass-emu --config $cfg @Argumentos
        if ($LASTEXITCODE -ne 0) { throw "landmass-emu $($Argumentos -join ' ') falhou ($LASTEXITCODE)" }
    }
    finally {
        Pop-Location
        Remove-Item Env:LANDMASS_MATCH_LOGIN_NUM_FILE, Env:LANDMASS_MATCH_LOGIN_NUM -ErrorAction SilentlyContinue
    }
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw 'uv não encontrado. Instale: https://docs.astral.sh/uv/' }
if (-not (Test-Path $cfg)) { Copy-Item (Join-Path $raiz 'config.example.toml') $cfg }
$toml = [IO.File]::ReadAllText($cfg)

Write-Host "`n=== LandMass: configurar o servidor ($cfg) ===`n"

Write-Host '1. IP público: o endereço que os jogadores usam para chegar a este PC (máximo 15 caracteres).'
$ip = Perguntar 'IP público' (Get-Toml 'public_host')
Set-Toml 'public_host' (Texto $ip)
Set-Toml 'game_host' (Texto $ip)

Write-Host "`n2. Cliente instalado: o servidor lê dele o catálogo, os mapas e a loja (landmass.wdb)."
$atual = Get-Toml 'client_dir'
if ($atual -and -not [IO.Path]::IsPathRooted($atual)) { $atual = [IO.Path]::GetFullPath((Join-Path $raiz $atual)) }
$clienteSys = PedirPasta 'Pasta system do cliente' $atual { param($p) Test-Path (Join-Path $p 'landmass.wdb') } 'landmass.wdb não encontrado nessa pasta.'
Set-Toml 'client_dir' (Texto $clienteSys)

Write-Host "`n3. Partidas com armas e equipamento: cada sala abre um LandMass.exe servidor que dá a cada jogador"
Write-Host '   o morat, as armas e as peças da conta. Sem isso, as partidas não têm o equipamento nem bots.'
$partidas = SimNao 'Ligar as partidas?' $true
$bots = 0
if ($partidas) {
    $atual = Get-Toml 'match_server_dir'
    $padrao = if ($atual) { Split-Path $atual -Parent } else { Join-Path (Split-Path $raiz -Parent) 'servidor-partida' }
    $destino = Perguntar 'Pasta do servidor de partida (cópia do cliente)' $padrao
    $sysPartida = Join-Path $destino 'system'
    if (-not (Test-Path (Join-Path $sysPartida 'LMEmu.u')) -or (SimNao 'Servidor de partida já existe. Atualizar (copiar o LMEmu.u e as rotas de novo)?' $true)) {
        & (Join-Path $PSScriptRoot 'aplicar.ps1') -Cliente (Split-Path $clienteSys -Parent) -Destino $destino
    }
    Set-Toml 'match_server_dir' (Texto $sysPartida)

    Write-Host "`n4. Bots: a partida começa completa com bots até o total pedido. Com 4: você + 3 bots, o jogo"
    Write-Host '   equilibra os times (2 contra 2). Quem entra depois toma a vaga de um bot. O dono da sala usa'
    Write-Host '   /bot add e /bot remove no chat. Desligados: sem bots, sem /bot e sem iniciar sozinho, mesmo'
    Write-Host '   que o jogador altere o cliente.'
    $atual = Get-Toml 'match_bots'
    if (SimNao 'Ligar os bots?' (-not $atual -or [int]$atual -gt 0)) {
        $padrao = if ($atual -and [int]$atual -gt 0) { $atual } else { '4' }
        do { $bots = [int](Perguntar 'Jogadores na partida, humanos e bots (2 a 24)' $padrao) } until ($bots -ge 2 -and $bots -le 24)
    }
}
else {
    Set-Toml 'match_server_dir' $null
}
Set-Toml 'match_bots' $bots

Write-Host "`n5. Launcher.exe: liga um FTP só de leitura (porta 7412) para o Launcher do jogo abrir sem erro."
Write-Host '   Sem ele, os jogadores entram pelo jogar.bat. Com ele, o landmass.wdb do cliente é apontado para'
Write-Host '   este servidor: distribua essa pasta do cliente aos jogadores.'
$launcher = SimNao 'Ligar o Launcher?' ([bool](Get-Toml 'update_port'))
Set-Toml 'update_port' $(if ($launcher) { 7412 } else { $null })

[IO.File]::WriteAllText($cfg, $toml)
Write-Host "`nconfig.toml gravado."

# login_num do servidor de partida: token de uma conta só dele, guardado fora do config (segredo).
if ($partidas -and -not (Test-Path $segredo)) {
    $pasta = Split-Path $segredo -Parent
    New-Item -ItemType Directory -Force $pasta | Out-Null
    try { Emu @('account', 'create', '--user', 'servidor', '--nickname', 'Servidor', '--client-dir', $pasta) }
    catch { Emu @('account', 'token', '--user', 'servidor', '--client-dir', $pasta) }
    $bat = Join-Path $pasta 'jogar_servidor.bat'
    $token = [regex]::Match([IO.File]::ReadAllText($bat), 'login_num=([0-9a-f]+)').Groups[1].Value
    if (-not $token) { throw "token não encontrado em $bat" }
    [IO.File]::WriteAllText($segredo, $token)
    Remove-Item $bat
    Write-Host "Conta 'servidor' do servidor de partida criada; token em $segredo"
}

if ($launcher) { Emu @('launcher') }

$linhas = @('@echo off', 'cd /d "%~dp0"')
if ($partidas) { $linhas += 'set LANDMASS_MATCH_LOGIN_NUM_FILE=data\secrets\match_login_num.txt' }
$linhas += 'uv run landmass-emu --config config.toml serve', 'pause'
[IO.File]::WriteAllText((Join-Path $raiz 'iniciar-servidor.bat'), ($linhas -join "`r`n") + "`r`n", [Text.Encoding]::ASCII)

Write-Host "`nPronto. Para subir: iniciar-servidor.bat (na raiz do emulador)."
$portas = 'TCP 7313 e 7314'
if ($partidas) { $portas += '; UDP 7800 a 7899' }
# O FTP passivo abre porta aleatória: liberar o python do emulador cobre todas.
if ($launcher) { $portas += '; TCP 7412 e o python.exe do .venv (portas passivas do FTP)' }
Write-Host "Libere no firewall: $portas."
Write-Host 'Contas: uv run landmass-emu account create --user <usuário> --nickname <apelido> --password <senha>'
