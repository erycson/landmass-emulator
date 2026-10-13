# Notas de engenharia reversa

Fonte da verdade: o cliente em `D:\landmass\cliente\system` (2009). Os servidores em `D:\landmass\servidor` são de 2006-07.

## Linha de comando do LandMass.exe (`re/LandMass.exe/main_loop.c`)

- `version=<n>` **obrigatório** — sem ele o jogo fecha. Vira `LocalVersion()`.
- `login_num=<guid>` **obrigatório** — sem ele o jogo fecha. Vira `LoginGUID()`.
- `login_server=<ip>:<porta>` — define `MessageServerAddr/Port` (sobrepõe o endereço do Message Server).
- `SERVER` — liga `GIsClient=0` (modo servidor/dedicado).
- Parâmetros são extraídos com `Parse()` e removidos da linha antes do `appInit`.

O Launcher monta: `LandMass.exe %s%s?%s%I64d?%s%s` com `login_server=`, `version=`, `login_num=`.

## Config do cliente

`system\landmass.wdb` é SQLite comum. Tabelas úteis: `message_server` (idx, name, address, port),
`update_server` (FTP de patch), `launcher`, `maps`, `item`, `Item_Equip`, `LevelList`, `msg_error`, ...
Os demais `.wdb` (magic `f7 db 00 00 72 f3 31 01`) são tabelas proprietárias (`Cdb_table`).

## Game server (partida)

- `LM_Engine.dll` tem o motor de servidor: `UServerEngine` (`LM_Engine.ServerEngine`), `UServerLevel`, `CServerRoom`.
- `InitServer(cmdline)` (export) lê: `ip=`, `port=`, `mode=`, `ch_ip=`, `ch_port=`, `ch_code=`, `ch_pw=`
  e conecta no Channel Server (`ch_pw` = `game_server_password` do ChannelServer, 4567).
  Também exporta `ExitServer`, `ChannelServerTick`, `LogoutChannelServer`, `ServerRoom`.
- **Nenhum binário disponível importa `InitServer`**: o executável host do game server dedicado não está
  nem no cliente nem em `servidor/`. `UServerEngine::Init/Tick` só repassam para `UGameEngine`.
- `UServerLevel::NotifyReceivedText` trata o handshake Unreal (`CONNECT`, `NETSPEED`, `LOGIN`, `JOIN`).
  No `LOGIN URL=...?name=...?team=...?key=...`, chama `LoginPlayer(key, name, team)`, que confere o
  jogador contra o `CServerRoom` (dados enviados pelo Channel via `GS_IN_PLAYER`). `-1` = recusa.
  Ou seja: o LOGIN da partida é validado pela sala que o Channel Server informou.

## Fluxo observado (LandMass.log do cliente)

- Message: `0 → 101 → 111 → 121 → 131`
- Channel: `0 → 101 → 111 → 103×n → 151 → 141 → 121 …`; salas/jogo 3xx/4xx/5xx.
