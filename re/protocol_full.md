# Protocolo completo: Message (7313) e Channel (7314)

Escopo: todos os opcodes que o cliente envia ou recebe nas portas 7313 (Message, net_code 13) e 7314 (Channel, net_code 14), mais as mensagens GS_* entre o Channel e o servidor de partida (`LM_Engine.dll`). Esta página consolida `message_server.md`, `channel_server.md`, `rooms.md` e `layouts_f0.md`. Onde há detalhe byte a byte, a tabela aponta para o arquivo de origem.

## 0. Fontes e convenções

Binários (somente leitura, nada alterado em `cliente\system`):

| Binário | sha256 |
|---|---|
| `LM_Engine.dll` | `4a08e7cebf2abe31cc1e6d0f73bf7734b58af5ce5cc21474987f0242fd04230f` |
| `+server_interface.dll` | `18a3b8dc2935b8b811e3fd8e3345c450f7a1d760e5fbed8456168b8715b90c31` |
| `+manager_interface.dll` | `5052551eb049b037813c2ebc3e2933895c1a89332ad89fae11b37928e11febbd` |
| `_core_network.dll` | `8dbbba00cc649183a6affc616a9bac825e48bdfc5585bcccbc6ce5530c46b83b` |

Pseudocódigo em lote (Ghidra 12.1.4, mesmo provider do REA):

| Binário | Pasta | Funções | Decompiladas | Observação |
|---|---|---|---|---|
| `LM_Engine.dll` | `re/LM_Engine.dll/all/` | 983 | 972 | 11 já existiam em `re/LM_Engine.dll/` (não duplicadas, marcadas `duplicate` no índice). `1000e800` (LoadMap) expirou no dump headless e foi obtida por `mcp__rea__batch_decompile`. |
| `+server_interface.dll` | `re/+server_interface.dll/all/` | 409 | 409 | Inclui `Cchannel_interface`, `Cmessage_interface`, `Cresource_interface`, `Cupdate_interface`, `Cmembership_interface`. |
| `+manager_interface.dll` | `re/+manager_interface.dll/all/` | 350 | 350 | `Cmanager_interface` (porta 7310, fora do escopo). |
| `_core_network.dll` | `re/_core_network.dll/all/` | 373 | 373 | Transporte (`CnetworkClient`). |

Cada pasta tem um `_index.tsv` (endereço, nome, tamanho, thunk, status, arquivo, duplicata). Arquivo: `<endereço>_<nome>.c`.

Convenções:
- **N** = tamanho total no fio, em bytes, incluindo o cabeçalho de 2 bytes. Frame TCP = `u16 LE (N-2)` + corpo. Não há criptografia.
- **Offsets** = offset de corpo (depois do cabeçalho u16), salvo indicação `buf+`.
- **Cabeçalho** = `u16 LE = (opcode << 5) | net_code`. Message: `net_code` 13 (`config.ini`, `:MESSAGE`). Channel: 14 (`:CHANNEL`).
- **Resposta** = opcode do pedido + 1 quando observado no log (`message_server.md` §1). Os demais pares são inferidos pelo nome do evento e estão marcados.
- **(inferido)** = dedução a partir de código, sem captura. **(gap)** = layout ou semântica não decodificados.

Como os opcodes C→S foram obtidos: no `+server_interface.dll` o opcode está em `MOV EAX,imm` antes do `CALL` ao helper de montagem (helper `FUN_10003b10`, `FUN_10003ba0`, `FUN_10003c50`, `FUN_10003ce0`, `FUN_10001xxx`, opcode em AX, o helper faz `<< 5`), ou em `OR EBX,imm` após o `CALL [GetSendBuff]` (cabeçalho já deslocado; opcode = `imm >> 5`). Tabela extraída do disassembly de cada método, conferida com o pseudocódigo.

## 1. Framing e cabeçalho (ambas as portas)

| Item | Valor | Evidência |
|---|---|---|
| Frame | `u16 LE` (N-2) + corpo, máximo 65000 | `message_server.md` §1; `channel_server.md` §1 |
| Cabeçalho | `(op << 5) \| net_code` | `Cmessage_interface::Init` @0x10003940 lê net_code para `DAT_10016504`; `Cchannel_interface::Init` @0x10001140 |
| Envio | `CnetworkClient::GetSendBuff(N)` → escreve cabeçalho → `Send`. Retorno: `0` ok, `-10` falha de envio, `-0xb` sem buffer | `_core_network`; `FUN_1000bb80` @0x1000bb80 (Channel) |
| Recepção (Channel/GS) | aceita se `(hdr & 0x1f) == 0` ou `== ChannelNetCode()` (14) | `FUN_1000bcd0` @0x1000bcd9–0x1000bcf3 |
| Heartbeat | Cliente envia 2 a cada 10 s. Channel responde 2 (`channel_dispatch` case 2). Message não responde (dispatch: 3 = sem caso). | `message_server.md` §3; `channel_server.md` §3 |
| Erro (envelope) | Channel: opcode 54 = `u16 @0` opcode real + `i32 @4` erro. Message: não observado. | `channel_server.md` §3, L96–108 |

Portas: Message 7313 (`message_server.md`), Channel 7314 (`channel_server.md`). Outros servidores do cliente: ServerManager 7310, Update 7312 (`Cresource_interface` e `Cupdate_interface` em `+server_interface.dll`, fora desta tabela), Membership (`Cmembership_interface`, seção `:MEMBERSHIP` no cliente, porta não identificada (gap)).

---

## 2. Message Server (porta 7313, net_code 13)

### 2.1 Requisições C→S (`Cmessage_interface::*`, `+server_interface.dll`)

| op | Método (endereço da função) | Caminho | N | Corpo (offsets de corpo) | Resposta | Evidência |
|---|---|---|---|---|---|---|
| 2 | `SendHeartbeat` (0x10004230) | inline, `OR EBX,0x40` | 2 | — | nenhuma | `Cmessage_interface::SendHeartbeat` |
| 100 | `Login` (0x10003d90) | helper `FUN_10003b10`, AX=0x64 | 44 + id_len + pw_len | `MS_LOGIN_IN`: `i32 id_len @0`; `i32 pw_len @4`; `char login_num[33] @8`; padding @0x29..0x2b (lixo, não usar); `id` @0x2c; `pw` @0x2c+id_len. Ver `message_server.md` §5.1. | 101 (observado) | 0x10003d90 |
| 110 | `Register` (0x10003dc0) | inline, `OR EBX,0xdc0` | 2 | — | 111 (observado) | 0x10003dc0 |
| 120 | `InMessageServer` (0x10003e10) | inline, `OR EBX,0xf00` | 2 ou 3 | sem corpo; com parâmetro, 1 byte (`MS_IN_MESSAGE_SERVER_IN`, conteúdo (gap)). | 121 (observado) | 0x10003e10 |
| 130 | `GetChannelServerInfo` (0x10003f20) | inline, `OR EBX,0x1040` | 2 | — | 131 (observado) | 0x10003f20 |
| 140 | `CheckNickname` (0x10003e80) | helper `FUN_10003ce0`, AX=0x8c | 19 | `char nick[17]` @0, NUL-terminado (wrapper `0x10023a10`, cópia sem limite) | 141 (par não observado) | 0x10003e80; wrapper 0x10023a10 |
| 150 | `CreateNickname` (0x10003ea0) | inline, `OR EBX,0x12c0` | 2 ou 57 | 13 dwords @0x00..0x33 (bloco opaco); `u16 @0x34`; `u8 @0x36` (semântica (gap); a UI sugere opções + nick). Ver `message_server.md` §5.6. | 151 (par não observado) | 0x10003ea0 |
| 152 | `UpdateNickname` (0x10004280) | helper `FUN_10003ce0`, AX=0x98 | 19 | `char nick[17]` @0, NUL-terminado (wrapper `0x10023c20`) | 153 (par não observado) | 0x10004280 |
| 160 | `SendWhisper` (0x10003f70) | helper `FUN_10003ba0`, AX=0xa0 | `len + 0x16` | destinatário `char[18]` @0 (NUL-terminado); `u16 len` @0x12 (strlen da mensagem, máx. 0x78); texto `char[len]` @0x14 (wrapper `0x10023ce0`) | 161 (ok) ou 162 (erro) | 0x10003f70; `FUN_10003ba0` @0x10003ba0 |
| 170 | `GetRankingInfo` (0x10003fa0) | inline, `OR EBX,0x1540` | 2 | — | 171 (par não observado) | 0x10003fa0 |
| 171 | `GetClanInfo` (0x10003ff0) | inline, `OR EBX,0x1560` | 2 | — | 172 (inferido) | 0x10003ff0 |
| 174 | `GetClanMember` (0x10004040) | inline, `OR EBX,0x15c0` | 2 | — | 175 (inferido) | 0x10004040 |
| 177 | `SendClanMessage` (0x10004090) | helper `FUN_10003c50`, AX=0xb1 | `len + 4` | `u16 len` @0 (strlen, máx. 0x78); texto `char[len]` @2 (wrapper `0x10023e30`) | 178 (inferido) | 0x10004090; `FUN_10003c50` @0x10003c50 |
| 180 | `GetFriendList` (0x100040c0) | inline, `OR EBX,0x1680` | 2 | — | 183 por amigo, depois 188 por bloqueado; um registro por mensagem; sem registros, sem resposta (inferido) | 0x100040c0 |
| 181 | `AddFriendList` (0x10004110) | helper `FUN_10003ce0`, AX=0xb5 | 19 | `char nick[17]` @0, NUL-terminado, zerado antes da cópia (wrapper `0x10023f10`) | 183 com o registro do amigo; recusa: mesmo opcode com id 0 e gate `@0x28` negativo (inferido de 0xb7) | 0x10004110 |
| 182 | `GetDelFriendList` (0x10004130) | inline, `OR EBX,0x16c0` | 2 ou 6 | `u32 @0` = id do amigo: o wrapper (`0x10024a30`) procura o nick digitado na lista local e envia `node+0xc`; envia 0 se não achar | 184 (inferido) | 0x10004130; wrapper 0x10024a30 |
| 186 | `AddBlackList` (0x100041a0) | helper `FUN_10003ce0`, AX=0xba | 19 | `char nick[17]` @0, NUL-terminado, zerado antes da cópia (wrapper `0x10023f90`) | 188 com o registro do bloqueado; recusa igual a 181 (inferido de 0xbc) | 0x100041a0 |
| 187 | `GetDelBlackList` (0x100041c0) | inline, `OR EBX,0x1760` | 2 ou 6 | `u32 @0` = id do bloqueado: o wrapper (`0x10024af0`) procura o nick na lista local e envia `node+0xc`; 0 se não achar | 189 (inferido) | 0x100041c0; wrapper 0x10024af0 |
| 190 | `RefreshFriendList` (0x10004320) | inline, `OR EBX,0x17c0` | 2 ou 62 (o wrapper não envia se count = 0) | `u8 count @0` (1..14; acima de 13 vira 14); @1..@3 não usados; `i32 id[i] @4+4i` (i < 14; ids = tokens de param[1]; o último token só entra se a string terminar em espaço (mesmo laço do SaveOption); sem limite de tokens no cliente (gap)) | 191 (inferido; par não observado) | 0x10004320; wrapper 0x10024010 |
| 192 | `RefreshBlackList` (0x100042a0) | inline, `OR EBX,0x1800` | 2 ou 62 (o wrapper não envia se count = 0) | igual a 190 (wrapper `0x10024130`) | 193 (inferido; par não observado) | 0x100042a0 |
| 194 | `RefreshClanList` (0x100043a0) | inline, `OR EBX,0x1840` | 2 ou 62 (o wrapper não envia se count = 0) | igual a 190 (wrapper `0x10024250`) | 195 (inferido; par não observado) | 0x100043a0 |

