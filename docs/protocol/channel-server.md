# Channel Server (TCP 7314, `net_code` 14)

Implementação: `protocol/channel.py` (codec), `domain/lobby.py` (presença), `domain/rooms.py` (salas em memória), `handlers/channel/` (comportamento; salas em `rooms.py`), `ports/options.py` (opções, gravadas pelo 544), `net/server.py` (transporte). Evidências e layouts completos: [`../../re/channel_server.md`](../../re/channel_server.md) e [`../../re/rooms.md`](../../re/rooms.md).

Este documento cobre o que o emulador implementa: marco 2 (entrada, lobby, chat), F1 (opções, 544), marco 3 (salas: criar, entrar, sair, slots, pronto, início, expulsar) e F2 e F3 (tutorial, saldos e exp). Os demais opcodes da tabela completa seguem como não tratados: logados com hexdump e ignorados, sem derrubar a conexão.

## Grupos de opcodes

| Faixa | Assunto | Estado |
|-------|---------|--------|
| 1xx | Entrada no canal, lobby, lista de jogadores e de salas | marco 2 (100, 120, 122); lista de salas no 141 pelo marco 3 |
| 2 | Heartbeat | marco 2 |
| 2xx | Chat | marco 2 (240/241); escopo da sala pelo marco 3 |
| 3xx | Salas: criar, entrar, sair, mudança de dono e remoção | marco 3 (301 a 342) |
| 4xx | Sala: pronto, início, slot | marco 3 (401 a 421) |
| 5xx | Itens, loja, hangar, presentes | marco 5 |
| 7xx | Expulsar jogador da sala | marco 3 (700/701) |
| `GS_*` | Game Server Host ↔ Channel (autenticado por `ch_pw`) | marco 4 |

Sequência de entrada pelo cliente, conforme `re/NOTES.md`: `101 → 111 → 151 → 141 → 121`. O emulador mantém a ordem.

## Fluxo implementado

| Pedido (C→S) | Resposta (S→C) | Efeito |
|--------------|----------------|--------|
| `2` heartbeat | nenhuma | Conta como tráfego. O servidor não responde. |
| `100` InChannelServer, `char session_key[33]` | `101` (176 bytes, `result` @0xa8, progressão do próprio jogador), `111` (`count` 1) e os saldos `900` e `902` (F3) | Resolve a chave de sessão emitida no `111` do Message. Chave recusada (zerada, desconhecida, expirada ou de conta reemitida): `101` com `result` -160 e sem entrada no lobby. |
| `120` InChannel, corpo ignorado | `151` (todos os jogadores do lobby, o próprio incluído, com nick), `141` (salas do canal), `121` (próprio registro) | Entra no lobby. Os demais jogadores recebem `121` com o registro do recém-chegado. |
| `122` OutChannel | `123` (próprio id) | Sai da sala, se estiver em uma (322, e 332 ou 342), e do lobby. Os demais jogadores recebem `123`. |
| `240` SendMsg, `u8 msg_type`, `u8 len`, texto | `241` a todos do lobby, remetente incluído; se o remetente está em sala, só aos membros da sala | Chat. Sem login ou fora do lobby: ignorado. |
| `600` TutorialClear, `u8 passo` (0 a 2) | `601` (máscara e LD) | Liga o bit do passo em `accounts.tutorial_clear` com um `UPDATE` (pedidos concorrentes não perdem bit). Passo fora da faixa: `ValueError` logado, nada gravado, conexão mantida. Sem login: ignorado. |
| `301` CreateRoom, 74 bytes | `302` ao lobby (registro da sala), `312` ao lobby (criador no slot 0), `314` e `317` ao criador | Cria a sala em memória; o criador é o dono e fica pronto. Nome curto: envelope `54` com `302` e código 211000202. Outro erro: código 211000201. |
| `311` InRoom, 20 bytes | `312` ao lobby; `314` e `317` ao entrante | Entra no primeiro slot livre. Recusa: `312` com código negativo só ao entrante, com 1001 (sala não existe), 1202 (cheia), 1701 (senha) ou 200 (partida já iniciada). Estar em sala já: sem resposta. |
| `321` OutRoom, vazio | `322` ao lobby; `332` se trocou o dono; `342` se a sala esvaziou | Sai da sala. |
| `401` ReadyGame, `u8 morats`, de jogador não dono | `402` aos membros da sala | Alterna o estado de pronto. |
| `401` ReadyGame, do dono | `412` ao lobby e `403` aos membros da sala (endereço e porta da partida) | Inicia a partida se houver outro jogador e todos os outros estiverem prontos. Senão: envelope `54` com `404` e código 241002702. |
| `420` ChangeRoomSlot, `u8 slot` | `421` aos membros da sala | Troca de slot. Slot ocupado ou inválido: sem resposta. |
| `700` ExpelPlayer, `i32 position` | `322` ao lobby e `701` (0) ao dono | Só o dono expulsa. Recusa: envelope `54` com `701` e código 241000302 (não é dono) ou 241001202 (alvo fora da sala). |
| `544` SaveOption, 37 bytes | nenhuma | Grava as 37 opções da conta logada em `account_options`. Sem login: ignorado. Payload curto: logado e ignorado. |
| (queda da conexão) | `123` aos demais | Saída implícita; antes, sai da sala como em `321`. |
| servidor, a cada 10 s | `2` heartbeat | O cliente responde com `2`; o servidor ignora essa resposta. |

