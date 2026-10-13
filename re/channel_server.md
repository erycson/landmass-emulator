# Channel Server: protocolo que o cliente entende

Escopo: requisições do cliente ao Channel Server (`+server_interface.dll`, classe `Cchannel_interface`), respostas tratadas pelo dispatcher (`LM_Engine.dll`, `FUN_1001da60`) e mensagens GS_* entre o Channel Server e o servidor de jogo (`LM_Engine.dll`, `FUN_1000bcd0` e `CServerRoom`).

Binários analisados (somente leitura, nada alterado em `cliente\`):
- `cliente\system\LM_Engine.dll`, sha256 `4a08e7cebf2abe31cc1e6d0f73bf7734b58af5ce5cc21474987f0242fd04230f`.
- `cliente\system\+server_interface.dll`, sha256 `18a3b8dc2935b8b811e3fd8e3345c450f7a1d760e5fbed8456168b8715b90c31`.
- `cliente\system\_core_network.dll` (transporte, `CnetworkClient`): não reanalisado aqui; ver `message_server.md` §1 (`GetSendBuff` @0x10007860, `Send` @0x10007A10).

Ghidra 12.1.4 via REA. Pseudocódigo salvo em:
- `re\+server_interface.dll\channel_helpers.c`: 14 helpers de montagem de pacote, `FUN_10001380`..`FUN_10001c20`, com opcode em AX.
- `re\+server_interface.dll\channel_interface.c`: procedimentos de `Cchannel_interface`, com opcode e tamanho N.
- `re\LM_Engine.dll\channel_dispatch_FUN_1001da60.c`: dispatcher de respostas, bruto (2940 linhas). Números `L…` deste documento referem-se a este arquivo.

## 0. Endereços e convenções

Mapa de endereços (imagem base 0x10000000 nas duas DLLs; endereços sem o nome do binário são ambíguos):
- `+server_interface.dll`: `Cchannel_interface::*` em 0x10001000..0x100032e0 (ctor em 0x10003440; 68 procedimentos no total); helpers `FUN_10001380`, `FUN_10001420`, `FUN_100014e0`, `FUN_10001580`, `FUN_10001620`, `FUN_100016e0`, `FUN_10001790`, `FUN_10001830`, `FUN_10001990`, `FUN_100018f0`, `FUN_10001a40`, `FUN_10001ae0`, `FUN_10001b80`, `FUN_10001c20`.
- `LM_Engine.dll`:
  - dispatcher de respostas `FUN_1001da60` (xref da string "Recived from Channel Server %d" @0x10031574 em 0x1001daa6);
  - handler GS `FUN_1000bcd0` (0x1000bcd0..0x1000bedf);
  - enviador GS `FUN_1000bb80`;
  - log `FUN_1000ba20`, com strings @0x1002d754, 0x1002d760, 0x1002d770, 0x1002d788, 0x1002d7b8 (GS) e 0x1002d7ec, 0x1002d804 (debug);
  - `ChannelServerTick` @0x1000bb70; `LogoutChannelServer` @0x1000bb60; `InitServer` @0x1000c6d0;
  - `ServerRoom()` @0x100162a0; `ChannelNetCode()` @0x1000c5e0; `FUN_1000ba90` (devolve o `CnetworkClient`);
  - `CServerRoom::InPlayer` @0x100159a0; `CServerRoom::OutPlayer` @0x100171c0.

Legenda: **(inferido)** = dedução a partir de evidência indireta; **(não decodificado)** = campo ou layout não lido no pseudocódigo; **(gap)** = fora do alcance desta revisão, ver §6.

Convenção de offsets: nas tabelas, `@N` é o offset dentro do **corpo** (depois do cabeçalho u16), como em `message_server.md`. Os helpers e `channel_interface.c` escrevem offsets a partir do início do buffer, com cabeçalho em +0; conversão: offset de buffer − 2 = offset de corpo. As tabelas já usam offset de corpo.

Os ponteiros `CS_*_OUT` são tipados com 1 byte, então `param_2[N]` e `param_2 + N` são offsets em bytes (confirmado pelo uso `*(int*)(param_2 + 4)`, `param_2[0x5d]`).

## 1. Framing, cabeçalho e net_code

| Item | Valor | Evidência |
|---|---|---|
| Frame TCP | `u16 LE` tamanho (exclui os 2 bytes) + corpo | igual ao Message (`message_server.md` §1); `re/NOTES.md` |
| Cabeçalho | `u16 LE = (opcode << 5) \| net_code` | `channel_helpers.c` (cabeçalho dos helpers: `(net & 0x1f) \| (AX << 5)`); `FUN_1000bb80` @0x1000bb80 (`param_1 & 0x1f \| in_AX << 5`) |
| `net_code` Channel | `14` (`:CHANNEL net_code[1-31]`) | `cliente\system\config.ini`; `Cchannel_interface::Init` @0x10001140 |
| `time_out` Channel | `20000` (unidade não confirmada) | `config.ini`; `Cchannel_interface::Init` @0x10001140 |
| Filtro de net_code (GS) | aceita se `(hdr & 0x1f) == 0` ou `== ChannelNetCode()` | `FUN_1000bcd0` @0x1000bcd9–0x1000bcf3 (`TEST [EDI+2],0x1f`; `CALL 0x1000c5e0`; `CMP`) |
| Envio | `CnetworkClient::GetSendBuff(N)` devolve o início do cabeçalho; `N` = cabeçalho + corpo (inclui os 2 bytes) | `channel_helpers.c`; `message_server.md` §1 |
| Retorno do envio | `0` se `CnetworkClient::Send` devolveu não zero; `-10` se zero (sucesso = 0, inferido); `-0xb` se `GetSendBuff` devolveu NULL | `FUN_1000bb80` @0x1000bb80: `return (-(uint)(iVar1 != 0) & 10) - 10` |

Tamanho `N` nos helpers: `N = body ? tail_len + K : 2`, com `K` = 2 + tamanho fixo do corpo.

## 2. Requisições do cliente ao Channel (`Cchannel_interface`)

Direção: todas as linhas desta seção são C→S (cliente → Channel). Struct: tipo entre parênteses, na coluna método. Colunas: opcode (decimal) | método (endereço) | helper (AX) | N | corpo (offsets de corpo) | evidência (`channel_interface.c`, linha). `lit` = literal de cabeçalho passado no método (`LIT=0x...`; opcode = LIT >> 5). `p?k:2` = `N = k` se o ponteiro `p` não for nulo, senão 2.

Métodos sem opcode (não são requisições): `Init` 0x10001140, `Connect` 0x100012d0, `Disconnect` 0x10001330, `Tick` 0x10001350, `IsConnect` 0x10001130, `Ping` 0x10001370, ctor 0x10003440, `operator=` 0x10001000. Total de procedimentos: 68. Requisições com opcode: 60.

| op | método (endereço) | helper (AX) | N | corpo | evidência |
|---|---|---|---|---|---|
| 2 | `SendHeartbeat` (0x100027a0) | lit 0x40 | 2 | — | L77 |
| 62 | `LoginServerMonitor(nome, porta, extra)` (0x10001ce0) | `FUN_10001380`, AX=0x3e | 34 | 32 bytes fixos: `nome[16]` @0; `u16 porta` @16; `extra[14]` @18 (distribuição inferida) + tail | L113–115 |
| 64 | `RequestSubChannnelInfo` (0x10001d90) | lit 0x800 | 2 | — | L35 |
| 66 | `SendLobbySpecInfo(u32 a, bool b)` (0x10001df0) | lit 0x840 | 10 | `u32 a` @0; `u32 b` @4 (bool como dword) | L43 |
| 67 | `RequestRoomList(int a)` (0x10001e70) | lit 0x860 | 6 | `i32 a` @0 | L45 |
| 68 | `RegisterChannelServer(char *p17)` (0x10002240) | `FUN_10001420`, AX=0x44 | 19 | 17 bytes: 4 dwords (@0,@4,@8,@12) + `u8` @16 | L117 |
| 72 | `RequestForceUserQuit(char *p17)` (0x100022a0) | `FUN_10001420`, AX=0x48 | 19 | 17 bytes (igual a 68) | L118 |
| 100 | `InChannelServer(CS_IN_CHANNEL_SERVER_IN *p)` (0x10002360) | `FUN_100014e0`, AX=0x64 | 35 | 33 bytes: 8 dwords (@0..@31) + `u8` @32 | L120 |
| 105 | `SetRegular(CS_SET_REGULAR_IN *p)` (0x10002960) | lit 0xd20 | p?4:2 | `u16` @0 | L82–83 |
| 120 | `InChannel(CS_IN_CHANNEL_IN *p)` (0x10002390) | lit 0xf00 | p?6:2 | `u32` @0 (primeiro dword de `*p`) | L59–60 |
| 122 | `OutChannel()` (0x10002410) | lit 0xf40 | 2 | — | L62 |
| 240 | `SendMsg(CS_SEND_MESSAGE_IN *p, char *texto)` (0x100027f0) | `FUN_10001790`, AX=0xf0 | len+4 | `u16` @0 (`p[0..1]`); texto a partir de @2, `len = p[1]` bytes | L135–137 |
| 250 | `SendCommand(CS_SEND_COMMAND_IN *p, char *texto, int idx)` (0x10002820) | `FUN_10001790`, AX=0xfa | len+4 | igual a 240 | L139–140 |
| 301 | `CreateRoom(CS_CREATE_ROOM_IN *p)` (0x10002470) | `FUN_10001580`, AX=0x12d | 76 | 74 bytes: 18 dwords (@0..@71) + `u16` @72 | L122 |
| 311 | `InRoom(CS_IN_ROOM_IN *p)` (0x100024a0) | `FUN_10001620`, AX=0x137 | 22 | 20 bytes: 5 dwords | L123 |
| 321 | `OutRoom()` (0x100024d0) | lit 0x2820 | 2 | — | L64 |
| 401 | `ReadyGame(CS_READY_GAME_IN *p)` (0x100026c0) | lit 0x3220 | p?3:2 | `u8` @0 | L72–73 |
| 411 | `ChangeRoomProperty(CS_CHANGE_ROOM_PROPERTY_IN *p)` (0x10002530) | `FUN_100016e0`, AX=0x19b | 12 | 10 bytes: `u32` @0, `u32` @4, `u16` @8 | L124 |
| 420 | `ChangeRoomSlot(CS_CHANGE_ROOM_SLOT_IN *p)` (0x10002560) | lit 0x3480 | p?3:2 | `u8` @0 | L66–67 |
| 451 | `RoomExpel(CS_ROOM_EXPEL_IN *p)` (0x100025e0) | `FUN_10001830`, AX=0x1c3 | 20 | 18 bytes: 4 dwords (@0..@12) + `u16` @16 | L125; `FUN_10001830` (`puVar2[9]`, byte 18 do buffer = corpo @16) |
| 461 | `RoomInvite(CS_ROOM_INVITE_IN *p)` (0x10002610) | `FUN_10001420`, AX=0x1cd | 19 | 17 bytes (igual a 68) | L126 |
| 464 | `GetChannelPlayerInfo()` (0x10002db0) | lit 0x3a00 | 2 | — | L94 |
| 471 | `RoomInviteAnswer(CS_ROOM_INVITE_ANSWER_IN *p)` (0x10002640) | lit 0x3ae0 | p?10:2 | `u32` @0, `u32` @4 | L69–70 |
| 500 | `ExitPlay()` (0x10002740) | lit 16000 (0x3e80) | 2 | — | L75 |
| 540 | `GetChannelRoomDetail(CS_CHANNEL_ROOM_DETAIL_IN *p)` (0x10002880) | lit 0x4380 | p?10:2 | `u32` @0, `u32` @4 | L79–80 |
| 542 | `GetChannelPlayerDetail(CS_CHANNEL_PLAYER_DETAIL_IN *p)` (0x10002900) | `FUN_10001420`, AX=0x21e | 19 | 17 bytes (igual a 68) | L127 |
| 544 | `SaveOption(_OPTION_INFO *p)` (0x10002930) | `FUN_100018f0`, AX=0x220 | 39 | 37 bytes: 9 dwords (@0..@35) + `u8` @36 | L128 |
| 545 | `RefreshRoomList(CS_REFRESH_ROOM_LIST_IN *p)` (0x10002c10) | `FUN_10001a40`, AX=0x221 | 46 | 44 bytes: 11 dwords | L129 |
| 546 | `RefreshPlayerList(CS_REFRESH_PLAYER_LIST_IN *p)` (0x10002c40) | `FUN_10001ae0`, AX=0x222 | 66 | 64 bytes: 16 dwords | L130 |
| 550 | `ItemBuy(CS_ITEM_BUY_IN *p)` (0x100029e0) | `FUN_10001990`, AX=0x226 | 14 | 12 bytes: 3 dwords | L131 |
| 555 | `ItemDestroy(CS_ITEM_DESTROY_IN *p)` (0x10002a10) | lit 0x4560 | p?10:2 | `u32` @0, `u32` @4 | L85 |
| 560 | `ItemUsed(CS_ITEM_USED_IN *p)` (0x10002a90) | lit 0x4600 | p?10:2 | `u32` @0, `u32` @4 | L86 |
| 570 | `ItemUnused(CS_ITEM_UNUSED_IN *p)` (0x10002b10) | lit 0x4740 | p?6:2 | `u32` @0 | L87 |
| 580 | `ItemExtend(CS_ITEM_EXTEND_IN *p)` (0x10002b90) | lit 0x4880 | p?10:2 | `u32` @0, `u32` @4 | L88 |
| 586 | `InHangar()` (0x10002cf0) | lit 0x4940 | 2 | — | L92 |
| 588 | `OutHangar()` (0x10002d50) | lit 0x4980 | 2 | — | L93 |
| 600 | `ClearTutorial(CS_CLEAR_TUTORIAL_IN *p)` (0x10002c70) | lit 0x4b00 | p?3:2 | `u8` @0 | L90 |
| 610 | `GetGiftItem(CS_GET_GIFTITEM_IN *p)` (0x100031e0) | lit 0x4c40 | p?6:2 | `u32` @0 | L108 |
| 612 | `GiftItemUsed(CS_GIFTITEM_USED_IN *p)` (0x10003260) | lit 0x4c80 | p?6:2 | `u32` @0 | L109 |
| 615 | `ItemGift(CS_ITEM_GIFT_IN *p)` (0x100032e0) | `FUN_10001c20`, AX=0x267 | 26 | 24 bytes: 6 dwords | L133 |
| 640 | `RegisterGroup()` (0x10002e10) | lit 0x5000 | 2 | — | L96 |
| 642 | `GetMatchingGroup()` (0x10002e70) | lit 0x5040 | 2 | — | L97 |
| 644 | `RequestMatch(CS_REQUEST_MATCH_IN *p)` (0x10002ed0) | lit 0x5080 | p?10:2 | `u32` @0, `u32` @4 | L99 |
| 645 | `AcceptMatch(CS_REQUEST_MATCH_IN *p)` (0x10002f50) | lit 0x50a0 | p?10:2 | igual a 644 | L100 |
| 646 | `RejectMatch(CS_REQUEST_MATCH_IN *p)` (0x10002fd0) | lit 0x50c0 | p?10:2 | igual a 644 | L101 |
| 647 | `CancelMatch(CS_REQUEST_MATCH_IN *p)` (0x10003050) | lit 0x50e0 | p?10:2 | igual a 644 | L102 |
| 655 | `EndMatch()` (0x100030d0) | lit 0x51e0 | 2 | — | L104 |
| 657 | `ChangeGroupSlot(CS_CHANGE_ROOM_SLOT_IN *p)` (0x10003130) | lit 0x5220 | p?3:2 | `u8` @0 | L106 |
| 659 | `RefreshClanMatchInfo(CS_REFRESH_CLAN_MATCH_INFO_IN *p)` (0x100031b0) | `FUN_10001b80`, AX=0x293 | 42 | 40 bytes: 10 dwords | L132 |
| 700 | `ExpelPlayer(CS_EXPEL_PLAYER_IN *p)` (0x10002850) | `FUN_10001830`, AX=0x2bc | 20 | 18 bytes (igual a 451) | L142 |
| 850 | `RequestLoadChannelServer()` (0x10001ee0) | lit 0x6a40 | 2 | — | L47 |
| 851 | `RequestLoadMessageServer()` (0x10001f40) | lit 0x6a60 | 2 | — | L48 |
| 852 | `RequestLoadServerManager()` (0x10002060) | lit 0x6a80 | 2 | — | L51 |
| 860 | `RequestUnloadChannelServer()` (0x10001fa0) | lit 0x6b80 | 2 | — | L49 |
| 861 | `RequestUnloadMessageServer()` (0x10002000) | lit 0x6ba0 | 2 | — | L50 |
| 862 | `RequestUnloadServerManager()` (0x100020c0) | lit 0x6bc0 | 2 | — | L52 |
| 870 | `RequestRebootSystem()` (0x100021e0) | lit 0x6cc0 | 2 | — | L55 |
| 880 | `RequestLoadGameServerManager()` (0x10002120) | lit 0x6e00 | 2 | — | L53 |
| 881 | `RequestUnloadGameServerManager()` (0x10002180) | lit 0x6e20 | 2 | — | L54 |
| 890 | `RequestGameServerInfo()` (0x10002300) | lit 0x6f40 | 2 | — | L56 |

Nota: `LoginServerMonitor` descreve o corpo de 32 bytes como `nome[16] ; u16 porta ; extra[14]` (L114). A posição exata de `extra` em @18 é inferência. Revisão: os 60 opcodes foram conferidos nos bytes de `+server_interface.dll` (imediato do opcode ou literal presente no método, e `CALL` para o helper quando houver); os offsets e tamanhos `N` dos 14 helpers foram conferidos no pseudocódigo REA, com correção do offset de `FUN_10001830` (linhas 451 e 700).

## 3. Respostas do Channel (`FUN_1001da60`)

Entrada: `FUN_1001da60(ushort opcode, CS_IN_CHANNEL_SERVER_OUT *body)`, com `body` = corpo (offset 0). Revisão: `channel_dispatch_FUN_1001da60.c` coincide com o pseudocódigo REA do mesmo endereço (`diff -w`: só o cabeçalho de 4 linhas difere; o REA tem 2936 linhas).

Envelope de erro, opcode `0x36` (54), L96–108: `u16 @0` = opcode real; `i32 @4` = código de erro. Se o erro for ≠ 0, chama `ULM_ServerInterface::NotifyErrorMessage(erro)`. Em seguida, o dispatch continua com o opcode real sobre o **mesmo** buffer (corpo real sobreposto ao envelope, inferido).

Opcodes 0, 1 e 2 (locais, L809–852):
- `0`: `NotifyConnectChannelServer()`; zera `DAT_1005ada0` e reinicia listas.
- `1`: `NotifyDisconnectChannelServer(0)`.
- `2`: `Cchannel_interface::SendHeartbeat()`. Ao receber 2 do servidor, o cliente responde com 2. Diferente do Message, que não responde (`message_server.md` §3).
- `default`: retorna sem efeito.

### 3.1 Respostas com layout lido (opcodes exigidos)

Direção: todas as linhas desta seção são S→C (Channel → cliente). Colunas: op | evento (`ULM_ServerInterface::Notify*`) | struct (nome no cast) | layout (corpo) | semântica | evidência (`dispatch` L…).

| op | evento | struct | layout (corpo) | semântica | evidência |
|---|---|---|---|---|---|
| 101 | `NotifyInChannelServer` | `CS_IN_CHANNEL_SERVER_OUT` | `i32 @0xa8` = resultado; com resultado 0: `i32 @0x90` → `DAT_1005ada0`, `i32 @0xac` → `_DAT_1005ae08`, 168 bytes (0x2a dwords) do corpo @0 copiados para um nó novo (`FUN_1001d5d0`) | resultado 0: registra o nó e `DAT_1005ada4 = timeGetTime()`. Resultado ∉ {0, −0x17, −0x1a} recebe o erro do envelope 0x36 quando este é −0x1d ou −0x1e (inferido) | L853–882 |
| 103 | `NotifyGetMorats` | `CS_GET_MORATS_OUT` | `i16 @0` = chave (`*(short*)param_2`); `u8 @0x5d` ≠ 0 zera `i32 @0x30`; 92 bytes (0x17 dwords) copiados para o registro novo de `FUN_1001d7f0` quando a chave **não** é encontrada (ramo `== fim da lista`) | insere registro novo se a chave não existir (L919–930); notifica sempre | L901–933 |
| 111 | `NotifyChannelInfo` | — | `u8 @0` = `count`; `count` iterações chamam `FUN_1001c170`; tamanho da entrada não decodificado | reset (`FUN_10024560`) e depois uma entrada por iteração; `FUN_1001c170` recebe só o objeto de lista devolvido por `FUN_100230a0()` (REA: parâmetro único; insere um nó via `FUN_10019640`; o corpo não é passado a ela; globais lidos por `FUN_10019640` não verificados) (L981–989) | L978–992 |
| 121 | `NotifyInChannel` | — | `i32 @0` = id; `i32 @0 < 0`: erro via `FUN_10021c80((short)_DAT_1005aa88)`; `i32 @0 >= 0`: busca o nó pela chave do corpo (`FUN_10007830`); se não achar, cria nó (`FUN_1001d5d0`) com 168 bytes zerados (inferido) e preenche: `i32 @0` → +0xa0; `i32 @4` → +0x3c; `u8 @0x19` → +0x23; `u8 @0x1a` → +0x21; `u8 @0x24` → +0x30; +0xb0 = 0x22; `i32 @0x1c` → +0x28; `i32 @0x20` → +0x2c; `i32 @8` → +0x10; `i32 @0xc` → +0x14; `i32 @0x10` → +0x18; `i32 @0x14` → +0x1c; `u8 @0x18` → +0x20 | entra no canal; `NotifyInChannel()` sem argumento; guarda `_DAT_1005aa88 = i32 @0` | L2772–2824 (label `switchD_1001db47_caseD_79`) |
| 123 | `NotifyOutChannel` (ramo de 0x7b) | `CS_OUT_CHANNEL_OUT` | `i32 @0` = id; o gate `i32 @0 >= 0` controla só a atualização da lista; `i32 @0` → `_DAT_1005aa68` | ramo por igualdade com `DAT_1005ada0` (inferido: canal atual × outros); `NotifyOutChannel` é chamado fora do gate | L807 (`if (param_1 != 0x7b)`), L997–1037 (L993 é o `goto` de 0x79) |
| 141 | `NotifyChannelRoomInfo` | — | `u16 @0` = `count`; entradas a partir de `@2` (passo não decodificado) | `count` iterações (corpo de cada iteração não decodificado) | L1039–1081 |
| 151 | `NotifyChannelPlayerInfo` | — | `u16 @0` = `count`; entradas a partir de `@0x1b` (passo não decodificado) | `count` iterações (`u16 @0` e `@0x1b` confirmados em L1189–1190) | L1147–1245 |
| 241 | `NotifySendMsg` | `CS_SEND_MESSAGE_OUT` | `u8 @5` = `len`; texto a partir de `@8`; ramo `len > 0x78` não decodificado | repassa o texto ao evento | L1246–1280 |
| 251 | `NotifySendCommand` | `CS_SEND_COMMAND_OUT` | `u8 @0` = comando; texto a partir de `@1` | repassa ao evento | L1281–1311 |
| 302 | `NotifyCreateRoom` | — | corpo passado a `FUN_1001d640` (inserção de sala; layout não decodificado: gap) | insere a sala e notifica (dois ramos com `NotifyCreateRoom`) | L1312–1347 |
| 312 | `NotifyInRoom` | — | `i32 @0` = resultado; `i32 @0 < 0`: erro, código `i16 @0` via `FUN_10021c80`, copia `u8 @8..@0x0e` → nó `+0x48..+0x4e` e `i16 @0x10` → `+0x50`, e escreve -1 em `i32 @4` e `i32 @8` (inferido: marca o registro inválido); ramo de sucesso não decodificado (gap); envelope 0x36 com erro `0xfffff04b` retorna sem notificar | ramo de erro e cauda comum (`LAB_1001e74b`) chamam `NotifyInRoom` | L1348–1349 (`case 0x138`), L2858–2934 (label `switchD_1001e098_caseD_138`; cauda `LAB_1001e74b`; `NotifyInRoom` @L2935; polaridade `i32 @0 < 0` = erro confirmada em L2863) |
| 314 | `NotifyRoomInfo` | — | chave de busca do nó: corpo a partir de @0x0c (tipo não decodificado; `FUN_10019e90`); cabeçalho: `i16 @0` → +0x54; `u8 @2..@4` → +0x56..+0x58; `i32 @8` → +0x5c; a partir de `@0x0c`: `u8 @0x10` → +0x48, `@0x11` → +0x49, `@0x12` → +0x4a, `@0x13` → +0x4d, `@0x14` → +0x4e; `i16 @0x16` → +0x50; `i32 @0x2c` → +0x178; `i32 @0x30` → +0x17c; `i16 @0x34` → +0x180; `i16 @0x36` → +0x182 | preenche o nó da sala e chama `NotifyRoomInfo` | L1350–1388 |
| 317 | `NotifyRoomPlayerInfo` | — | `u8 @0` = `count` (laço `< (byte)*param_2`); `i32 @1` = chave de busca; antes do laço a lista é consultada por `DAT_1005ada0` (definido por 101) via `FUN_10007830`; registros de 0x30 bytes, com `B = 0x1a + 0x30·i`: `i32 @(B-0x19)` → +0xa0; `i32 @(B-0x15)` → +0x3c; `u8 @B` → +0x23; `u8 @(B+1)` → +0x21; `u8 @(B+0x0b)` → +0x30; `i32 @(B+3)` → +0x28; `i32 @(B+7)` → +0x2c; `i32 @(B+0x13)` → +0xb4; `u8 @(B+0x12)` → +0x90; `u8 @(B+0x10)` = flag (bit0 com +0xac); `u8 @(B+0x11)` define +0xb0 (0x23, ou 0x25 se ≠ 0, ou 0x24 pela condição de flag); `i32 @(B-0x11)` → +0x10; `i32 @(B-0xd)` → +0x14; `i32 @(B-9)` → +0x18; `i32 @(B-5)` → +0x1c; `u8 @(B-1)` → +0x20; `u8 @(B+0x0f)` = índice de inserção (`piVar22[idx + 0x14]`) | atualiza ou insere o registro do jogador (`FUN_1001d640`) e notifica | L1389–1473 (cauda `LAB_10020a0e`; `NotifyRoomPlayerInfo` @L1474) |
| 322 | `NotifyOutRoom` | `CS_OUT_ROOM_OUT` | `i32 @0` → `_DAT_1005aa74` (lido); corpo passado ao evento | sai da sala | L173–248 |
| 342 | `NotifyRemoveRoom` | `CS_REMOVE_ROOM_OUT` | layout não decodificado; corpo passado ao evento | remove a sala | L285–298 |
| 402 | `NotifyReadyGame` | `CS_READY_GAME_OUT` (cast) | se o envelope 0x36 não tem erro (`pCVar16 == 0`): busca o nó pelo corpo (`FUN_10007830`), testa `FUN_10018aa0` e, se verdadeiro, chama `FUN_1001d640` sobre `nó+0xa4`; `u8 @4` = flag: bit0 → `+0xac` (XOR); `i32 @8` → `+0xb4`; `+0xb0` = 0x24 se `u8 @4` ≠ 0 e `registro+0x38` == 1, = 0x23 se `u8 @4` = 0, sem alteração nos demais casos (inferido); demais campos não decodificados | `NotifyReadyGame(corpo, erro do envelope)`; `_DAT_1005aa84 = 0` | L2825–2853 (label `switchD_1001ea5b_caseD_192`; cauda `LAB_1001f06d` em L2852) |
| 403 | `NotifyStartGame` | `CS_START_GAME_OUT` | `i32 @0`, `i32 @4`, `i32 @8`, `i32 @0xc` → `_DAT_1005ac34..40`; `i16 @0x10` → `_DAT_1005ac44` (18 bytes lidos) | inicia a partida | L301–346 |
| 404 | `NotifyReadyGameError` | — | sem leitura de corpo | erro de "pronto" | L347–351 |
| 412 | `NotifyChangeRoomProperty` | — | `u8 @4` = máscara: bit0 → `i16 @6`; bit1 → `u8 @8`, `u8 @9`; bit2 → `u8 @10`; bit3 → `i16 @0xc`; bit4 → `u8 @0xb`; bit5 → `u8 @0xf`; bit6 → `u8 @0xe` | atualiza só os campos marcados | L352–381 |
| 421 | `NotifyChangeRoomSlot` | — | layout não decodificado | troca de slot | L382–406 |
| 462 | `NotifyResultRoomInvite` | — | passado raw; layout não decodificado | resultado do convite | L407–415 |
| 463 | `NotifyRoomInvite` | `CS_ROOM_INVITE_OUT` | `i32 @0` → `DAT_1005aa90` (lido); corpo passado ao evento; `FUN_1001d640` insere o nó | convite recebido | L416–423 |
| 501 | `NotifyExitPlay` | — | `i32 @0` → `_DAT_1005aa58`; passado como `int` | saída da partida | L424–427 |
| 701 | `NotifyExpelPlayer` | — | `i32 @0` → `_DAT_1005aa54`; mesmo código de 501 a partir do `goto switchD_10020b72_caseD_2bd` | expulsão | L2386–2387; L428–431 |
| 512 | `NotifyGameResult` | `CS_GAME_RESULT_OUT` | `i32 @0` (comparado com `DAT_1005ada0`); `i32 @4` → `+0x3c`; `i32 @8` → `+0x5c`; `i16 @0xc`; `i32 @0x10` → `+0x40` | atualiza o resultado | L432–487 |
| 541 | `NotifyDetailRoomInfo` | — | `i16 @0` → `+0x54`; `u8 @2..@4` → `+0x56..+0x58`; `i32 @8` → `+0x5c`; `i16 @0x18`, `@0x1a`, `@0x1c` limitados a 0 se < 1 e regravados (inferido: padrão de `@0x1c`); zeros em `@0x00..0x27` em um ramo (não decodificado) | informações detalhadas da sala | L488–534 |
| 543 | `NotifyDetailPlayerInfo` | `PLAYER_INFO_DETAIL` | passado raw; layout não decodificado | detalhes do jogador | L535–540 |
| 547 | `NotifyChangeRoomProperty` (lista) | — | `u8 @0` = `count`; entradas a partir de `@8` (passo não decodificado) | lista de salas (inferido pelo layout; resposta a 545) | L541–576 |
| 548 | `NotifyChangePlayerProperty` (lista) | — | `u8 @0` = `count`; entradas a partir de `@8` (passo não decodificado) | lista de jogadores (inferido pelo layout; resposta a 546) | L577–607 |
| 549 | `NotifyInRoom` | — | `i32 @0` → `+0xa0`; `i32 @4` → `+0x3c`; `i32 @8`, `@0xc`, `@0x10`, `@0x14` → `+0x10..+0x1c`; `i32 @0x1c` → `+0x28`; `i32 @0x20` → `+0x2c`; `u8 @0x19` → `+0x23`; `u8 @0x1a` → `+0x21`; `u8 @0x24` → `+0x30`; `u8 @0x29` bit0 (XOR com `+0xac`); `i32 @0x2c` → `+0xb4`; `u8 @0x2b` → `+0x90` | entra na sala e preenche o nó; `u8 @0x28` = índice do jogador na sala: `i32 @0` gravado em `sala + 0x60 + 4·idx` (`sala` = `local_89c`, obtida por `FUN_10019e90` na lista de `FUN_10023500`, L670–673; escrita em L675); contador `sala+0x4b` se `idx < 0x3c`, senão `sala+0x4c` (L677–681) | L608–691 |
| 54 (0x36) | `NotifyErrorMessage` | — | `u16 @0` = opcode real; `i32 @4` = erro | envelope de erro (§3) | L96–108 |

### 3.2 Apêndice: todos os rótulos do switch

Valores em decimal. Evento = `Notify*` do bloco (do rótulo até o próximo). Blocos fora do `switch` principal: por label `goto` — 121 (`caseD_79`), 312 (`caseD_138`), 402 (`caseD_192`), 701 (`caseD_2bd`, alcançado por `goto` em L2387); por guarda `if` — 123 (`!= 0x7b`, L807), 317 (`!= 0x13d`, bloco em L1386 em diante), 556 (`== 0x22c`, L110). Blocos com goto ainda não reatribuídos por label: 0x22f (559), 0x269 (617), 0x290 (656), 0x386 (902) e os blocos com `goto LAB_1002xxxx` (ver §6). O bloco 0x24f (591) é delimitado em §3.2 pela linha de `NotifyGetGatchaPrize`.

| op | evento (bloco) | linhas (.c) |
|---|---|---|
| 0 | `NotifyConnectChannelServer` | 809–830 |
| 1 | `NotifyDisconnectChannelServer` | 831–845 |
| 2 | `SendHeartbeat` | 846–849 |
| 101 | `NotifyInChannelServer` (ver §3.1) | 853–882 |
| 102 | `NotifyGetItem` | 883–900 |
| 103 | `NotifyGetMorats` (ver §3.1) | 901–933 |
| 104 | `NotifySetRegular` | 934–937 |
| 107 | `NotifyGetTrainingMorats` | 938–960 |
| 108 | `NotifyMoratsCreated` | 961–977 |
| 111 | `NotifyChannelInfo` (ver §3.1) | 978–992 |
| 121 | `NotifyInChannel` (ver §3.1) | 2772–2824 (label `switchD_1001db47_caseD_79`) |
| 123 | `NotifyOutChannel` (ver §3.1) | 997–1037 (ramo de 0x7b, guarda L807) |
| 141 | `NotifyChannelRoomInfo` (ver §3.1) | 1039–1081 |
| 142 | `NotifyMatchRoomInfo` | 1082–1110 |
| 143 | `NotifyMatchRoomInsert` | 1111–1128 |
| 144 | `NotifyMatchRoomDelete` | 1129–1143 |
| 151 | `NotifyChannelPlayerInfo` (ver §3.1) | 1147–1245 |
| 241 | `NotifySendMsg` (ver §3.1) | 1246–1280 |
| 251 | `NotifySendCommand` (ver §3.1) | 1281–1311 |
| 302 | `NotifyCreateRoom` (ver §3.1) | 1312–1347 |
| 312 | `NotifyInRoom` (ver §3.1; label `switchD_1001e098_caseD_138`) | 1348–1349; 2858–2934 |
| 314 | `NotifyRoomInfo` (ver §3.1) | 1350–1388 |
| 317 | `NotifyRoomPlayerInfo` (ver §3.1; cauda `LAB_10020a0e`) | 1389–1473 |
| 322 | `NotifyOutRoom` (ver §3.1) | 173–248 |
| 323 | `NotifyDisconnectChannelServer` | 249–252 |
| 332 | `NotifyChangeRoomMaster` | 256–284 |
| 342 | `NotifyRemoveRoom` (ver §3.1) | 285–298 |
| 402 | `NotifyReadyGame` (ver §3.1; label `switchD_1001ea5b_caseD_192`) | 299–300; 2825–2853 |
| 403 | `NotifyStartGame` (ver §3.1) | 301–346 |
| 404 | `NotifyReadyGameError` | 347–351 |
| 412 | `NotifyChangeRoomProperty` (ver §3.1) | 352–381 |
| 421 | `NotifyChangeRoomSlot` | 382–406 |
| 462 | `NotifyResultRoomInvite` | 407–415 |
| 463 | `NotifyRoomInvite` (ver §3.1) | 416–423 |
| 501 | `NotifyExitPlay` (ver §3.1) | 424–427 |
| 512 | `NotifyGameResult` (ver §3.1) | 432–487 |
| 541 | `NotifyDetailRoomInfo` (ver §3.1) | 488–534 |
| 543 | `NotifyDetailPlayerInfo` (ver §3.1) | 535–540 |
| 547 | `NotifyChangeRoomProperty` (lista, ver §3.1) | 541–576 |
| 548 | `NotifyChangePlayerProperty` (ver §3.1) | 577–607 |
| 549 | `NotifyInRoom` (ver §3.1) | 608–691 |
| 551 | `NotifyItemBuy` | 692–719 |
| 552 | `NotifyMoratsBuy` | 720–748 |
| 553 | `NotifyItemUsedGate` | 749–775 |
| 554 | `NotifyItemUsedSystem` | 776–808 |
| 556 | `NotifyItemDestroy` (if de 0x22c) | 110–170 |
| 557 | `NotifyMoratsDestroy` | 2452–2468 |
| 559 | `NotifyGetSystemItemState`, `NotifyItemDestroy` | 2469–2489 |
| 561 | `NotifyItemUsed` | 2490–2495 |
| 562 | `NotifyItemUsed` | 2496–2510 |
| 565 | `NotifyItemUsed` | 2511–2525 |
| 566 | `NotifyItemUsed` | 2526–2528 |
| 567 | `NotifyItemUsed` | 2529–2555 |
| 568 | `NotifyItemUsed` | 2556–2571 |
| 569 | `NotifyChangeNest` | 2572–2586 |
| 571 | (sem Notify no bloco) | 2587–2601 |
| 572 | (sem Notify no bloco) | 2602–2615 |
| 573 | `NotifyItemUnused` | 2616–2633 |
| 581 | (sem Notify no bloco) | 2634–2656 |
| 582 | `NotifyItemExtend` | 2657–2685 |
| 585 | `NotifyItemEndtime` | 2686–2704 |
| 587 | `NotifyEnterHanger` | 2705–2712 |
| 589 | `NotifyLeaveHanger` | 2713–2723 |
| 590 | `NotifyItemUsedChangeMainMorats` | 2724–2748 |
| 591 | `NotifyGetGatchaPrize` (L2767) | 2749–2771 (a partir de L2772 o código pertence aos labels 121, 402 e 312) |
| 611 | `NotifyGetGiftItem` | 1483–1522 |
| 613 | `NotifyGiftItemUsed` | 1526–1563 |
| 614 | `NotifyGiftMoratsUsed` | 1564–1607 |
| 616 | `NotifyItemGift` | 1608–1625 |
| 617 | `NotifyGetGift`, `NotifyRegisterGroup`, `NotifyChangeGroupSlot` (blocos misturados) | 1626–1667 |
| 643 | `NotifyMatchingGroupList` | 1668–1697 |
| 648 | `NotifyRequestMatch` | 1701–1711 |
| 649 | `NotifyReturnRequestMatch` | 1712–1737 |
| 650 | `NotifyAcceptMatch` | 1738–1861 |
| 651 | `NotifyRejectMatch` | 1862–1865 |
| 652 | `NotifyCancelMatch` | 1866–1869 |
| 653 | (sem Notify no bloco) | 1870–1973 |
| 654 | (sem Notify no bloco) | 1974–2076 |
| 656 | `NotifyEndMatch` | 2077–2118 |
| 659 | `NotifyRefreshMatchRoomList` | 2119–2154 |
| 660 | `NotifyMatchResult` | 2155–2210 |
| 661 | (sem Notify no bloco) | 2211–2296 |
| 662 | (sem Notify no bloco) | 2297–2382 |
| 701 | `NotifyExpelPlayer` (ver §3.1) | 2386–2387 |
| 900 | `NotifyChargeCash` (`i32 @0` → `local+0x58` se `FUN_10018aa0` ≠ 0) | 2388–2401 |
| 901 | `NotifyChargePremium` | 2402–2415 |
| 902 | `NotifyChargePoint`, `NotifyClanInsertPlayer`, `NotifyTutorialClear` | 2416–2451 |

Pareamento pedido/resposta: somente o log e o código observados; o resto é inferido.
- Sequência observada (`re/NOTES.md`, fluxo do Channel): 101, 111, 103 (repetido), 151, 141, 121. Mostra a ordem, não o par.
- Pares por rótulo de switch e nome do evento, valor +1 ou igual ao pedido (inferido): 100→101 (`InChannelServer`), 120→121 (`InChannel`/`NotifyInChannel`), 122→123 (`OutChannel`/`NotifyOutChannel`), 301→302 (`CreateRoom`), 311→312 (`InRoom`/`NotifyInRoom`), 401→402 (`ReadyGame`/`NotifyReadyGame`), 500→501 (`ExitPlay`), 550→551 (`ItemBuy`), 555→556 (`ItemDestroy`), 560→561 (`ItemUsed`), 545→547 e 546→548 (listas, pelo layout).
- 659 é usado como pedido (`RefreshClanMatchInfo`) e como resposta (`NotifyRefreshMatchRoomList`), com o mesmo valor nos dois sentidos (observado no código).
- Os demais pares não foram confirmados.

## 4. Mensagens GS_* (Channel ↔ servidor de jogo)

Estes handlers ficam em `LM_Engine.dll` e processam mensagens recebidas quando o `LM_Engine` atua como servidor de jogo (`InitServer` conecta ao Channel com `ch_ip`/`ch_port`, `re/NOTES.md`). A direção é inferida: o Channel envia `GS_IN_PLAYER` e `GS_OUT_PLAYER`; o `LM_Engine` responde a `GS_IN_PLAYER`.

Evidência geral: `FUN_1000bcd0` @0x1000bcd0..0x1000bedf. Frame: `u16` tamanho @0, cabeçalho @2, corpo @4. Opcode = `hdr >> 5`.

| op (dec / hex) | mensagem | direção | corpo / layout | semântica | evidência |
|---|---|---|---|---|---|
| 1002 (0x3ea) | controle de saída | Channel → GS | `i32 @0`; se `== 0`, `GIsRequestingExit = 1` | pedido de encerramento do servidor | `FUN_1000bcd0` @0x1000bd79–0x1000bd93 |
| 0 (0x00) | debug (`Cdebug::Dump`, string @0x1002d7ec) | entrada | sem corpo | zera `DAT_10056fa4` | `FUN_1000bcd0` @0x1000bd4d–0x1000bd76 |
| 1 (0x01) | debug (`Cdebug::Dump`, string @0x1002d804) | entrada | sem corpo | só dump | `FUN_1000bcd0` @0x1000bd26–0x1000bd4a |
| 1010 (0x3f2) | `GS_IN_PLAYER` (log "OnRecv(GS_IN_PLAYER)", @0x1002d770) | Channel → GS | ver §4.1 | adiciona o jogador à sala se o room guid bater; responde 1011 | `FUN_1000bcd0` @0x1000be11–0x1000bed5 |
| 1011 (0x3f3) | resposta de `GS_IN_PLAYER` | GS → Channel | ver §4.2 | resultado 0 ou −4000 (0xfffff060) | `FUN_1000bcd0` @0x1000bec7 (`MOV EAX, 0x3f3`), @0x1000bed0 (`CALL FUN_1000bb80`) |
| 1020 (0x3fc) | `GS_OUT_PLAYER` (logs "Succeed/Failed OnRecv[GS_OUT_PLAYER…]", @0x1002d788, @0x1002d7b8) | Channel → GS | `i32 @0` = room guid; `i32 @4` = chave do jogador | remove o jogador da sala se a chave bater (`CServerRoom::OutPlayer` @0x100171c0: compara `body+4` com `this+0x4bc+4·i`, laço `i < 0x46`, e passa o registro de 17 bytes do slot a `UServerLevel::DestroyPlayer`; `FUN_1000bcd0` compara só `body+0` com a sala); sem resposta | `FUN_1000bcd0` @0x1000bda6–0x1000bdfc; `CServerRoom::OutPlayer` @0x100171c0 |

Regra de aceitação do Channel: `(hdr & 0x1f)` deve ser 0 ou igual a `ChannelNetCode()` (= 14). Outros valores são descartados (`FUN_1000bcd0` @0x1000bcd9–0x1000bcf3).

### 4.1 `GS_IN_PLAYER` (1010), corpo

Offsets em bytes a partir do início do corpo (frame @4). Evidências: `FUN_1000bcd0` e `CServerRoom::InPlayer` @0x100159a0.

| @ | tamanho | campo | uso | evidência |
|---|---|---|---|---|
| 0x00..0x83 | 132 bytes (33 dwords) | dados do jogador (não decodificado) | copiados para `this + slot*0x90 + 0x604` por `CServerRoom::InPlayer` | `InPlayer` @0x100159a0 (laço de 0x21 dwords) |
| 0x84 | `u8` | flag (não decodificado) | eco no reply @12 | `FUN_1000bcd0` @0x1000be1b (`MOV CL,[ESI+0x84]`) |
| 0x85 | `u8` (signed, `(char)`) | índice do slot `s` (0..69 inferido do laço de `OutPlayer`, `i < 0x46`; `InPlayer` e `FUN_1000bcd0` não verificam o limite) | `this + s*0x11 + 0x13` (registro de 17 bytes), `this + s*4 + 0x4bc`, `this + s*0x90 + 0x604` | `InPlayer` @0x100159a0 (`(char)param_1[0x85]`); `FUN_1000bcd0` @0x1000be31 |
| 0x88 | `i32` | room guid | comparado com `ServerRoom+0x00`; se `ServerRoom+0x5e4 == 6`, também com `ServerRoom+0x600` | `FUN_1000bcd0` @0x1000be21, @0x1000be4d–0x1000be74 |
| 0x8c | `i32` | chave do jogador | guardado em `this + s*4 + 0x4bc`; usado como chave em `GS_OUT` | `InPlayer` @0x100159a0; `FUN_1000bcd0` @0x1000be27 |
| 0x90..0x9f | 4 dwords (16 bytes) | registro do jogador (string, inferido) | registro de 17 bytes junto com `@0xa0`; passado como `char*` a `UServerLevel::DestroyPlayer` (em `OutPlayer`) e como `%s` no log | `InPlayer` @0x100159a0 (`+0x90..+0x9c`); `OutPlayer` @0x100171c0 |
| 0xa0 | `u8` | último byte do registro (17 bytes) | `this + s*0x11 + 0x13 + 0x10` | `InPlayer` @0x100159a0 (`pCVar3[0x10]`) |

Tamanho mínimo do corpo: 0xa1 bytes (inferido: maior offset lido).

Validação (`FUN_1000bcd0` @0x1000be46–0x1000be74): aceita se `ServerRoom+0 == body+0x88`, ou se `ServerRoom+0x5e4 == 6` e `ServerRoom+0x600 == body+0x88`. Caso contrário, log @0x1002d760 com o registro de @0x90, `result = 0xfffff060` (−4000), e reply.

### 4.2 Reply de `GS_IN_PLAYER` (1011), corpo de 16 bytes

Enviado por `FUN_1000bb80(net=ChannelNetCode(), body=16 bytes, tail=NULL, tail_len=0)`, com `AX = 0x3f3` (`FUN_1000bcd0` @0x1000bec7). Frame = 18 bytes (`N = 0x12`: `FUN_1000bb80` @0x1000bb80 faz `iVar1 = param_4 + 0x12`).

| @ (corpo) | tamanho | campo | origem |
|---|---|---|---|
| 0 | `i32` | resultado: 0 (ok) ou 0xfffff060 (−4000) | `local_10` |
| 4 | `i32` | room guid (eco de body+0x88) | `local_c` |
| 8 | `i32` | chave do jogador (eco de body+0x8c) | `local_8` |
| 12 | `u8` | flag (eco de body+0x84) | `local_4` |
| 13 | `u8` | slot (eco de body+0x85) | `local_3` |
| 14..15 | — | não escritos (inferido: bytes da pilha) | — |

Layout de pilha (inferido de `MOV [ESP+…]`): `local_10` @+0, `local_c` @+4, `local_8` @+8, `local_4` @+12, `local_3` @+13 no buffer de reply.

## 5. Resumo do protocolo do Channel para o cliente

- Cabeçalho: net_code 14 (`config.ini`). Frame com `u16` de tamanho, sem criptografia.
- Pedidos: 60 opcodes com layout (§2).
- Respostas: 84 rótulos de switch e o envelope 0x36 (§3); layout lido para 101, 103, 111 (contagem), 121, 123, 141 e 151 (contagem), 241, 251, 312 (parcial), 314, 317, 322, 402 (parcial: `u8 @4`, `i32 @8`), 403, 412, 463, 501, 512, 541 (parcial), 549, 701 e 0x36.
- GS: 1010, 1011, 1020 e controle 1002 (§4).

## 6. Lacunas

1. **Labels e gotos**: a atribuição de evento por intervalo de linhas (§3.2) está errada onde há goto. Exemplos: `goto LAB_10020a0e` (L2116, cauda de `NotifyRoomPlayerInfo`), `goto LAB_10021279` (L2233–2380), `goto LAB_1001fdb3` (L2555), `goto LAB_1001fb03` (L2601, L2615). A reatribuição por label está concluída só para 121, 123, 312, 317, 402 e 701. Os blocos 0x22f, 0x24f, 0x269, 0x290 e 0x386 seguem com atribuição aproximada.
2. **Layouts não decodificados**: entradas de 111 (`FUN_1001c170`), passo das entradas de 141, 151, 547 e 548 (a partir de @8 em 547/548), registro de sala de 302 e 314 (bytes além dos lidos), 342, 421, 462 e 543 (passados raw), 541 (zeros em @0x00..0x27, ordem em relação às leituras ambígua).
3. **Caminho de entrada do Channel**: quem chama `FUN_1001da60` e o tratamento de net_code/cabeçalho das respostas não foram analisados. Só o log (@0x10031574, xref @0x1001daa6) foi confirmado. O envelope 0x36 é inferido do código, não do transporte.
4. **Pareamento pedido/resposta**: só a sequência do log (`re/NOTES.md`) é observada; os demais pares da §3 são inferidos por rótulo e nome do evento.
5. **`LoginServerMonitor`**: distribuição de `extra[14]` no corpo de 32 bytes é inferida.
6. **GS**: `FUN_1000bcd0` não tem chamador identificado nos binários. `InitServer`, `LogoutChannelServer` e `ChannelServerTick` não são importados por nenhum host (`re/NOTES.md`), então o caminho de entrada GS é só estático.
7. **Tempo**: `_DAT_10056fa8` (ms desde o último envio) e `DAT_1005ada4` (timestamp de 101) não têm finalidade protocolar confirmada.
8. **Corpo real sob o envelope 0x36**: não confirmado se o corpo real começa em @0 do mesmo buffer (sobreposição com o envelope). O pseudocódigo indica que sim (inferido).