Evidência de N: `FUN_10003ce0` (`param_2 != 0 ? param_4 + 0x13 : 2`), `FUN_10003c50` (`param_2 != 0 ? param_4 + 4 : 2`), `FUN_10003ba0` (`LEA EAX,[EBP+0x16]`). Os demais métodos calculam N por constante no próprio método (asm: `PUSH imm` antes de `CALL [GetSendBuff]`).

Interface paralela `Cmembership_interface` (seção `:MEMBERSHIP` com `server_ip`/`server_port`, string no binário; ausente de `config.ini`): `Login` (100, 0x100036e0), `Register` (110, 0x10003760), `SendHeartbeat` (2, 0x100037ce). Mesmos opcodes do Message, outro destino (gap: porta e servidor não identificados no cliente).

### 2.2 Respostas S→C (`FUN_10025120`, dispatcher do Message)

Dispatcher: `re/LM_Engine.dll/message_dispatch_FUN_10025120.c`. Rótulos de `case` e `if` (parser automático sobre o `.c`): 0, 1, 101, 111, 121, 131, 141, 151, 153, 161, 162, 171, 172, 173, 175, 176, 178, 183, 184, 188, 189, 191, 193, 195, e o `default` (sem efeito) para 3. Layouts completos e evidências por linha: `message_server.md` §4.

| op | Evento (`ULM_ServerInterface::Notify*`) | Struct | Corpo (resumo) | Par (pedido) | Evidência |
|---|---|---|---|---|---|
| 0 | `NotifyConnectMessageServer()` | — | evento local (`CnetworkClient::OnConnect`), sem pacote | — | `FUN_10025120` case 0; `message_server.md` §4 |
| 1 | `NotifyDisconnectMessageServer()` | — | evento local (origem no `_core_network` não verificada) | — | case 1 |
| 3 | (sem caso) | — | heartbeat do servidor, não processado | — | `default` |
| 101 | `NotifyLogin(bool forced_login, int result)` | `MS_LOGIN_OUT` | `u8 @0` = forced; `i32 @4` = result | 100 (observado) | case 0x65 |
| 111 | `NotifyRegister(LM_REGISTER_INFO)` | `MS_REGISTER_OUT` | `@0x00..0x24` = `LM_REGISTER_INFO` (37 bytes, §4.1); `@0x25..0x45` sem leitor; `i32 @0x48` = result | 110 (observado) | case 0x6f |
| 121 | `NotifyInMessageServer(int result, string nickname, int clan_code)` | `MS_IN_MESSAGE_SERVER_OUT` | `i32 @0` = result; nick `char[17] @4` (inferido) | 120 (observado) | case 0x79 |
| 131 | `NotifyChannelServerInfo(bool bRandom)` | `MS_GET_CHANNEL_SERVER_OUT` (nome não achado) | `u8 @0` = count; `u8 @1` = bRandom; entradas de 72 bytes a partir de `@2` | 130 (observado) | case 0x83 |
| 141 | `NotifyCheckNickname(int result)` | `MS_CHECK_NICKNAME_OUT` | `i32 @0` = result | 140 (par não observado) | case 0x8d |
| 151 | `NotifyCreateNickname(int result)` | `MS_CREATE_NICKNAME_OUT` | `i32 @0` = result | 150 (par não observado) | case 0x97 |
| 153 | `NotifyUpdateNickname(int result)` | `MS_CREATE_NICKNAME_OUT` (reuso) | `i32 @0` = result | 152 (par não observado) | case 0x99 |
| 161 | `NotifySendWhisper(string sender, string msg)` | `MS_SEND_WHISPER_OUT` | `u16 @0x12` = len (`> 0x78` descarta); texto @0x14 | 160 | case 0xa1 |
| 162 | `NotifySendWhisperError(int result, string receiver, string msg)` | `MS_SEND_WHISPER_ERROR_OUT` | `i32 @0` = result; `u16 @0x16` = len; texto @0x18 | 160 | case 0xa2 |
| 171 | `NotifyRankingInfo(LM_PLAYER_INFO[])` | `MS_RANKING_INFO_OUT` | entradas de 0x20 bytes a partir de `@0`: `i32 @0` índice; `u16 @4` result (0 encerra); nick a partir de `@6`; `i32 @0x18` iTotalExp (inferido); `u16 @0x1c` siClan (inferido); máx. 100 | 170 (par não observado) | case 0xab |
| 172 | `NotifyGetClanList()` | `MS_GET_CLAN_LIST_OUT` (nome não achado) | (gap) | 171 (inferido) | case 0xac |
| 173 | `NotifyDelClan()` | `MS_DEL_CLAN_INFO_OUT` | `i32 @0` = erro e chave (papel duplo, não confirmado) | (inferido) | case 0xad |
| 175 | `NotifyGetClanMember()` | `MS_GET_CLAN_MEMBER_OUT` | `i16 @0` chave; nick a partir de `@2`; `u8 @0x14` → +0xB0; `i32 @0x18` → +0x3C; `u8 @0x1C` → +0x23 | 174 (inferido) | case 0xaf |
| 176 | `NotifyDelClanMember()` | `MS_DEL_CLAN_MEMBER_OUT` | `i16 @4` | (inferido) | case 0xb0 |
| 178 | `NotifySendClanMessage(string sender, string msg)` | `MS_SEND_WHISPER_OUT` (reuso) | `u16 @0x12` = len; texto @0x14 | 177 (inferido) | case 0xb2 |
| 183 | `NotifyFriendList()` | `MS_GET_BLACK_LIST_OUT` (reuso) | gate `i32 @0x28 >= 0`; i32 em `@0,4,8,0xC,0x10,0x18,0x1C,0x20`; u8 em `@0x14,0x24,0x25,0x26` | 180 (inferido) | case 0xb7 |
| 184 | `NotifyDelFriend()` | `MS_DEL_FRIEND_LIST_OUT` | `i32 @0` = id do amigo (eco do 182); `i32 @4` = result; remove o nó pela chave `@0` se `@4 == 0` | 182 (inferido) | case 0xb8 |
| 188 | `NotifyBlackList()` | `MS_GET_BLACK_LIST_OUT` | igual a 183, exceto que não grava `@0x25` em +0xB0 | 186 (inferido) | case 0xbc |
| 189 | `NotifyDelBlack()` | `MS_DEL_BLACK_LIST_OUT` | `i32 @0` = id do bloqueado (eco do 187); `i32 @4` = result; remove o nó pela chave `@0` se `@4 == 0` | 187 (inferido) | case 0xbd |
| 191 | (sem evento; atualiza amigos em lote) | — | `u8 @0` = count; registros de 0x14 a partir de `@4` | 190 (inferido) | case 0xbf |
| 193 | (sem evento; atualiza lista em lote) | — | `u8 @0` = count; registros de 0x14 a partir de `@4` (`i32 @0` → +0xA0, `i32 @4` → +0x3C, `i32 @8` → +0x28, `i32 @0xC` → +0x2C, `u8 @0x10` → +0x30, `u8 @0x11` → +0xB0) | 192 (inferido) | case 0xc1 |
| 195 | (sem evento; atualiza clã em lote) | — | cabeçalho `i32 @0` → +0x28, `i32 @4` → +0x2C, `u8 @8` → +0x30, `u8 @9` = count; registros de 0x0C a partir de `@0x0C` | 194 (inferido) | case 0xc3 |

Detalhes de byte, rótulos e linhas do `.c`: `message_server.md` §4 e §4.1–§4.2.

---

## 3. Channel Server (porta 7314, net_code 14)

### 3.1 Requisições C→S (`Cchannel_interface::*`, `+server_interface.dll`)