Opcodes sem handler (inclusive 67, 64, 66, 464, 545, 546): logados com hexdump e ignorados. Pedido com payload inválido: logado sem hexdump e ignorado.

## Identificação do cliente

O cliente não envia nickname nem token ao entrar no canal. Envia no `100` a chave de sessão que recebeu no `111` do Message (`char[33]` @0x25; [message-server.md](message-server.md)). O canal resolve a chave com `SessionKeyRegistry` (`ports/session_keys.py`, implementado em `domain/session_keys.py`) e usa `account.id` como `client_guid` de toda a sessão. O canal não acessa o banco. Regras da chave em [authentication.md](authentication.md).

Evidências: o corpo do `100` tem 33 bytes (teste com o cliente real; `u8 @32` é o NUL do `char[33]`). O `ChannelServer.exe` original loga `in->guid=%s` logo após `InChannelServer(`. Inferido: o `num` de `InChannelServer(int num)` do UnrealScript não viaja no pacote.

## Opcodes

| Opcode | Direção | Nome (`CsOp`) | Corpo | Estado |
|-------:|---------|---------------|-------|--------|
| 2 | C↔S | `HEARTBEAT` | vazio | implementado |
| 54 | S→C | `ERROR` (envelope) | 8 bytes: opcode real e código | implementado |
| 100 | C→S | `IN_CHANNEL_SERVER` | `char session_key[33]` | implementado |
| 101 | S→C | `IN_CHANNEL_SERVER_OUT` | 176 bytes | implementado (progressão de `@0x28` a `@0x4C`, F2 e F3; ver Layouts) |
| 111 | S→C | `CHANNEL_INFO_OUT` | `u8 count` = 1 | implementado (shortcut) |
| 120 | C→S | `IN_CHANNEL` | `u32 num` ou vazio | implementado (`num` ignorado) |
| 121 | S→C | `IN_CHANNEL_OUT` | entrada de jogador, 40 bytes | implementado (`total_exp` = exp do banco, F3: o 121 sobrescreve o nó do próprio jogador) |
| 122 | C→S | `OUT_CHANNEL` | vazio | implementado |
| 123 | S→C | `OUT_CHANNEL_OUT` | 8 bytes | implementado |
| 141 | S→C | `CHANNEL_ROOM_INFO_OUT` | `u16 count` + registros de sala de 68 bytes | implementado |
| 151 | S→C | `CHANNEL_PLAYER_INFO_OUT` | `u16 count` + entradas de 40 bytes, todos os jogadores do lobby | implementado |
| 545 | C→S | `REFRESH_ROOM_LIST` | 44 bytes: `channel`, `u8 count` (máximo 9), `i32 room_guid[count]` | implementado |
| 546 | C→S | `REFRESH_PLAYER_LIST` | 64 bytes: `channel`, `u8 count` (máximo 14), `i32 client_guid[count]` | implementado |
| 547 | S→C | `REFRESH_ROOM_LIST_OUT` | `u8 count` + entradas de 16 bytes | implementado (shortcut: `map_num`) |
| 548 | S→C | `REFRESH_PLAYER_LIST_OUT` | `u8 count` + entradas de 20 bytes | implementado (resposta só a quem está no lobby) |
| 240 | C→S | `SEND_MESSAGE` | `u8 msg_type`, `u8 len`, texto | implementado |
| 241 | S→C | `SEND_MESSAGE_OUT` | 8 bytes + texto | implementado |
| 600 | C→S | `TUTORIAL_CLEAR` | `u8 passo` (0 a 2) | implementado (F2): liga o bit `1 << passo`; passo fora da faixa é logado e nada é gravado |
| 601 | S→C | `TUTORIAL_CLEAR_OUT` | `i32` máscara @0, `i32` LD @4 | implementado (F2); o LD vai no @4 porque o cliente o grava em `iPoint` |
| 900 | S→C (push) | `CHARGE_CASH_OUT` | `i32` Cash | implementado (F3): enviado depois do 111 no login |
| 902 | S→C (push) | `CHARGE_POINT_OUT` | `i32` LD | implementado (F3): enviado depois do 111 no login; bloco misto no dispatcher (shortcut) |
| 301 | C→S | `CREATE_ROOM` | 74 bytes | implementado (shortcut) |
| 302 | S→C | `CREATE_ROOM_OUT` | registro de sala, 612 bytes | implementado (shortcut) |
| 311 | C→S | `IN_ROOM` | 20 bytes | implementado (shortcut) |
| 312 | S→C | `IN_ROOM_OUT` | 12 bytes (sucesso) ou 18 bytes (erro) | implementado (shortcut) |
| 314 | S→C | `ROOM_INFO_OUT` | 56 bytes | implementado |
| 317 | S→C | `ROOM_PLAYER_INFO_OUT` | `u8 count` + entradas de 48 bytes | implementado |
| 321 | C→S | `OUT_ROOM` | vazio | implementado |
| 322 | S→C | `OUT_ROOM_OUT` | 8 bytes | implementado |
| 332 | S→C | `CHANGE_ROOM_MASTER_OUT` | 8 bytes | implementado (shortcut: layout inferido) |
| 342 | S→C | `REMOVE_ROOM_OUT` | 4 bytes | implementado (shortcut: gap no RE) |
| 401 | C→S | `READY_GAME` | `u8 morats` | implementado |
| 402 | S→C | `READY_GAME_OUT` | 12 bytes | implementado |
| 403 | S→C | `START_GAME_OUT` | 18 bytes | implementado (shortcut) |
| 404 | S→C | `READY_GAME_ERROR` (dentro do envelope 54) | sem corpo próprio | implementado |
| 412 | S→C | `CHANGE_ROOM_PROPERTY_OUT` | 16 bytes | implementado |
| 420 | C→S | `CHANGE_ROOM_SLOT` | `u8 slot` | implementado |
| 421 | S→C | `CHANGE_ROOM_SLOT_OUT` | 8 bytes | implementado |
| 700 | C→S | `EXPEL_PLAYER` | `i32 position` | implementado (shortcut) |
| 701 | S→C | `EXPEL_PLAYER_OUT` | `i32` 0, ou envelope de erro | implementado |
| 64, 66, 67, 464 | C→S | pedidos de lista | — | não tratados |

