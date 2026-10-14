# Notas de engenharia reversa

Fonte da verdade: o cliente em `D:\landmass\cliente\system` (2009). Os servidores em `D:\landmass\servidor` são de 2006-07.

Protocolo consolidado (opcodes C→S/S→C, layouts, pares e lacunas): `tools/re/protocol_full.md`. Pseudocódigo em lote por função: `tools/re/<binário>/all/` (índice `_index.tsv`). Os `.c` ficam só na cópia local (`.gitignore`): são derivados dos binários do jogo e não vão ao repositório público. Para gerar de novo, use o REA ou o Ghidra ([reverse-engineering.md](../../docs/operations/reverse-engineering.md)); as citações de `.c` nos docs apontam para essa cópia.

## Linha de comando do LandMass.exe (`tools/re/LandMass.exe/main_loop.c`)

- `version=<n>` **obrigatório** — sem ele o jogo fecha. Vira `LocalVersion()`.
- `login_num=<guid>` **obrigatório** — sem ele o jogo fecha. Vira `LoginGUID()`. Só o texto antes de `version=` mantém a caixa; depois, vira minúsculas (`main_loop.c` 74-161; [game_server_host.md](game_server_host.md) §2). Ver [docs/protocol/authentication.md](../../docs/protocol/authentication.md).
- `login_server=<ip>:<porta>` — define `MessageServerAddr/Port` (sobrepõe o endereço do Message Server).
- `SERVER` — liga `GIsClient=0` (modo servidor/dedicado).
- Parâmetros são extraídos com `Parse()` e removidos da linha antes do `appInit`.

O Launcher monta o Play com `LandMass.exe %s%s?%s%I64d?%s%s` (três pares chave=valor). A ordem dos pares está em conflito entre fontes: ver [launcher.md](launcher.md).

## Tela cheia x janela (`tools/re/fullscreen.md`)

- Causa estática: `TryRenderDevice` grava `UWV+0xD0` = 1 no cliente, então o SetRes sai em tela cheia. Sem foco, o SetRes não roda e a janela é minimizada.
- Não há chave de ini nem token de linha de comando para janela. Patch de 1 byte proposto em `WinDrv.dll` offset `0x1349D` (não aplicado).

## Widescreen (`tools/re/widescreen.md`)

- A UI posiciona por frações da tela: acompanha qualquer resolução, mas estica em 16:9. Caminho proposto: área 4:3 no Canvas.

## Config do cliente

`system\landmass.wdb` é SQLite comum. Tabelas úteis: `message_server` (idx, name, address, port),
`update_server` (FTP de patch; `landmass-emu launcher` aponta para o servidor, D242), `launcher`, `maps`, `item`, `Item_Equip`, `LevelList`, `msg_error`, ...
Os demais `.wdb` (magic `f7 db 00 00 72 f3 31 01`) são tabelas proprietárias (`Cdb_table`).

## Game server (partida)

- `LM_Engine.dll` tem o motor de servidor: `UServerEngine` (`LM_Engine.ServerEngine`), `UServerLevel`, `CServerRoom`.
- `InitServer(cmdline)` (export, `0x1000C6D0`) lê: `ip=`, `port=`, `mode=`, `ch_ip=`, `ch_port=`, `ch_code=`, `ch_pw=`
  e carrega `ServerMessage.wdb` e `error.wdb`. **Não conecta** no Channel Server (corrigido em 2026-10-13, REA; a conexão, se existir, fica no Tick do singleton de `FUN_1000BA90`). `ch_pw` = `game_server_password` do ChannelServer, 4567.
  Também exporta `ExitServer`, `ChannelServerTick`, `LogoutChannelServer`, `ServerRoom`.
- **Nenhum binário disponível importa `InitServer`**: o executável host do game server dedicado não está
  nem no cliente nem em `servidor/`. `UServerEngine::Init/Tick` só repassam para `UGameEngine`.
- `UServerLevel::NotifyReceivedText` trata o handshake Unreal (`CONNECT`, `NETSPEED`, `LOGIN`, `JOIN`).
  No `LOGIN URL=...?name=...?team=...?key=...`, chama `LoginPlayer(key, name, team)`, que confere o
  jogador contra o `CServerRoom` (dados enviados pelo Channel via `GS_IN_PLAYER`, gravados por `CServerRoom::InPlayer`
  `0x100159A0`). `-1` = recusa. Com a sala vazia, todo LOGIN devolve -1 (ver `tools/re/LM_Engine.dll/LoginPlayer.c`).
  Esse ramo só roda se o nível for `UServerLevel`; no caminho `GameEngine` + `ULevel` não roda (inferido, `tools/re/cmdline.md` §2).
  Ou seja: o LOGIN da partida é validado pela sala que o Channel Server informou.

## Fluxo observado (LandMass.log do cliente)

- Message: `0 → 101 → 111 → 121 → 131`
- Channel: `0 → 101 → 111 → 103×n → 151 → 141 → 121 …`; salas/jogo 3xx/4xx/5xx.

## Protocolo do Message/Channel (`_core_network.dll` + `+server_interface.dll`)

- **Framing (TCP):** `u16 LE tamanho` + corpo (tamanho não inclui os 2 bytes). Máx. 65000. Sem criptografia.
- **Cabeçalho do corpo:** `u16 LE = (opcode << 5) | net_code`. `net_code`: Message=13, Channel=14, Update=12
  (`system\config.ini` do cliente). Resposta do servidor = opcode do pedido + 1.
- Opcodes do cliente → Message: Heartbeat 2 (a cada 10 s), Login 100, Register 110, InMessageServer 120,
  GetChannelServerInfo 130, CreateNickname 150.
- `MS_LOGIN_IN` (44 bytes fixos): `i32 id_len, i32 pw_len, char login_num[33]` (+3 padding), seguido de
  `id` (id_len bytes) e `senha` (pw_len bytes). Lixo de pilha no padding — ignorar.
- O evento local "Recived from Message Server 0" é a própria conexão (`CnetworkClient::OnConnect`), não um pacote.

## Login no cliente (UnrealScript em `XInterface.u`, fonte embutida)

- `login_num=DEVELOPERGUID` (const em `Core.u`) → mostra o formulário e faz `NetLogin(id, senha)`. Precisa vir antes de `version=` (ver linha de `login_num` acima).
- Qualquer outro `login_num` → login automático por token (`NetGuidLogin`), sem formulário.
- Os `.u` trazem o código-fonte UnrealScript; extrair strings UTF-16 é suficiente para ler.