Total: 60 opcodes com cabeçalho medido (extração automática conferida com o texto de `channel_server.md` §2). Caminho: `helper` = `FUN_1000xxxx` com AX; `inline` = `OR EBX,lit` após GetSendBuff (`lit >> 5` = opcode). N e caminho vêm de `channel_server.md` §2 e do disassembly; o corpo (campos, tipos e ordem) vem dos wrappers de `LM_Engine.dll` nesta revisão (endereço do wrapper em cada linha). Se `channel_server.md` §2 divergir, prevalece esta página.

| op | Método (endereço) | Caminho | N | Corpo (offsets de corpo) | Resposta (pareamento) |
|---|---|---|---|---|---|
| 2 | `SendHeartbeat` (0x100027a0) | inline, lit 0x40 | 2 | — | 2 (Channel responde) |
| 62 | `LoginServerMonitor` (0x10001ce0) | helper `FUN_10001380`, AX=0x3e | 34 | nome[16] @0; `u16` porta @16; extra[14] @18 (distribuição inferida) | (gap) |
| 64 | `RequestSubChannnelInfo` (0x10001da8) | inline, lit 0x800 | 2 | — | (gap) |
| 66 | `SendLobbySpecInfo(u32 a, bool b)` | inline, lit 0x840 | 10 | `u32 a @0`; `u32 b @4` | (gap) |
| 67 | `RequestRoomList(int a)` | inline, lit 0x860 | 6 | `i32 a @0` | (gap) |
| 68 | `RegisterChannelServer(char p17[17])` | helper `FUN_10001420`, AX=0x44 | 19 | 17 bytes: 4 dwords @0..@12 + `u8` @16 | (gap) |
| 72 | `RequestForceUserQuit(char p17[17])` | helper `FUN_10001420`, AX=0x48 | 19 | igual a 68 | (gap) |
| 100 | `InChannelServer(CS_IN_CHANNEL_SERVER_IN)` | helper `FUN_100014e0`, AX=0x64 | 35 | 8 dwords @0..@31 + `u8` @32 | 101 |
| 105 | `SetRegular(CS_SET_REGULAR_IN)` | inline, lit 0xd20 | 4 ou 2 | `u8 @0` = param[0]; `u8 @1` = param[1] (dois parâmetros; wrapper `0x10017dd0`) | 104 (inferido) |
| 120 | `InChannel(CS_IN_CHANNEL_IN)` | inline, lit 0xf00 | 6 ou 2 | `u32 @0` | 121 |
| 122 | `OutChannel()` | inline, lit 0xf40 | 2 | — | 123 |
| 240 | `SendMsg(CS_SEND_MESSAGE_IN, texto)` | helper `FUN_10001790`, AX=0xf0 | len + 4 | `u16 @0` (`p[0..1]`); `len = p[1]`; texto @2 | 241 |
| 250 | `SendCommand(CS_SEND_COMMAND_IN, texto, idx)` | helper `FUN_10001790`, AX=0xfa | len + 4 | igual a 240 | 251 |
| 301 | `CreateRoom(CS_CREATE_ROOM_IN)` | helper `FUN_10001580`, AX=0x12d | 76 | 18 dwords @0..@71 + `u16` @72 | 302 |
| 311 | `InRoom(CS_IN_ROOM_IN)` | helper `FUN_10001620`, AX=0x137 | 22 | 5 dwords (20 bytes) | 312 |
| 321 | `OutRoom()` | inline, lit 0x2820 | 2 | — | 322 |
| 401 | `ReadyGame(CS_READY_GAME_IN)` | inline, lit 0x3220 | 3 ou 2 | `u8 @0` | 402 |
| 411 | `ChangeRoomProperty(CS_CHANGE_ROOM_PROPERTY_IN)` | helper `FUN_100016e0`, AX=0x19b | 12 | `u32 @0`; `u32 @4`; `u16 @8` | 412 |
| 420 | `ChangeRoomSlot(CS_CHANGE_ROOM_SLOT_IN)` | inline, lit 0x3480 | 3 ou 2 | `u8 @0` = grupo, não slot (`ChangeTeam`, D66; wrapper `0x100179c0`) | 421 |
| 451 | `RoomExpel(CS_ROOM_EXPEL_IN)` | helper `FUN_10001830`, AX=0x1c3 | 20 | 18 bytes: `@0` não é preenchido pelo wrapper `0x10017a10` (lixo de pilha, gap); nick `char[17]` a partir de @1 (cópia sem limite) | 452 (**gap**: sem `case 452` no dispatcher) |
| 461 | `RoomInvite(CS_ROOM_INVITE_IN)` | helper `FUN_10001420`, AX=0x1cd | 19 | `char nick[17]` @0, NUL-terminado (wrapper `0x10017a90`, cópia sem limite) | 462 |
| 464 | `GetChannelPlayerInfo()` | inline, lit 0x3a00 | 2 | — | 151 (inferido) |
| 471 | `RoomInviteAnswer(CS_ROOM_INVITE_ANSWER_IN)` | inline, lit 0x3ae0 | 10 ou 2 | `i32 chave @0` = atoi(param[1]) (padrão `DAT_1005aa90` se faltar); `u8 aceite @4` = 1 se param[0] for 'Y' ou 'y' (wrapper `0x10017b10`); @5..@7 não inicializados (gap) | (gap) |
| 500 | `ExitPlay()` | inline, lit 0x3e80 | 2 | — | 501 |
| 540 | `GetChannelRoomDetail(CS_CHANNEL_ROOM_DETAIL_IN)` | inline, lit 0x4380 | 10 ou 2 | `u32 @0`; `u32 @4` | 541 |
| 542 | `GetChannelPlayerDetail(CS_CHANNEL_PLAYER_DETAIL_IN)` | helper `FUN_10001420`, AX=0x21e | 19 | `char nick[17]` @0, NUL-terminado (wrapper `0x10017d50`) | 543 |
| 544 | `SaveOption(_OPTION_INFO)` | helper `FUN_100018f0`, AX=0x220 | 39 | 36 bytes `u8` @0..@35: um valor por token numérico de param[0] seguido de param[1] (separados por espaço; a última token só é lida se a string termina em espaço; o total tem de ser 36, senão o cliente lança exceção) (wrapper `0x10017e60`); @36 não preenchido (gap) | (gap) |
| 545 | `RefreshRoomList(CS_REFRESH_ROOM_LIST_IN)` | helper `FUN_10001a40`, AX=0x221 | 46 | `i32 nChannel @0`; `u8 count @4` (>8 vira 9; 0 = nada); `i32 room_guid[i] @8+4i` (i<9) | 547 (lista) |
| 546 | `RefreshPlayerList(CS_REFRESH_PLAYER_LIST_IN)` | helper `FUN_10001ae0`, AX=0x222 | 66 | `i32 nChannel @0`; `u8 count @4` (>14 vira 14); `i32 client_guid[i] @8+4i` (i<14) | 548 (lista) |
| 550 | `ItemBuy(CS_ITEM_BUY_IN)` | helper `FUN_10001990`, AX=0x226 | 14 | `i32 nItemID @0`; `u8 bPoint @4` (param[1]; 1 = LD); `u8 nBuyOption @5` (param[2]); `u16 @6` (param[3]) e `u8 @8` (param[4] != 0) só são gravados se count > 3 e > 4; no `.u` ItemBuy tem 3 parâmetros, então @6..@11 = 0 (wrapper `0x10017fa0`) | 551 |
| 555 | `ItemDestroy(CS_ITEM_DESTROY_IN)` | inline, lit 0x4560 | 10 ou 2 | `i32 nItemID @0`; `u16 nIndex @4` (param[1]); @6..@7 = 0 (wrapper `0x10018190`) | 556/559 |
| 560 | `ItemUsed(CS_ITEM_USED_IN)` | inline, lit 0x4600 | 10 ou 2 | `u16 nItemIndex @0`; `u16 nGateIndex @2`; @4..@7 = 0 (`ItemUsed`, wrapper `0x100181f0`). `ItemUsedByValue` (wrapper `0x10018260`, 3 parâmetros) usa o mesmo opcode com `i32 valor @4` = param[2] | 561 / 562 / 565–568 |
| 570 | `ItemUnused(CS_ITEM_UNUSED_IN)` | inline, lit 0x4740 | 6 ou 2 | `u16 nItemIndex @0`; `u16 nGateIndex @2` (wrapper `0x100182e0`) | 573 |
| 580 | `ItemExtend(CS_ITEM_EXTEND_IN)` | inline, lit 0x4880 | 10 ou 2 | `i32 nItemID @0`; `u16 nItemIndex @4`; `u8 @6` (param[2]); `u8 @7` (param[3]) (wrapper `0x10018340`) | 581 (NotifyItemExtend por goto, ver §3.2) |
| 586 | `InHangar()` | inline, lit 0x4940 | 2 | — | 587 |
| 588 | `OutHangar()` | inline, lit 0x4980 | 2 | — | 589 |
| 600 | `ClearTutorial(CS_CLEAR_TUTORIAL_IN)` | inline, lit 0x4b00 | 3 ou 2 | `u8 @0` = param[0] (passo do tutorial; wrapper `0x100186a0`) | 601 |
| 610 | `GetGiftItem(CS_GET_GIFTITEM_IN)` | inline, lit 0x4c40 | 6 ou 2 | `i32 Page @0` (wrapper `0x10018110`) | 611 |
| 612 | `GiftItemUsed(CS_GIFTITEM_USED_IN)` | inline, lit 0x4c80 | 6 ou 2 | `i32 nItemID @0` (wrapper `0x10018150`) | 613 |
| 615 | `ItemGift(CS_ITEM_GIFT_IN)` | helper `FUN_10001c20`, AX=0x267 | 26 | `i32 nItemID @0`; `u8 bPoint @4`; `u8 @5` (param[2]); `char strNick[18] @6`, NUL-terminado, destinatário (wrapper `0x10018050`, cópia sem limite) | 616 |
| 640 | `RegisterGroup()` | inline, lit 0x5000 | 2 | — | (gap; 641 não tratado, guarda `!= 0x281`) |
| 642 | `GetMatchingGroup()` | inline, lit 0x5040 | 2 | — | 643 |
| 644 | `RequestMatch(CS_REQUEST_MATCH_IN)` | inline, lit 0x5080 | 10 ou 2 | `u32 @0`; `u32 @4` | 648 (inferido) |
| 645 | `AcceptMatch(CS_REQUEST_MATCH_IN)` | inline, lit 0x50a0 | 10 ou 2 | igual a 644 | 650 (inferido) |
| 646 | `RejectMatch(CS_REQUEST_MATCH_IN)` | inline, lit 0x50c0 | 10 ou 2 | igual a 644 | 651 (inferido) |
| 647 | `CancelMatch(CS_REQUEST_MATCH_IN)` | inline, lit 0x50e0 | 10 ou 2 | igual a 644 | 652 (inferido) |
| 655 | `EndMatch()` | inline, lit 0x51e0 | 2 | — | 656 |
| 657 | `ChangeGroupSlot(CS_CHANGE_ROOM_SLOT_IN)` | inline, lit 0x5220 | 3 ou 2 | `u8 @0` | 658 |
| 659 | `RefreshClanMatchInfo(CS_REFRESH_CLAN_MATCH_INFO_IN)` | helper `FUN_10001b80`, AX=0x293 | 42 | 10 dwords (40 bytes) | 659 (mesmo valor nos dois sentidos) |
| 700 | `ExpelPlayer(CS_EXPEL_PLAYER_IN)` | helper `FUN_10001830`, AX=0x2bc | 20 | `u8 tipo @0` = atoi(param[0]) (0x10 WEB, 0x21 CHANNEL, 0x22 LOBBY só no ramo sem parâmetro); `char nick[17] @1`, NUL-terminado (wrapper `0x10017bb0`) | 701 |
| 850 | `RequestLoadChannelServer()` | inline, lit 0x6a40 | 2 | — | (gap) |
| 851 | `RequestLoadMessageServer()` | inline, lit 0x6a60 | 2 | — | (gap) |
| 852 | `RequestLoadServerManager()` | inline, lit 0x6a80 | 2 | — | (gap) |
| 860 | `RequestUnloadChannelServer()` | inline, lit 0x6b80 | 2 | — | (gap) |
| 861 | `RequestUnloadMessageServer()` | inline, lit 0x6ba0 | 2 | — | (gap) |
| 862 | `RequestUnloadServerManager()` | inline, lit 0x6bc0 | 2 | — | (gap) |
| 870 | `RequestRebootSystem()` | inline, lit 0x6cc0 | 2 | — | (gap) |
| 880 | `RequestLoadGameServerManager()` | inline, lit 0x6e00 | 2 | — | (gap) |
| 881 | `RequestUnloadGameServerManager()` | inline, lit 0x6e20 | 2 | — | (gap) |
| 890 | `RequestGameServerInfo()` | inline, lit 0x6f40 | 2 | — | (gap) |