## Salas

Estado em `domain/rooms.py`, só em memória (D12, D24). `handlers/channel/rooms.py` monta as respostas. Regras:

- **Criar.** O criador entra no slot 0, já pronto, e é o dono. Nome de 3 a 31 bytes; senha de até 15 bytes (shortcut). Valores numéricos fora da faixa são limitados e logados, não recusados: `scale`, `game_mode`, `team_count` e `limit_time` em 0..255; `map_num` e `limit_score` em 0..32767; `max_player` em 1..70.
- **Entrar.** A sala precisa existir, não ter começado, ter slot livre e, se tiver senha, a senha certa. Entra no primeiro slot livre. Quem entra não sai do lobby: continua recebendo a lista e o chat do canal.
- **Pronto.** Jogador que não é dono alterna o estado com `401`. O dono não marca pronto: o `401` dele inicia a partida.
- **Iniciar.** Só o dono. Exige ao menos um outro membro e todos os outros prontos. A sala passa a jogando (estado 2) e não aceita novas entradas. O `403` leva `LANDMASS_GAME_HOST` e `LANDMASS_GAME_PORT` ([05-configuration](../architecture/05-configuration.md)).
- **Sair.** Se o dono sai e ainda há membros, o dono passa ao primeiro membro na ordem de entrada (`332`). Sala sem membros é removida (`342`).
- **Expulsar.** Só o dono. O expulso sai da sala (`322`).

Escopo da difusão:

| Opcode | Vai a | Motivo |
|--------|-------|--------|
| 302 | lobby | toda a lista de salas recebe a nova sala |
| 312 (sucesso) | lobby | o canal soma o jogador na sala |
| 322 | lobby | saída ou expulsão |
| 332 | lobby | troca de dono |
| 342 | lobby | sala removida |
| 412 | lobby | estado da sala (jogando) |
| 402, 403, 421 | membros da sala | pronto, início, slot |
| 314, 317 | só quem criou ou entrou | detalhe da sala e lista de jogadores |
| 312 (erro), 54 com 404 ou 701 | só quem pediu | recusa |

Confirmado pela análise de `re/rooms.md` (§ de escopo); o cliente real confirma ou corrige.

## Layouts

Offsets no corpo, depois do cabeçalho `u16`. Campo sem nome no RE recebe o nome do offset.

**100 IN_CHANNEL_SERVER (C→S), 33 bytes**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `char[33]` | `session_key`, NUL-terminado: 32 hexadecimais minúsculos. Mínimo 33 bytes; o emulador ignora bytes extras. |

**101 IN_CHANNEL_SERVER_OUT (S→C), 176 bytes**