Nota de consistência: os opcodes 850–890 são pedidos de administração (`Request*Server`) para o próprio Channel. O cliente os envia; a resposta não tem `case` no dispatcher (gap).

### 3.2 Respostas S→C (`FUN_1001da60`, dispatcher do Channel)

Dispatcher: `re/LM_Engine.dll/channel_dispatch_FUN_1001da60.c` (2940 linhas). Rótulos de `case`/`if` extraídos automaticamente (`dispatch_cases.py`, ~89 rótulos). Layouts por evento: `channel_server.md` §3.1 (linhas `L…` do `.c`) e `layouts_f0.md` (§1.2 jogadores, §3.1 jogador, §4.2 salas, §7.4 start, §7.6 itens). Abaixo, uma linha por opcode; **corpo** = resumo; detalhe completo no arquivo indicado.

Envelope de erro (op 54, L96–108): `u16 @0` = opcode real; `i32 @4` = erro; se erro ≠ 0, chama `NotifyErrorMessage(erro)`.

| op | Evento | Corpo (resumo) | Par (pedido) | Evidência (`.c`) |
|---|---|---|---|---|
| 0 | `NotifyConnectChannelServer()` | evento local; zera `DAT_1005ada0` | — | L809–830 |
| 1 | `NotifyDisconnectChannelServer(0)` | evento local | — | L831–845 |
| 2 | `SendHeartbeat()` | responde 2 | 2 | L846–849 |
| 54 | `NotifyErrorMessage(erro)` | `u16 @0` opcode real; `i32 @4` erro | — | L96–108 |
| 101 | `NotifyInChannelServer` | `i32 @0xa8` = resultado; se 0: `i32 @0x90` → `DAT_1005ada0`, `i32 @0xac` → `_DAT_1005ae08`; copia 168 bytes para nó novo | 100 | L853–882 (`channel_server.md` §3.1) |
| 102 | `NotifyGetItem` | `u16 @0` key; registro 0x34 bytes; `u8 @0x35` ≠ 0 zera `i32 @0x30` | (gap) | L883–900 |
| 103 | `NotifyGetMorats` | `i16 @0` key; `u8 @0x5d` ≠ 0 zera `i32 @0x30`; 92 bytes copiados se chave nova | (gap) | L901–933 |
| 104 | `NotifySetRegular` | sem corpo lido; evento sem argumentos (`NotifySetRegular()`) | 105 | L934–937 |
| 107 | `NotifyGetTrainingMorats` | (gap) | (gap) | L938–960 |
| 108 | `NotifyMoratsCreated` | (gap) | (gap) | L961–977 |
| 111 | `NotifyChannelInfo` | `u8 @0` = count; `u8 @(1+i)` = carga do canal (>=100 = FULL) | (gap) | L978–992 |
| 121 | `NotifyInChannel` | `i32 @0` = id (<0 erro); preenche nó do canal (`channel_server.md` §3.1) | 120 | L2772–2824 |
| 123 | `NotifyOutChannel` | `i32 @0` = id; guarda `!= 0x7b` | 122 | L997–1037 (guarda L807) |
| 141 | `NotifyChannelRoomInfo` | `u16 @0` = count; entradas a partir de `@2` (gap) | (gap) | L1039–1081 |
| 142 | `NotifyMatchRoomInfo` | (gap) | (gap) | L1082–1110 |
| 143 | `NotifyMatchRoomInsert` | (gap) | (gap) | L1111–1128 |
| 144 | `NotifyMatchRoomDelete` | (gap) | (gap) | L1129–1143 |
| 151 | `NotifyChannelPlayerInfo` | `u16 @0` = count; entradas de 40 bytes a partir de `@2` (`layouts_f0.md` §1.2) | (inferido) | L1147–1245 |
| 241 | `NotifySendMsg` | `u8 @5` = len; texto a partir de `@8` (`len > 0x78` não decodificado) | 240 | L1246–1280 |
| 251 | `NotifySendCommand` | `u8 @0` = comando; texto a partir de `@1` | 250 | L1281–1311 |
| 302 | `NotifyCreateRoom` | corpo para inserção de sala (layout (gap)) | 301 | L1312–1347 |
| 312 | `NotifyInRoom` | `i32 @0` = resultado (<0 erro, `i16 @0` código); sucesso (gap) | 311 | L1348–1349; L2858–2934 |
| 314 | `NotifyRoomInfo` | cabeçalho `i16 @0`, `u8 @2..@4`, `i32 @8`; a partir de `@0x0c` campos de sala (`channel_server.md` §3.1) | (gap) | L1350–1388 |
| 317 | `NotifyRoomPlayerInfo` | `u8 @0` = count; registros de 0x30 bytes (`channel_server.md` §3.1) | (gap) | L1389–1473 |
| 322 | `NotifyOutRoom` | `i32 @0` → `_DAT_1005aa74` | 321 | L173–248 |
| 323 | `NotifyDisconnectChannelServer` (alias) | — | — | L249–252 |
| 332 | `NotifyChangeRoomMaster(CS_CHANGE_MASTER_OUT)` | **(parcial)** `i32 @0` = room_guid; `i32 @4` = client_guid (assinatura `NotifyChangeRoomMaster(int room_guid, int client_guid)`, wrapper `0x10002f80`). No dispatcher: validação `FUN_10018aa0` e gravação em `sala+0x5c` (inferido); semântica de master (gap) | (inferido) | L256–284 |
| 342 | `NotifyRemoveRoom` | `i32 @0` = room_guid (assinatura `NotifyRemoveRoom(int room_guid)`, wrapper `0x10002e50`); se não é a sala atual, `FUN_1001c990` remove | (inferido) | L285–298 |
| 402 | `NotifyReadyGame` | `u8 @4` = flag (bit0 → +0xAC); `i32 @8` → +0xB4; +0xB0 = 0x24/0x23 | 401 | L299–300; L2825–2853 |
| 403 | `NotifyStartGame(string address, int port)` | `char[16] @0` endereço; `u16 @0x10` porta | (inferido) | L301–346; `layouts_f0.md` §7.4 |
| 404 | `NotifyReadyGameError` | sem corpo | 401 | L347–351 |
| 412 | `NotifyChangeRoomProperty` | `u8 @4` = máscara: bit0 `i16 @6`; bit1 `u8 @8`, `@9`; bit2 `u8 @10`; bit3 `i16 @0xc`; bit4 `u8 @0xb`; bit5 `u8 @0xf`; bit6 `u8 @0xe` | 411 | L352–381 |
| 421 | `NotifyChangeRoomSlot(CS_CHANGE_ROOM_SLOT_OUT)` | **(decodificado nesta revisão)** `i32 @0` = guid do jogador; `u8 @4` = slot de destino, sem limite verificado (o laço de busca usa 60 entradas, `sala+0x50+4·i`). Limpa o slot antigo (-1) e grava o guid no novo | 420 | L382–406 |
| 462 | `NotifyResultRoomInvite(CS_RESULT_OUT)` | o evento recebe o corpo (`NotifyResultRoomInvite((CS_RESULT_OUT*)param_2)`); `i32 @0` = result (desreferenciado pelo wrapper `0x10003170`). Antes disso, se o erro do envelope `pCVar16` for `0xfffff023` (−4061), retorna sem notificar (inferido) | 461 | L407–415 |
| 463 | `NotifyRoomInvite(CS_ROOM_INVITE_OUT)` | `i32 @0` → `DAT_1005aa90` | (gap; convite recebido, não resposta de 461) | L416–423 |
| 501 | `NotifyExitPlay` | `i32 @0` → `_DAT_1005aa58` | 500 | L424–427 |
| 512 | `NotifyGameResult(CS_GAME_RESULT_OUT)` | `i32 @0` (vs `DAT_1005ada0`); `i32 @4` → +0x3C; `i32 @8` → +0x5C; `i16 @0xc`; `i32 @0x10` → +0x40 | (resultado de partida, sem pedido) | L432–487 |
| 541 | `NotifyDetailRoomInfo` | `i16 @0` → +0x54; `u8 @2..@4` → +0x56..+0x58; `i32 @8` → +0x5C; `i16 @0x18/0x1a/0x1c` limitados | 540 | L488–534 |
| 543 | `NotifyDetailPlayerInfo(int result, LM_PLAYER_DETAIL_INFO)` | `int result` = `(int)pCVar16`, ou seja, o erro do envelope (0 = ok); corpo `param_2` (`PLAYER_INFO_DETAIL`): `char nick[] @0` (ANSI, NUL); `i32 @0x14, @0x18, @0x1c, @0x20, @0x24, @0x28, @0x2c, @0x30, @0x38`; `u8 @0x34`; `char texto2[] @0x3c` (ANSI, NUL); semântica dos campos (gap) (wrapper `0x10004750`) | 542 | L535–540 |
| 547 | `NotifyChangeRoomProperty` (lista) | `u8 @0` = count; entradas de 16 bytes a partir de `@4`: `i32 @4` room_guid; `u8 @8`→+0x48 … `u16 @0x10`→+0x50 | 545 | L541–576; `layouts_f0.md` §4.2 |
| 548 | `NotifyChangePlayerProperty` (lista) | `u8 @0` = count; entradas de 20 bytes a partir de `@4`: `i32 @4` client_guid; `i32 @8` → +0x3C; `i32 @0xc` → +0x28; `i32 @0x10` → +0x2C; `u8 @0x14` → +0x30 | 546 | L577–607; `layouts_f0.md` §3.1 |
| 549 | `NotifyInRoom` (2) | `i32 @0` → +0xA0; `i32 @4` → +0x3C; campos de jogador; `u8 @0x28` = índice na sala | (gap) | L608–691 |
| 551 | `NotifyItemBuy` | `u16 @0` key; registro 0x34; `i32 @0x38` → +0x58 (iCash); `i32 @0x3c` → +0x5C (iPoint); `i32 @0x40` = resultado (0 aplica) | 550 | L692–719; `layouts_f0.md` §7.6 |
| 552 | `NotifyMoratsBuy(CS_MORATS_BUY_OUT)` | `u16 @0` key; registro 0x5c; `i32 @0x5c` → +0x58; `i32 @0x60` → +0x5C; `i32 @0x64` = resultado | (gap; compra de morat) | L720–748 |
| 553 | `NotifyItemUsedGate` | `u16 @0` key; `u16 @2` idx; `i32 @4` = resultado; se 0 remove item | (inferido) | L749–775 |
| 554 | `NotifyItemUsedSystem` | `u16 @0` key (registro de 0x34 bytes, como 102); `u16 @0x34` slot de sistema (0 a 9, `sEventSlot`; grava `*param_2` em `local_89c[idx+0x60]`); `i32 @0x38` = resultado (gate `== 0` aplica) | 560 (`CsItemUsedSystemOut`, medido) | L776–808 |
| 556 | `NotifyItemDestroy` (guarda `== 0x22c`) | `u16 @0` key (índice do item); `u16 @2` **gate** do morat (corrigido nesta revisão: não é índice); `u8 @4` flag (1 = estava montado); `i32 @8` = resultado (o despacho grava o erro do envelope em @8; gate `== 0`); o evento recebe o corpo | 555 | L110–170 |
| 557 | `NotifyMoratsDestroy` | `u16 @0` key; `i32 @4` = resultado (gate `== 0` aplica); o evento recebe o corpo (`CS_MORATS_DESTROY_OUT`) | (inferido) | L2452–2468 |
| 559 | `NotifyGetSystemItemState` + `NotifyItemDestroy` | `u16 @0` key (índice); `u16 @2` slot de sistema (grava `0xff` no estado, liberando o slot); `u8 @4` = 1; `i32 @8` = resultado (gate `== 0`); `NotifyGetSystemItemState` recebe `pCVar16+0x60` (layout do estado (gap)) | 555 (item de sistema) | L2469–2489 |
| 561 | `NotifyItemUsed` | `i32 @8` = resultado (o despacho grava o erro do envelope em @8) | 560 | L2490–2495 |
| 562 | `NotifyItemUsed` | `u16 @0` gate; `u16 @2` índice do item montado (0 na recusa); `u16 @6` slot da peça (0 a 15, `SLOT_NAMES`), gravado em `local_8a4[0] + u16@6·2 + 0x44`; `i32 @8` = resultado (gate `== 0`) | 560 | L2496–2510 |
| 565 | `NotifyItemUsed` | `u16 @0` key; `u16 @2` valor gravado em `+ u16@4·2 + 0x64`; `i32 @8` = resultado (gate `== 0`) | 560 | L2511–2525 |
| 566 | `NotifyItemUsed` | `i32 @4` = resultado (sem gate; evento direto) | 560 | L2526–2528 |
| 567 | `NotifyItemUsed` (cauda `LAB_1001fdb3`) | `u16 @0` key; `i32 @4` = resultado (gate `== 0`); evento recebe 100 (constante) ou `iVar13 = @4` (caminho de erro) | 560 | L2529–2555 |
| 568 | `NotifyItemUsed` | `u16 @0` key; `i32 @4` = resultado (gate `== 0`); evento recebe 0x65 (constante) ou `iVar13 = @4` | 560 | L2556–2571 |
| 569 | `NotifyChangeNest` | `u16 @0` key; `u8 @2` → nó `+0x30`; `i32 @4` = resultado (gate `== 0`) e argumento do evento | (inferido) | L2572–2586 |
| 571 | `NotifyItemUnused` (sem caso próprio: `goto LAB_1001fb03`, cauda em L2631–2632) | (gap) | (inferido) | L2587–2601 |
| 572 | `NotifyItemUnused` (via `goto LAB_1001fafc` e `goto LAB_1001fb03`) | desmontagem de peça (medido): `u16 @0` gate; `u16 @4` slot (0 a 15); `i32 @8` = resultado (gate `== 0` limpa a peça) | 570 | L2602–2615 |
| 573 | `NotifyItemUnused` | caminho de skin (`CITEM_SKIN`): `u16 @0` key; `u16 @4` índice (grava `0xffff`); `i32 @8` = resultado (gate `== 0`). O F6 não emite | 570 | L2616–2633 |
| 581 | `NotifyItemExtend` (via `goto LAB_1001fbf8`, L2682–2683) | caminho de morat (sem prazo). Não emitido: o F7 recusa a extensão de morat com 582 e `result` -4 | 580 | L2634–2656 |
| 582 | `NotifyItemExtend` (fall-through de L2682–2683) | medido: `u16 @0` índice; `i32 @4` apply_value (fim em segundos Unix, REALTIME); `i32 @8` cash; `i32 @0xc` point (LD); `i32 @0x10` = resultado (gate `== 0` grava prazo e saldos) | 580 | L2657–2685 |
| 585 | `NotifyItemEndtime` | `u8 @0` premium (0 no F7; o cliente não o lê, inferido); `u8 @1` bItem (1 = item, 0 = morat); `u16 @2` índice; o evento recebe o corpo (`CS_ITEM_ENDTIME_OUT`) | login e fim de prazo (inferido) | L2686–2704 |
| 587 | `NotifyEnterHanger(bool)` | `i32 @0` = chave; o evento recebe `(i32 @0 == DAT_1005ada0)` (jogador atual) | 586 | L2705–2712 |
| 589 | `NotifyLeaveHanger(bool)` | `i32 @0` = chave; `u8 @4` = 0x23 (condição); o evento recebe `(i32 @0 == DAT_1005ada0)` | 588 | L2713–2723 |
| 590 | `NotifyItemUsedChangeMainMorats` | `u16 @0` key; `u8 @2` → nó `+0x98`; `i32 @4` = argumento do evento | (inferido) | L2724–2748 |
| 591 | `NotifyGetGatchaPrize` (retorno em L2771) | `u16 @0` key; `i32 @4` = quantidade; `i32 @8` = resultado (gate `== 0`); registros `GACHA_PRIZE` a partir de `@0xc` (tamanho do registro (gap)) | (inferido) | L2749–2771 |
| 601 | `NotifyTutorialClear(CS_CLEAR_TUTORIAL_OUT)` | `i32 @0` → +0x38 (iTutorialClear); `i32 @4` → +0x5C (iPoint) | 600 | L2440–2449 (`if (param_1 == 0x259)`) |
| 611 | `NotifyGetGiftItem` | `i32 @0`; `i32 @4` = count; registros de 0x48 a partir de `@8` (`u16 @0` key) | 610 | L1483–1522 |
| 613 | `NotifyGiftItemUsed` | `u16 @0` índice do item, e registro de 0x34 bytes (catálogo `i32` @4); `i32 @0x34` = resultado (gate `== 0`); `i32 @0x38` = chave que o cliente remove do Depósito (`param_2 + 0x38`, L1528–1531) | 612 | L1526–1561 |
| 614 | `NotifyGiftMoratsUsed` | `u16 @0` key; `i32 @0x5c` = resultado (gate `== 0`) e argumento do evento; dados a partir de `@0x60` (gap) | (inferido) | L1564–1605 |
| 616 | `NotifyItemGift` | `i32 @0` = resultado; `i32 @4` → +0x58 (iCash); `i32 @8` → +0x5C (iPoint) | 615 | L1608–1625 |
| 617 | `NotifyGetGift` (sem argumentos) | nenhum campo do corpo é lido (corpo ignorado) | (inferido) | L1626–1629 |
| 643 | `NotifyMatchingGroupList` | (gap) | 642 | L1668–1700 |
| 648 | `NotifyRequestMatch` | (gap) | 644 | L1701–1711 |
| 649 | `NotifyReturnRequestMatch` | (gap) | (inferido) | L1712–1737 |
| 650 | `NotifyAcceptMatch` | (gap) | 645 (inferido) | L1738–1861 |
| 651 | `NotifyRejectMatch` | (gap) | 646 (inferido) | L1862–1865 |
| 652 | `NotifyCancelMatch` | (gap) | 647 (inferido) | L1866–1869 |
| 653 | (sem evento) | (gap) | (inferido) | L1870–1973 |
| 654 | (sem evento) | (gap) | (inferido) | L1974–2076 |
| 656 | `NotifyEndMatch` (ramo com `return`, L2112–2114); senão `goto LAB_10020a0e` (L2116): `NotifyRoomPlayerInfo` (cauda de 317) | (gap) | 655 | L2077–2118 |
| 658 | `NotifyChangeGroupSlot` (guarda `== 0x292`) | (gap) | 657 | L1641–1667 |
| 659 | `NotifyRefreshMatchRoomList` | (gap) | 659 (mesmo valor) | L2119–2154 |
| 660 | `NotifyMatchResult` | (gap) | (inferido) | L2155–2210 |
| 661 | (sem evento; `goto LAB_10021279`) | (gap) | (inferido) | L2211–2296 |
| 662 | (sem evento; `goto LAB_10021279`) | (gap) | (inferido) | L2297–2382 |
| 701 | `NotifyExpelPlayer` | `i32 @0` → `_DAT_1005aa54` | 700 | L2386–2387; L428–431 |
| 900 | `NotifyChargeCash` | `i32 @0` → +0x58 (iCash); só se o nó existe | (inferido) | L2388–2401 |
| 901 | `NotifyChargePremium` | `i32 @0` → +0x94 (premium_end); só se o nó existe | (inferido) | L2402–2415 |
| 902 | `NotifyChargePoint` | `i32 @0` → +0x5C (iPoint); só se o nó existe | (inferido) | L2416–2429 |
| (cauda) | `NotifyClanInsertPlayer` (`LAB_10021279`) | (gap) | alcançada por `goto` de 661 e 662 (inferido) | L2430–2439 |

Blocos sem `case` no dispatcher e sem evento próprio: 452 (resposta de 451, gap).

---

## 4. GS_* (servidor de partida ↔ Channel)

Os handlers ficam em `LM_Engine.dll`, `FUN_1000bcd0` (0x1000bcd0–0x1000bedf). O `LM_Engine` atua como servidor de jogo. Frame: `u16` tamanho @0, cabeçalho @2, corpo @4. Opcode = `hdr >> 5`. O `LM_Engine` recebe cinco opcodes (tratados em `FUN_1000bcd0`) e envia um só (1011, por `FUN_1000bb80`, único chamador da dump, em `FUN_1000bcd0`). Os envios Channel → GS (1002, 1010, 1020) são feitos pelo Channel, fora desta DLL; por isso o conjunto de recepção está fechado para o que o cliente faz, mas a origem dos envios não foi verificada no servidor de 2006-07 (gap).

| op (dec / hex) | Mensagem | Direção | Corpo (resumo) | Semântica | Evidência |
|---|---|---|---|---|---|
| 0 | Debug (`Cdebug::Dump`, string @0x1002d7ec) | Channel → GS | sem corpo | zera `DAT_10056fa4` | `FUN_1000bcd0` (case 0) |
| 1 | Debug (`Cdebug::Dump`, string @0x1002d804) | Channel → GS | sem corpo | só dump | `FUN_1000bcd0` (case 1) |
| 1002 (0x3ea) | Controle de saída | Channel → GS | `i32 @0`; se `== 0`, `GIsRequestingExit = 1` | encerramento do servidor | `FUN_1000bcd0` @0x1000bd79–0x1000bd93 |
| 1010 (0x3f2) | `GS_IN_PLAYER` | Channel → GS | ver §4.1 de `channel_server.md` (corpo 0xa1 bytes mínimo) | adiciona jogador à sala se o room guid bater; responde 1011 | `FUN_1000bcd0` @0x1000be11–0x1000bed5 |
| 1011 (0x3f3) | Resposta de `GS_IN_PLAYER` | GS → Channel | 16 bytes: `i32 @0` resultado (0 ou −4000 = 0xfffff060); `i32 @4` room guid (eco); `i32 @8` chave (eco); `u8 @12` flag (eco); `u8 @13` slot (eco) | N = 18 (`FUN_1000bb80` faz `param_4 + 0x12`) | `FUN_1000bcd0` @0x1000bec7, @0x1000bed0 |
| 1020 (0x3fc) | `GS_OUT_PLAYER` | Channel → GS | `i32 @0` room guid; `i32 @4` chave do jogador | remove o jogador (`CServerRoom::OutPlayer`) se a chave bater; sem resposta | `FUN_1000bcd0` @0x1000bda6–0x1000bdfc; `CServerRoom::OutPlayer` @0x100171c0 |