| Offset | Tipo | Campo | Valor |
|-------:|------|-------|-------|
| 0x00..0x27 | `byte[40]` | registro do próprio jogador (não decodificado) | zeros |
| 0x28 | `i32` | `iTutorialClear` (máscara, nó+0x38) | `accounts.tutorial_clear` (F2) |
| 0x2C | `i32` | `iTotalExp` (nó+0x3c; patente é derivada no cliente) | `accounts.total_exp` (F3) |
| 0x30..0x47 | `byte[24]` | não decodificado | zeros |
| 0x48 | `i32` | `iCash` (nó+0x58) | `accounts.cash` (F3) |
| 0x4C | `i32` | `iPoint`, LD (nó+0x5c) | `accounts.ld` (F3) |
| 0x50..0x8F | `byte[64]` | não decodificado | zeros |
| 0x90 | `i32` | id do jogador; lido como `DAT_1005ada0` | `account.id` |
| 0x94..0x9F | `byte[12]` | não decodificado | zeros |
| 0xA0 | `i32` | id do jogador (chave do nó, eco de 0x90) | `account.id` |
| 0xA4..0xA7 | `byte[4]` | não decodificado | zeros |
| 0xA8 | `i32` | `result` (0 = ok) | 0 ou -160 |
| 0xAC | `i32` | `location` (lido como `_DAT_1005ae08`; semântica não confirmada) | 0 |

**111 CHANNEL_INFO_OUT (S→C), 1 byte**

| Offset | Tipo | Campo | Valor |
|-------:|------|-------|-------|
| 0x00 | `u8` | `count` | 1 (entrada sem corpo) |

**Entrada de jogador (121 e 151), 40 bytes**

Em 121 o corpo é a entrada em @0. Em 151 as entradas começam em @2, com stride de 40 bytes. O cliente lê até @0x24; os bytes @0x1B e @0x25..0x27 não são lidos.

| Offset na entrada | Tipo | Campo (nó do cliente, `re/layouts_f0.md` §1.2) |
|------------------:|------|-----------------------------------------------|
| 0x00 | `i32` | `client_guid` (+0xA0, chave) |
| 0x04 | `i32` | `total_exp` (+0x3C) |
| 0x08 | `char[16]` | `nick`, ANSI, NUL-terminado (+0x10..0x1F): máximo 15 bytes |
| 0x18 | `u8` | byte após o nick (+0x20), zero |
| 0x19 | `u8` | `vehicle_licence` (+0x23) |
| 0x1A | `u8` | `access` (+0x21) |
| 0x1B | `byte` | padding |
| 0x1C | `i32` | `clan` (+0x28) |
| 0x20 | `i32` | `clan_mark` (+0x2C) |
| 0x24 | `u8` | `nest` (+0x30) |
| 0x25..0x27 | `byte[3]` | padding |

`total_exp`, clã, marca e nest vão zerados até o marco 5 (persistência). O nick vem de `account.nickname`.

**151 CHANNEL_PLAYER_INFO_OUT (S→C)**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `u16` | `count` |
| 0x02 | entrada[count] | 40 bytes cada, ver tabela acima |

**141 CHANNEL_ROOM_INFO_OUT (S→C), 2 + 68 × count bytes**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `u16` | `count` |
| 0x02 | registro[count] | 68 bytes cada: os primeiros 0x44 bytes do registro de sala (302) |

**123 OUT_CHANNEL_OUT (S→C), 8 bytes**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `i32` | `client_guid` |
| 0x04 | `u8` | `message` (lido como `byte message` de `NotifyOutChannel`; valor 0) |
| 0x05..0x07 | `byte[3]` | padding |

**240 SEND_MESSAGE (C→S)**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `u8` | `msg_type` (eco no 241). Inferido: primeiro parâmetro de `SendMsg(int msg_type, ...)`. |
| 0x01 | `u8` | `len` (máximo 0x78) |
| 0x02 | `char[len]` | texto, em bytes (sem conversão) |

**241 SEND_MESSAGE_OUT (S→C)**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `i32` | `sender` (`client_guid` do remetente; o cliente acha o nó por ele) |
| 0x04 | `u8` | `msg_type` (inferido de `NotifySendMsg(int sender, byte msg_type, string)`) |
| 0x05 | `u8` | `len` (máximo 0x78; o cliente descarta maior) |
| 0x06..0x07 | `byte[2]` | padding |
| 0x08 | `char[len]` | texto, sem NUL final |

**544 SAVE_OPTION (C→S), 37 bytes**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00..0x24 | `u8[37]` | Opções, na ordem de `LM_REGISTER_INFO` (`protocol/message.py`, `LmRegisterInfo`). Cada byte é uma opção. |

Evidência: `SaveOption` @0x10002930 chama `FUN_100018f0` com AX=0x220 (opcode 544) e N = 39 (2 de cabeçalho + 37 de corpo); o corpo é a cópia de `_OPTION_INFO`. Sem resposta conhecida.

**54 ERROR (S→C), envelope de 8 bytes**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `u16` | opcode real (302, 404 ou 701) |
| 0x02 | `byte[2]` | padding |
| 0x04 | `i32` | código de erro (chave de `msg_error` no `landmass.wdb`) |