Aceite: `ServerRoom+0 == body+0x88`, ou `ServerRoom+0x5e4 == 6` e `ServerRoom+0x600 == body+0x88`. Caso contrário, log e `result = -4000` (`channel_server.md` §4.1).

---

## 5. Pares pedido → resposta

Observados no log do cliente (`re/NOTES.md`, `LandMass.log`) ou confirmados no código:
- Message: 100→101, 110→111, 120→121, 130→131 (`message_server.md` §1).
- Channel: sequência observada no log 101, 111, 103 (repetido), 151, 141, 121. Mostra a ordem, não o par (`channel_server.md` §3).

Pareados por +1 ou igual ao pedido, por rótulo e nome (inferido, salvo indicação):
- Message: 140→141, 150→151, 152→153, 160→161/162, 170→171, 171→172, 174→175, 177→178, 190→191, 192→193, 194→195 (cabeçalho de pedido medido; caso de resposta existe no dispatcher; par não observado).
- Channel: 100→101, 120→121, 122→123, 301→302, 311→312, 401→402, 500→501, 545→547, 546→548, 550→551, 555→556 (559 para item de sistema; 557 para morat), 560→554/561/562 (561 na recusa), 570→572 (573 é de skin), 580→582 (581 é de morat, não emitido), 600→601, 610→611, 612→613, 615→616, 642→643, 644→648, 655→656, 657→658, 659→659, 700→701.
- Pares por nome, sem +1 (inferido): 180→183, 182→184, 186→188, 187→189, 645→650, 646→651, 647→652.

Sem par identificado: 451→452 (gap: sem `case 452`); 461 (convite enviado) não tem resposta direta, 463 é convite recebido; 540→541; 542→543; 464→151 (inferido por nome).

---

## 6. Correções aplicadas nesta revisão