Evidência: `re/channel_server.md` §3 (`u16 @0` e `i32 @4`, L96–108). O cliente mostra o código e segue o dispatch com o opcode real sobre o mesmo buffer (inferido).

**301 CREATE_ROOM (C→S), 74 bytes**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `char[32]` | `name` (NUL-terminado; shortcut) |
| 0x20 | `char[16]` | `password` (NUL-terminado; shortcut) |
| 0x30 | `i32` | `scale` |
| 0x34 | `i32` | `game_mode` |
| 0x38 | `i32` | `map_num` |
| 0x3C | `i32` | `max_player` |
| 0x40 | `i32` | `team_count` |
| 0x44 | `i32` | `limit_time` |
| 0x48 | `u16` | `limit_score` |

**302 CREATE_ROOM_OUT (S→C), registro de sala, 612 bytes**

Offsets relativos ao valor do nó (`re/rooms.md` §1, §2, §5 e 412). Bytes não listados ficam zero.

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `i32` | `room_id`; chave de busca de 302, 312, 322, 332, 342 e 412 |
| 0x04 | `u8` | `scale` (shortcut: posição inferida) |
| 0x10 | `char[32]` | `name` (shortcut: posição inferida) |
| 0x30 | `u8` | `has_password` (shortcut: posição inferida) |
| 0x38 | `u8` | `state`: 1 espera, 2 jogando |
| 0x39 | `u8` | `game_mode` |
| 0x3A | `u8` | `team_count` |
| 0x3B | `u8` | `curr_player` (conta o dono) |
| 0x3C | `u8` | `curr_spectator` (0) |
| 0x3D | `u8` | `max_player` |
| 0x3E | `u8` | `open` (1) |
| 0x40 | `i16` | `map_num` |
| 0x44 | `i16` | `limit_score` |
| 0x46 | `u8` | `limit_time` |
| 0x4C | `i32` | `master` (guid do dono) |
| 0x50 + 4·i, i < 70 | `i32` | guid do slot i, -1 se vazio |
| 0x174 + 4·j, j < 60 | `i32` | espectador j, -1 se vazio (fim do registro em 0x264) |

**311 IN_ROOM (C→S), 20 bytes**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `i32` | `room_id` (guid da sala; shortcut) |
| 0x04 | `char[16]` | `password` (shortcut: tamanho inferido dos 5 dwords) |

**312 IN_ROOM_OUT (S→C)**

Sucesso, 12 bytes:

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `i32` | `room_id` |
| 0x04 | `i32` | `client_guid` de quem entrou |
| 0x08 | `i32` | `slot` |

Erro, 18 bytes: `i32` com o código negativo, em que o código é `i16` @0 (1001, 1202, 1701 ou 200). Não usa envelope: o `u16` @0 positivo faria o ramo de sucesso rodar. Campos da sala, lidos pelo cliente:

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `i32` | código - 0x10000 (`i16` @0 = código) |
| 0x04 | `i32` | `room_id` (-1 se a sala não existe) |
| 0x08..0x0E | `u8[7]` | state, game_mode, team_count, curr_player, curr_spectator, max_player, open |
| 0x10 | `i16` | `map_num` |

**314 ROOM_INFO_OUT (S→C), 56 bytes**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `i16` | `limit_score` |
| 0x02 | `u8` | `limit_time` |
| 0x08 | `i32` | `master` |
| 0x0C | `i32` | `room_id` (chave de busca, `FUN_10019e90(body+0xc)`) |
| 0x10 | `u8` | `state` |
| 0x11 | `u8` | `game_mode` |
| 0x12 | `u8` | `team_count` |
| 0x13 | `u8` | `max_player` |
| 0x14 | `u8` | `open` |
| 0x16 | `i16` | `map_num` |

O 314 zera os slots; a lista de jogadores vem no 317, logo depois.

**317 ROOM_PLAYER_INFO_OUT (S→C)**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `u8` | `count` (até 255) |
| 0x01 | entrada[count] | 48 bytes cada, abaixo |

Entrada de 48 bytes:

| Offset na entrada | Tipo | Campo |
|------------------:|------|-------|
| 0x00..0x27 | — | registro de jogador como em 151 (`client_guid`, `total_exp`, `nick`, ...) |
| 0x28 | `u8` | `slot` |
| 0x29 | `u8` | `ready` (1 pronto) |
| 0x2A | `u8` | flag de estado: 0 vira 0x23 (em sala) |
| 0x2B | `u8` | `pc_room` (zero) |
| 0x2C | `i32` | `morats` (`select_morats_id`, +0xB4) |

A sala não vai na entrada: o cliente a tira do próprio jogador (`re/layouts_f0.md` §1.2).

**321 OUT_ROOM (C→S)**: corpo vazio.

**322 OUT_ROOM_OUT (S→C), 8 bytes**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `i32` | `room_id` |
| 0x04 | `i32` | `client_guid` de quem saiu |

**332 CHANGE_ROOM_MASTER_OUT (S→C), 8 bytes**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `i32` | `room_id` |
| 0x04 | `i32` | `master` novo |

Shortcut: layout inferido de `disp@2358` (body+4 vira o dono da sala, +0x5c); o RE tem gap no rótulo (`re/rooms.md` §10 conflita nos offsets).

**342 REMOVE_ROOM_OUT (S→C), 4 bytes**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `i32` | `room_id` (a chave é body@0; `disp@285-298`) |

Shortcut: o RE não decodifica o resto do corpo de 342 (gap); o emulador manda só os 4 bytes.

**401 READY_GAME (C→S), 1 byte**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `u8` | `morats` (`selected_morats`) |

**402 READY_GAME_OUT (S→C), 12 bytes**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `i32` | `client_guid` |
| 0x04 | `u8` | `ready` (flag; bit0 vira o pronto em +0xAC) |
| 0x08 | `i32` | `morats` (+0xB4) |

**403 START_GAME_OUT (S→C), 18 bytes**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `char[16]` | `address` da partida, NUL-terminado (`LANDMASS_GAME_HOST`) |
| 0x10 | `u16` | `port` da partida (`LANDMASS_GAME_PORT`) |

Shortcut: os 16 bytes de endereço são hipótese (`re/rooms.md` §8). Se o cliente não conectar, a falha aparece em `OnStartGame` → `OnReadyGameError(0)`.

**412 CHANGE_ROOM_PROPERTY_OUT (S→C), 16 bytes**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `i32` | `room_id` |
| 0x04 | `u8` | máscara; 0x20 indica o estado |
| 0x0F | `u8` | `state` (2 jogando) |

**420 CHANGE_ROOM_SLOT (C→S), 1 byte**: `u8 slot`.

**421 CHANGE_ROOM_SLOT_OUT (S→C), 8 bytes**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `i32` | `client_guid` |
| 0x04 | `u8` | `slot` |

**700 EXPEL_PLAYER (C→S), 4 bytes**: `i32 position`. Shortcut: `position` é o slot (`re/rooms.md` §7 deixa o mapeamento em aberto).

**701 EXPEL_PLAYER_OUT (S→C), 4 bytes**: `i32` 0 (sucesso) ou envelope `54` com 241000302 ou 241001202.

**545 REFRESH_ROOM_LIST (C→S), 44 bytes**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `i32` | `channel` (ignorado: canal único) |
| 0x04 | `u8` | `count`, máximo 9 (o cliente trunca acima disso) |
| 0x08 + 4·i | `i32` | `room_guid[i]` |

**547 REFRESH_ROOM_LIST_OUT (S→C)**: `u8 count` @0, 3 bytes sem uso, entradas de 16 bytes a partir de @4. Offsets da entrada:

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `i32` | `room_guid` |
| 0x04 | `u8` | `state` (0 vazio, 1 espera, 2 jogando) |
| 0x05 | `u8` | `game_mode` |
| 0x06 | `u8` | `team_count` |
| 0x07 | `u8` | `curr_player` |
| 0x08 | `u8` | `curr_spectator` |
| 0x09 | `u8` | `max_player` |
| 0x0A | `u8` | `open` |
| 0x0C | `u16` | `map_num` (shortcut: conflito com o 302, `re/layouts_f0.md` §4.2) |

**546 REFRESH_PLAYER_LIST (C→S), 64 bytes**: `i32 channel` @0 (ignorado); `u8 count` @4 (máximo 14); `i32 client_guid[i]` a partir de @8.

**548 REFRESH_PLAYER_LIST_OUT (S→C)**: `u8 count` @0, 3 bytes sem uso, entradas de 20 bytes a partir de @4. Offsets da entrada:

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `i32` | `client_guid` |
| 0x04 | `i32` | `total_exp` (zero até o marco 5) |
| 0x08 | `i32` | `clan` |
| 0x0C | `i32` | `clan_mark` |
| 0x10 | `u8` | `nest` |

Só quem está no lobby entra na resposta; sem nenhum, não há resposta. O cliente não cria jogador com o 548: só atualiza nó existente (`re/layouts_f0.md` §3.1). Os nicks vêm no 151 e no 317.

## Lobby