1. `re/channel_server.md` §3.2, linha da tabela do opcode 902: a faixa `2416–2451` juntava três eventos. Corrigida para: 902 = `NotifyChargePoint` (2416–2429); cauda `LAB_10021279` = `NotifyClanInsertPlayer` (2430–2439, alcançada por `goto` de 661 e 662); 601 = `NotifyTutorialClear` (2440–2449, `if (param_1 == 0x259)`). A faixa 2440–2449 do 601 e a 2416–2429 do 902 já estavam certas em `channel_server.md` §3.1 e `layouts_f0.md`.
2. Blocos que `channel_server.md` §3.2 marcava como "goto não reatribuído" foram atribuídos pelo parser de rótulos: 617 → `NotifyGetGift` (L1626–1640), 656 → `NotifyEndMatch` (L2077–2118), 658 → `NotifyChangeGroupSlot` (L1641–1667), 643 → `NotifyMatchingGroupList` (L1668–1700), 648–652 (`NotifyRequestMatch` … `NotifyCancelMatch`), 559 → `NotifyGetSystemItemState` + `NotifyItemDestroy`.
3. Message: `message_server.md` §4 descrevia 191, 193 e 195 como "(break)"; o caso é resposta em lote aos pedidos 190, 192 e 194 (par inferido, seção 5).
4. Opcode 641 (0x281): o dispatcher tem a guarda `!= 0x281` (L1481) e não trata 641. Não há evento para 641 (inferido: `RegisterGroup` 640 não tem resposta).
5. Gotos da seção 3.2 reatribuídos pelo corpo do `.c` (não pelo intervalo de linhas): 571 e 572 chamam `NotifyItemUnused` pela cauda `LAB_1001fb03` (L2631–2632); 581 e 582 chamam `NotifyItemExtend` (L2682–2683, 581 por `goto`, 582 por queda); 591 é `NotifyGetGatchaPrize` com `return` em L2771 (o parser havia atribuído a ele gotos de outros blocos); 656 chama `NotifyEndMatch` com `return` (L2112–2114) e, no outro ramo, `goto LAB_10020a0e` (`NotifyRoomPlayerInfo`, cauda de 317).
6. Layouts C→S corrigidos pelos wrappers de `LM_Engine.dll` (`FUN_10017xxx` e `FUN_10023xxx`, mais `FUN_10026810` como roteador): 105 é `u8` + `u8` (não `u16`); 471 é `i32` + `u8` (não `u32` + `u32`); 555, 560, 570 e 580 têm `u16` e bytes zero, não `u32`; 615 tem nick em @6; 700 tem `u8` tipo + nick @1; 451 tem `@0` não inicializado e nick @1 (a linha anterior com '4 dwords' estava errada); 190/192/194 são `u8 count` + ids a partir de @4.
7. Assinaturas de evento (UnrealScript `LM_ServerInterface`, `.u`): 332 `NotifyChangeRoomMaster(int room_guid, int client_guid)`; 342 `NotifyRemoveRoom(int room_guid)`; 462 `NotifyResultRoomInvite(int result)` (recebe o corpo; result = `i32 @0`); 543 `NotifyDetailPlayerInfo(int result, LM_PLAYER_DETAIL_INFO)` (result = erro do envelope `(int)pCVar16`; corpo = `param_2`); 421 `NotifyChangeRoomSlot(int client_guid, byte slot_num)` (confirmada).
8. Duplicatas dos agregados: `+server_interface.dll/channel_helpers.c` e `channel_interface.c`, e `LM_Engine.dll/message_notify_wrappers.c`, são anotações manuais por endereço (não pseudocódigo completo). Os `.c` de `all/` nesses endereços foram mantidos (são o pseudocódigo do lote); o índice `_index.tsv` aponta o agregado na coluna `existing`.
9. Correções medidas em F6 e F7 (dispatcher e wrappers): 556 tem `u16 @2` = gate (não índice); 585 tem `u8 @1` = bItem (não gate); 562 tem o slot em `u16 @6`; 572 tem o slot em `u16 @4`; 582 tem `i32` em @4, @8, @0xc e @0x10 (não `u32`); 570 é `u16` + `u16` (4 bytes) e 580 é `i32` + `u16` + `u8` + `u8` (8 bytes); 573 é de skin e 581 é de morat, e o F6 e o F7 não emitem nenhum dos dois. Layouts consolidados em §9.

---

## 7. Lacunas (aberto)

Fechado nesta revisão: layouts C→S prioritários por wrapper (§3.1 e §2.1), nick/amigo/bloqueio/clã (140, 152, 181, 182, 186, 187, 190, 192, 194); assinaturas de 332, 342, 462, 543; corpos S→C de 104, 554–573, 585–591, 613, 614, 616, 617; goto de 571, 572, 581, 582, 591, 656.

Ordem de prioridade para o próximo ciclo de RE:
1. **Corpos S→C ainda em gap** (coluna Corpo de §3.2, gerada automaticamente nesta revisão): 107, 108, 141, 142, 143, 144, 302, 312, 332, 543, 571, 613 (parcial, §10), 614, 643, 648, 649, 650, 651, 652, 653, 654, 656, 658, 659, 660, 661, 662, (cauda). Os de equipar e destruir (554 a 585) estão medidos desde F6 (§9).
2. **Message 150 (CreateNickname)**: corpo 52+2+1 não decodificado. Ler o wrapper de `/CreateNickname` no roteador `FUN_10026810` (ver `message_server.md` §5.6).
3. **Message 120 (InMessageServer)**: conteúdo do byte opcional (gap).
4. **Channel 543**: nomes dos campos `i32 @0x14..@0x38` e semântica de `u8 @0x34` e do texto `@0x3c` (falta o tipo `LM_PLAYER_DETAIL_INFO` nos `.u`).
5. **Channel 462**: `i32 @0` = result confirmado pelo wrapper; a regra do envelope 0x36 (`0xfffff023`) precisa de captura (inferido).
6. **Channel 332/342**: campos confirmados pela assinatura; a semântica de `sala+0x5c` e de `FUN_1001c990` continua inferida.
7. **Channel 452**: resposta de 451 sem `case` (confirmar em captura).
8. **Channel 850–890 (administração)**: sem resposta no dispatcher.
9. **Conferir offsets de 464, 540, 541, 547 e 548** com `layouts_f0.md` (não conferidos nesta revisão).
10. **Membership** (`Cmembership_interface`): porta e papel não identificados no cliente.
11. **Cresource / Cupdate / Cmanager**: fora desta página (portas 7312 e 7310); `ops_server_interface` existe no dump mas não está consolidado aqui.
12. **Pares observados**: nenhum par de Message além de 100–130 no log. Capturas nas telas de amigos, bloqueio, clã e ranking fechariam as linhas (inferido).
13. **UnrealScript de `WPGames.u` e `Engine.u`**: classes ainda não segmentadas por classe (ver §8).
14. **Bytes não preenchidos pelo cliente**: @0 de RoomExpel (451), @5..@7 de RoomInviteAnswer (471) e @36 de SaveOption (544) saem como lixo de pilha. Confirmar se o servidor de 2006 ignora esses bytes.
15. **Validação no servidor**: o cliente copia nick sem limite (RoomInvite, RoomExpel, ExpelPlayer, GetChannelPlayerDetail, CheckNickname, UpdateNickname, AddFriendList, AddBlackList, ItemGift strNick) e ids sem limite (RefreshFriendList). O emulador deve rejeitar entradas maiores que o campo (inferido).

---

## 8. Mapeamento UnrealScript → native → opcode

Classes `LM_*` dos pacotes `.u` do cliente (fonte embutida, `D:\landmass\cliente\System`). Quem chama o `LM_ServerInterface` (camada que chama `ULM_ServerInterface::*`, que chama `Cchannel_interface::*` / `Cmessage_interface::*`):

| Classe (pacote) | Chamadas ao servidor (UnrealScript) | Opcode (C→S) |
|---|---|---|
| `LM_ServerInterfacePage` (XInterface) | `GetMyPlayerInfo`, `GuidLogin`, `Servers`, `Channels`, `Rooms` (base de 163 referências) | — |
| `LM_LoginPage`, `LM_LoginPanel`, `LM_LoginComponent` (XInterface) | `Login`, `GuidLogin`, `GetLoginGuid` | 100 |
| `LM_TempLoginPage` (XInterface) | `Login`, `InMessageServer` | 100, 120 |
| `LM_NickNameChangePanel`, `LM_NicknameChangePage`, `LM_NicknameSetPage` (XInterface) | `CheckNickname`, `UpdateNickName`, `OutAllServer` | 140, 152 |
| `LM_CreateNickPanel` (XInterface) | `CreateNickName`, `CheckNickname` | 150, 140 |
| `LM_OptionPage` (XInterface) | `SaveOption` | 544 |
| `LM_ChannelMCL`, `LM_ServerMCL`, `LM_ServerChannelPage` (XInterface) | `InChannelServer`, `InChannel`, `OutChannelServer`, `RankPlayers`, `GetChannelServer` | 100, 120, 122 |
| `LM_RoomListPanel`, `LM_RoomMCL`, `LM_RoomPage` (XInterface) | `RefreshRoomList`, `InRoom`, `GetRoomInfoByGUID` | 545, 311 |
| `LM_CreateRoomPage` (XInterface) | `CreateRoom` | 301 |
| `LM_RoomSettingPage` (XInterface) | `ChangeRoomProperty`, `GetMatchGroupInfoList` | 411 |
| `LM_RoomInvitePage` (XInterface) | `RoomInvite`, `GetPlayerList` | 461 |
| `LM_RoomPasswordPage`, `LM_RoomInfoPage` (XInterface) | `InRoom`, `DetailRoomInfo` | 311, 540 |
| `LM_PlayerListPanel`, `LM_PlayerListInvitePanel` (XInterface) | `RefreshPlayerList`, `RefreshFriendList`, `RefreshClanList`, `RefreshBlackList`, `AddFriendList`, `AddBlackList`, `GetDelFriendList`, `GetDelBlackList` | 546, 190, 194, 192, 181, 186, 182, 187 |
| `LM_RoomPlayerListPanel`, `LM_ClanRoomPlayerListPanel` (XInterface) | `AddFriendList`, `AddBlackList`, `GetPlayerInfoList` | 181, 186 |
| `LM_PlayerInfoPage` (XInterface) | `DetailPlayerInfo` | 542 |
| `LM_ChatPanel`, `LM_ChatBasePage` (XInterface) | `SendMsg`, `SendWhisper`, `SendClanMessage` | 240, 160, 177 |
| `LM_RequestMatchPage` (XInterface) | `GetMatchClanInfo`, `GetAcceptMatch`, `GetRejectMatch`, `CancelMatch` | 645–647 |
| `LM_MatchRoomPage`, `LM_MatchingGroupListPage` (XInterface) | `GetMatchGroupInfoList`, `ResetMatchingGroupList`, `GetRequestMatch`, `RoomInvite` | 642, 644 |
| `LM_ClanRoomListPanel`, `LM_ClanRoomMCL`, `LM_ClanGroupMCL` (XInterface) | `RefreshRoomList`, `RefreshMatchRoomList`, `InRoom` | 545, 659 |
| `LM_HangerPage`, `LM_HangerInvenListPanel`, `LM_HangerGateInvenPanel`, `LM_HangerGateInfoPanel` (XInterface) | `GetMoratsInfoByGate`, `GetGiftItem`, `ItemDestroy`, `ItemUnused`, `ChangeMoratsItemID`, `ChangeMoratsGate` | 610, 555, 570 (inferido) |
| `LM_SupplyBuyPopPage`, `LM_HangerBuyItemPopPage`, `LM_HangerBuyMoratsPopPage`, `LM_HangerRenewMoratsPopPage`, `LM_SupplyMoratsBuyPopPage` (XInterface) | `ItemBuy`, `ItemGift`, `ItemExtend` | 550, 615, 580 |
| `LM_ItemRenewPage` (XInterface) | `ExpirationItems`, `ItemDestroy`, `GetSaleItemInfo` | 555 |
| `LM_JoinNestPage` (XInterface) | `ItemUsedByValue`, `SetRegular` | 560, 105 |
| `LM_TutorialCompletePage`, `LM_TutorialEndPage` (XInterface) | `ClearTutorialStep`, `ExitPlayer` | 600, 500 |
| `LM_ChangeMainMoratsPage` (XInterface) | `ChangeMoratsItemID`, `ChangeMoratsGate`, `GetItemClassify` | 560 (mudança de morat principal, inferido) |
| `LM_GatchaPopupPage` (XInterface) | `GetETCItemClassByID` | (local, sem pedido) |
| `LM_DMScoreBoardPage`, `LM_ScoreBoardMCL` (XInterface) | `GetPlayerInfoByName` | (local) |
| `LM_DeathMatch` (XGame) | `Disconnect` | (local) |
| `LM_Pawn`, `LM_PlayerController`, `LM_PlayerReplicationInfo` (Engine) | 43 referências (não mapeadas nesta revisão) | (gap) |
| `LM_TutorialTrigger`, `LM_OperatorTrigger`, `LM_TargetController` (WPGames) | 29 referências (não mapeadas nesta revisão) | (gap) |