- Membros do lobby: `domain/lobby.py` (`Lobby`), chave `client_guid`, com a conexão e o nick. Estado só em memória (D12). `send_to` leva a mensagem a um subconjunto (membros da sala).
- O 151 lista todos os jogadores do lobby, o próprio incluído. O cliente só cria nó para quem está na lista, e sem o próprio nó o 317 e o 546 não funcionam.
- O 121 do recém-chegado vai aos demais. A ele vai como resposta ao `120`: `[151, 141, 121]`, na ordem observada.
- Cada conexão tem uma `outbox`. Quem quer enviar a outra conexão enfileira o corpo nela. Só a task de escrita da própria conexão grava no socket ([03-emulator](../architecture/03-emulator.md#concorrência)).
- A lista de 151 é tirada antes do join, e o broadcast de 121 não vai ao próprio jogador: ele recebe `[151, 141, 121]` como resposta ao `120`, na ordem observada.
- Queda da conexão com jogador no lobby gera `123` aos demais, depois de sair da sala. Conexão sem jogador no lobby não gera nada.

## Lacunas e inferências

Cada item com código afetado tem um `shortcut:` no código. Ao confirmar no cliente real, remova a inferência ou corrija o layout.

1. **Nick e progressão.** O nick vem em `R+0x08` de 151, 121 e 317 (`re/layouts_f0.md` §1.2), copiado de `account.nickname`. `total_exp` do 121 de quem entra e do 101 vem do banco (F3); na 151 e no 317 sai zero (`ChannelRecords` só tem o nick). Clã, marca e nest vão zerados até o marco 5.
2. **111 com `count` 1.** `FUN_1001c170` não lê o corpo da entrada (`re/LM_Engine.dll/channel_dispatch_FUN_1001da60.c` L978–992). Nenhum dado do canal é enviado. Se o cliente exigir nome de canal, o layout precisa ser decodificado.
3. **`num` do `120`.** O servidor original tem `channel_count 1`; o emulador ignora o `num`. Se o cliente escolher canais por índice, a lista de 111 precisa de mais de uma entrada.
4. **`result` recusado.** -160 é o código de senha inválida do Message. O canal original pode usar outro código.
5. **`location` (101 @0xAC), `message` (123 @4) e `msg_type` (240 @0, 241 @4).** Lidos pelo cliente ou inferidos da assinatura do evento; semântica não confirmada.
6. **Mesma conta em duas conexões.** A segunda substitui a primeira no lobby sem notificá-la.
7. **Heartbeat do servidor.** O cliente responde a `2` com `2`; o emulador envia `2` a cada 10 s e nunca responde. Não há evidência de que o cliente exija esse heartbeat; se a conexão cair em 20 s sem tráfego, reduzir o intervalo.
8. **Limite de lobby.** Uma lista de 151 cabe em um quadro de 65000 bytes: no máximo 1600 entradas (`MAX_LOBBY_ENTRIES`). A lista de salas (141) cabe em 955 registros (`MAX_ROOM_ENTRIES`).
9. **Pedidos de lista (64, 66, 67, 464).** Não tratados. 545 e 546 têm resposta (547 e 548). Se o lobby passar do limite do item 8, a paginação ainda não está decodificada.
10. **Chave de sessão não zerada.** O teste com o cliente real mostrou o `100` com 33 bytes zerados, depois de um `111` zerado. Não confirmado: o cliente aceitar a chave não zerada que o `111` entrega e reenviá-la em nova conexão ao canal. Se o cliente recusar, conferir `MsRegisterOut.session_key` e a regra de expiração em [authentication.md](authentication.md).
11. **544 sem resposta e ordem não confirmada.** O RE não tem opcode de retorno para `SaveOption`; o emulador não responde. A ordem dos 37 bytes segue `LM_REGISTER_INFO` (inferido: o RE mostra cópia de 37 bytes de `_OPTION_INFO`, e a struct `LM_OPTION_INFO` do UnrealScript não foi decodificada campo a campo). Se o cliente real mostrar uma opção trocada, decodificar `LM_OPTION_INFO` em `LM_Engine.u`. Conta sem registro devolve 0 em tudo (sem fonte no RE).
12. **Nome e senha da sala (301).** O tamanho de `name` (32) e `password` (16) e a ordem dos nove parâmetros de `CreateRoom` nos dwords e no `u16` são inferidos (`re/rooms.md` §1). Limites de 31 e 15 bytes em `domain/rooms.py` (shortcut). Confirmar com o hexdump do primeiro 301.
13. **`room_id` no 311.** A chave da sala é o guid que o cliente passa no 311 (`NetInRoom(num, pw)`). Tamanho da senha inferido pelos 5 dwords.
14. **Códigos do 312.** O `short` vai para `FUN_10021c80`, cujo mapa para `msg_error` está em gap no RE. Os códigos 1001, 1202 e 1701 são os sufixos de 211000000 + código em `msg_error` do `landmass.wdb`. "Partida já iniciada" é 212000200: o prefixo 212 não cabe no `short`, então o emulador manda 200. Confirmar o texto no cliente.
15. **Envelope 54 e dispatch.** O código fica em @4 (`re/channel_server.md` §3). O corpo real fica sobreposto ao envelope, conforme o RE (inferido). Por isso o 312 não usa envelope.
16. **Campos do registro de sala sem decodificação.** `scale` (0x04), `has_password` (0x30) e `name` (0x10) têm posição inferida. `curr_spectator` (0x3C) e `open` (0x3E) são valores fixos.
17. **Escopo da difusão.** Confirmado na análise de `re/rooms.md`, mas não no cliente real (ver tabela em [Salas](#salas)).
18. **Início e endereço da partida (403).** O 403 vai só aos membros, com `address` de 16 bytes (hipótese, `re/rooms.md` §8) e `port`. O servidor de partida não existe até o marco 4: o cliente tenta conectar e falha, o que é esperado. O critério do marco é o recebimento do 403.
19. **Escopo do chat na sala (240).** O RE não decodifica o escopo (`re/rooms.md` §6). Assumido: remetente em sala fala só com a sala.
20. **Expulsão (700/701).** `position` é o slot (`re/rooms.md` §7). Expulsar o próprio jogador devolve 241001202.
21. **Pronto e seletor (402, 317).** O bit de pronto é `u8 @4` do 402 e `u8 @0x29` do 317. O seletor `@0x2A` do 317 vai zero (inferido).
22. **Limite de entrada.** Valores fora da faixa na criação são limitados e logados, não recusados. Sem paginação de salas: o limite de 955 por 141 vale até o marco 4.
23. **Troca de dono (332).** Passa para o primeiro membro na ordem de entrada. Regra escolhida, não observada no cliente.
24. **Progressão no login (F2 e F3).** O 101 leva tutorial, exp, Cash e LD em `@0x28`, `@0x2C`, `@0x48` e `@0x4C` (`PlayerRecord`), e os pushes 900 e 902 saem depois do 111. Inferido dos layouts `LM_PLAYER_INFO` (`re/layouts_f0.md` §1.1 e §7.6); não confirmado no cliente real. O 902 vai no bloco misto do dispatcher (shortcut).
25. **Exp nos demais registros.** Só o 101 e o 121 de quem entra levam a exp do banco. A 151 da lista, a 548 (resposta ao 546) e o 317 da sala saem com `total_exp` zero, e a 549 não é tratada. A 151 traz o próprio jogador, mas o 121 chega depois e corrige a exp dele. Se o cliente grava a 548 e o 317 no nó do jogador como faz com o 121, a exp própria pode voltar a zero após um 546 ou uma entrada em sala. Não verificado no cliente real. Correção natural, fora deste marco: guardar `total_exp` no membro do lobby ao entrar e preenchê-lo na 151, na 317 e na 548.

## Checklist no cliente real

Conferir nesta ordem; cada falha aponta o item de lacunas indicado.

1. **Hexdump do primeiro 301.** O servidor loga `CreateRoom` com hexdump. Os 74 bytes devem bater com `CsCreateRoomIn` (item 12).
2. **Criar sala com nome de 3 caracteres.** A sala aparece na lista de quem já está no lobby (302). Quem entra depois a vê no 141.
3. **Criar com nome de 2 caracteres.** Aparece a mensagem de nome curto (211000202).
4. **Entrar com senha errada.** Aparece a mensagem de senha inválida (1701), e nenhum slot fica ocupado (item 14).
5. **Entrar com a senha certa.** Os dois slots aparecem com o estado certo e o nick de cada um (item 1).
6. **Pronto.** O entrante marca pronto (401); o estado aparece nos dois clientes (402).
7. **Iniciar.** O dono inicia (401). Os dois recebem 412 e 403 com `127.0.0.1` e `7777`. O cliente tenta conectar; a falha é esperada até o marco 4 (item 18).
8. **Iniciar sem prontos.** Aparece a mensagem "ninguém está pronto" (404, 241002702).
9. **Sair.** A lista do outro atualiza (322). Se o dono sai, o outro vira dono (332). Sala vazia some da lista (342).
10. **Expulsar.** O dono expulsa; o alvo sai da sala. Não-dono recebe a recusa (241000302).
11. **Chat.** Mensagem na sala chega só à sala; no lobby, a todos (item 19). O remetente aparece com o nick, não com `[] texto` (item 1).
12. **Entrar em sala iniciada.** Aparece "partida já iniciada" (código 200 no 312; item 14).
13. **Queda em sala.** Os outros veem a saída (322).

## Responsabilidades do serviço

- Manter o lobby em memória (`domain/lobby.py`) e as salas em memória (`domain/rooms.py`).
- Resolver a chave de sessão do `100` no registro em memória (`ports/session_keys.py`).
- Gravar as opções da conta no 544 pelo `OptionsRepository` (`ports/options.py`). Sem resposta.
- Difundir entrada, saída, chat e eventos de sala conforme a tabela de escopo.
- Enviar o endereço da partida (403) vindo de `LANDMASS_GAME_HOST` e `LANDMASS_GAME_PORT`.
- Enviar heartbeat do servidor a cada 10 s por conexão.
- Partida e itens: marcos 4 e 5.