Interface nativa: `LM_ServerInterface` (`LM_Engine.u`) declara as `native function` (`GetItemInfo`, `GetRoomInfo`, `GetPlayerInfo`, `GetMyPlayerInfo`, `GetClanInfo`, `GetFriendPlayerInfo` …) e os eventos `NotifyDetailPlayerInfo`, `NotifyRankingInfo`, `NotifyRegister`, `NotifyGetGatchaPrize` que o `ULM_ServerInterface` dispara. Cada `Notify*` UnrealScript corresponde ao evento da seção 3.2 e 2.2.

Nota: o mapeamento de classe a opcode é pelo nome do método UnrealScript, igual ao nome do método C++ (`Cchannel_interface::<nome>` ou `Cmessage_interface::<nome>`). A capitalização difere em `CreateNickName`/`CreateNickname` e `UpdateNickName`/`UpdateNickname`. Os opcodes da coluna da direita são inferidos a partir do nome, exceto quando a tabela §2.1/§3.1 traz o método diretamente. A extração das classes foi feita por varredura de strings do `.u`, sem decompilar o pacote; `WPGames.u` e `Engine.u` têm referências que não foram segmentadas por classe.

---

## 9. Dúvidas 8 e 9 resolvidas: layouts de equipar, destruir e estender (F6, F7)

Resolve as dúvidas 8 (aridade de 570 e 580) e 9 (mapa `item_slot` → slot) de `07-progression.md` §8. Pedidos (C→S) vêm dos wrappers de `LM_Engine.dll`; respostas (S→C) vêm do dispatcher. Confirmar com captura no cliente real.

| Opcode | Sentido | Campos (offset de corpo) | Corpo (bytes) | Fonte |
|---|---|---|---|---|
| 560 | C→S | `u16 index` @0; `u16 gate` @2; `i32 value` @4 (≠ 0 = `ItemUsedByValue`, recusado no F6) | 8 | wrapper `0x100181f0`; `0x10018260` |
| 570 | C→S | `u16 index` @0; `u16 gate` @2 | 4 | wrapper `0x100182e0` |
| 555 | C→S | `i32 id` @0; `u16 index` @4 | 8 (6 usados) | wrapper `0x10018190` |
| 580 | C→S | `i32 id` @0; `u16 index` @4; `u8 point` @6 (1 = LD); `u8 option` @7 | 8 | wrapper `0x10018340` |
| 554 | S→C | registro de 0x34 bytes (102); `u16 slot` @0x34; `i32 result` @0x38 | 60 | L776–808 |
| 556 | S→C | `u16 index` @0; `u16 gate` @2; `u8 mounted` @4; `i32 result` @8 | 12 | L110–170 |
| 557 | S→C | `u16 gate` @0; `i32 result` @4 | 8 | L2452–2468 |
| 559 | S→C | `u16 index` @0; `u16 slot` @2; `u8` 1 @4; `i32 result` @8 | 12 | L2469–2489 |
| 561 | S→C | `i32 result` @8 (sem chave nem registro) | 12 | L2490–2495 |
| 562 | S→C | `u16 gate` @0; `u16 index` @2; `u16 slot` @6; `i32 result` @8 | 12 | L2496–2510 |
| 572 | S→C | `u16 gate` @0; `u16 slot` @4; `i32 result` @8 | 12 | L2602–2615 |
| 582 | S→C | `u16 index` @0; `i32 apply_value` @4; `i32 cash` @8; `i32 point` @0xc; `i32 result` @0x10 | 20 | L2657–2685 |
| 585 | S→C | `u8 premium` @0 (0); `u8 bItem` @1 (1); `u16 index` @2 | 4 | L2686–2704 |

**Dúvida 8 (resolvida).** 570 tem dois valores (`u16` índice e `u16` gate), 4 bytes. 580 tem quatro (`i32` id, `u16` índice, `u8` point, `u8` option), 8 bytes. A medição anterior de `u32` estava errada (§6, item 9).

**Dúvida 9 (resolvida).** `Item_Equip.item_slot` é o índice de `SLOT_NAMES` (`domain/equipment.py`):

| `item_slot` | `slot_name` |
|---|---|
| 0 | `main_weapon` |
| 1 | `sub_weapon` |
| 2 | `melee_weapon` |
| 3, 4, 5 | `etc_weapon_00`, `etc_weapon_01`, `etc_weapon_02` |
| 6 | `booster` |
| 7 | `generator` |
| 8 | `head` |
| 9 | `body` |
| 10 | `arm` |
| 11 | `leg` |
| 12 a 15 | `etc_item_00` a `etc_item_03` (aceitos pelo servidor; o wdb atual só traz 0 a 11) |

O slot de sistema (`sEventSlot[10]`) fica no registro do jogador, em 0x50..0x59 do 101. Vazio é `0xFF`; o índice do item (até `0xFE`) é gravado como byte (inferido).

**Códigos de resultado (inferidos, D68).** -1 sem gate (`NO_GATE`), -3 skin (`SKIN`), -4 genérico (`DENIED`), -7 requisito (`REQUIREMENT`). Os `CERR_*` não têm valor no dump.

## 10. Layouts de pintura, consumo, nest e classe (F15)

Resolve os layouts que faltavam para pintura e consumíveis. Os pedidos (C→S) são 560 e 570, já descritos em §9. As respostas (S→C) vêm do dispatcher `channel_dispatch_FUN_1001da60.c`. Os significados marcados como inferidos pedem captura no cliente real.

| Opcode | Sentido | Campos (offset de corpo) | Corpo (bytes) | Fonte |
|---|---|---|---|---|
| 565 | S→C | `u16 gate` @0; `u16 index` @2 (índice da pintura no inventário, inferido); `u16 k` @4 (slot de `siSkinID`, 0 em F15); `i32 result` @8 | 12 | L2511–2525 |
| 568 | S→C | `u16 index` @0 (item consumido); `i32 result` @4 | 8 | L2529–2571 |
| 569 | S→C | `u16 index` @0 (chave: índice do item, inferido); `u8 nest` @2; `i32 result` @4 | 8 | L2572–2586 |
| 573 | S→C | `u16 gate` @0; `u16 k` @4; `i32 result` @8 | 12 | L2616–2633 |
| 590 | S→C | `u16 index` @0 (chave: índice do item, inferido); `u8 classe` @2; `i32 result` @4 | 8 | L2724–2748 |

**Pintura (565 e 573).** O dispatcher acha o morat pelo `gate` e grava o índice da pintura em `siSkinID[k]`. O 103 leva os três slots de skin em @0x64 (`LM_MORATS_INFO`). Em F15, `k` é 0.

**Consumo (568).** O cliente tira o item da lista ao receber 568 e chama `NotifyItemUsed` (101). Por isso o servidor não manda 556 para consumíveis.

**Nest e classe (569 e 590).** 569 grava `u8` @2 no nó do jogador (+0x30) e tira o item. 590 grava `u8` @2 no nó do morat principal (+0x98) e tira o item. 590 não confere `result`, só o envelope: a recusa da Troca de Função vai por 561.

**Status.** 565, 568, 569, 573 e 590 estão implementados no servidor (F15). Nenhum foi testado no cliente real.

## 11. Presente, Depósito e gacha: layouts da implementação (F10, F11)

Os offsets de 610 a 617 e de 591 em §3.2 batem com o codec de `protocol/gift.py` e `protocol/gacha.py` (testes em `tests/test_gift_codec.py`). Pontos ainda inferidos:

- 611: registro de 0x48 (L1483–1522): `u16` chave @0; catálogo `i32` @0x14, `item_guid` @0x18 e opção `u8` @0x40 seguem a implementação, a confirmar no cliente.
- 613: medido no dispatcher (L1526–1561): registro do item em @0..0x33, resultado em @0x34 e chave em @0x38. A linha de §3.2 estava errada e foi corrigida. Nenhum chamador de 612 foi achado no XInterface (risco 1).
- 616: `i32` resultado @0, Cash @4, LD @8 (L1608–1625). Os códigos de recusa (-2407, -4055, -4056, 8000) são inferidos do `switch` de `NotifyItemGift`.
- 617: corpo ignorado (L1626–1629).
- 610: antes de listar, resgata os pendentes (D100): um 102 por item, e a página sai vazia, salvo o que não coube (count 0).
- 591: o dispatcher lê até dois registros (`while iVar3 < 2`, L2749–2771). O tamanho de 0x110 do registro `GACHA_PRIZE` e o texto UTF-8 NUL de 260 bytes são inferidos.
