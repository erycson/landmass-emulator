# Message Server: protocolo que o cliente entende

Escopo: respostas do Message Server (opcodes 0, 1, 101..195 do callback) e requisições 100/110/120/130/140/150/152/160/170/180/181/190/192/194 que o cliente envia (§1).
Binários analisados (somente leitura): `cliente\system\LM_Engine.dll` (sha256 `4a08e7ce…fd04230f`), `+server_interface.dll` (`18a3b8dc…b90c31`), `_core_network.dll` (`8dbbba00…c46b83b`). Ghidra 12.1.4 via REA (SHA-256 reconferidos nesta revisão). Dumps UnrealScript: `LM_Engine.u`, `XInterface.u` (strings UTF-16).
Pseudocódigo salvo em `re\LM_Engine.dll\message_dispatch_FUN_10025120.c` e `re\LM_Engine.dll\message_notify_wrappers.c`.

`message_notify_wrappers.c` é um trecho resumido (NotifyRegister e NotifyInMessageServer não são saída completa do Ghidra). O comentário `NAO le result` de `NotifyInMessageServer` é **falso**: o wrapper lê `[EAX]` (`i32 @0` = `result`) em 0x10003a53/0x10003a58 de `LM_Engine.dll` e o passa ao evento.

**Endereços por binário** (verificados nesta revisão; endereços iguais em DLLs diferentes são ambíguos sem este mapa):
- `LM_Engine.dll`: dispatcher `FUN_10025120` @0x10025120; wrappers `ULM_ServerInterface::Notify*` @0x100020f0 a 0x10003a20 (`NotifyUpdateNickname` @0x10002350); `execGetChannelServerInfo` @0x10007C70; blocos do switch de `FUN_10025120`: índice por opcode (byte) em `0x10025D7C`, alvo em `0x10025D18` (dword), padrão = entrada 24 (`0x10025D02`).
- `+server_interface.dll`: `Cmessage_interface::*` (`Init` @0x10003940, `Login` @0x10003D90, `Register` @0x10003DC0, `InMessageServer` @0x10003E10, `CheckNickname` @0x10003E80, `CreateNickname` @0x10003EA0, `GetChannelServerInfo` @0x10003F20, `SendHeartbeat` @0x10004230, `GetFriendList` @0x100040C0, `AddFriendList` @0x10004110, `RefreshFriendList` @0x10004320); helpers `FUN_10003B10` (Login) e `FUN_10003CE0` (CheckNickname, AddFriendList); `UpdateNickname` @0x10004280, `SendWhisper` @0x10003F70, `GetRankingInfo` @0x10003FA0, `RefreshBlackList` @0x100042A0, `RefreshClanList` @0x100043A0; helper `0x10003BA0` (SendWhisper).
- `_core_network.dll`: `CnetworkClient::GetSendBuff` @0x10007860, `DispatchRecv` @0x10008040, `OnRecv` @0x10001D80, vtable base @0x100102C4; `OVERLAPPED_IO::SetBuffer` @0x10005310, `CnetworkClient::Send` @0x10007A10, `CnetworkClient::OnConnect` @0x10007D30.

Legenda: **(não confirmado)** = não reproduzido no binário nesta revisão; **(inferido)** = dedução a partir de evidência indireta.
Convenção: `@0xNN` = offset do campo dentro do **corpo** (depois do cabeçalho u16). Itens sem evidência de código estão marcados como "(inferido)".

## 1. Framing e cabeçalho

| Item | Valor | Evidência |
|---|---|---|
| Frame TCP | `u16 LE` tamanho (exclui os 2 bytes) + corpo | `re/NOTES.md`; **lado de envio confirmado** (decompilação, `_core_network.dll`): `OVERLAPPED_IO::SetBuffer` @0x10005310 grava `*(short*)buf = param_1` e devolve `buf+2`; `CnetworkClient::GetSendBuff` @0x10007860 devolve esse ponteiro (início do cabeçalho u16); `CnetworkClient::Send` @0x10007A10 só marca o flag e chama `SetEvent`, sem prefixo. `param_1` = cabeçalho + corpo (ex.: Login `param_4 + 0x2e`). Não verificado: a rotina de `send` no socket |
| Cabeçalho do corpo | `u16 LE = (opcode << 5) \| net_code` | ver abaixo |
| `net_code` Message | `13` (`:MESSAGE net_code[1-31]`) | `system\config.ini`; `Cmessage_interface::Init` @0x10003940 lê `net_code[1-31]` para DAT_10016504 |
| `time_out` Message | `20000` (unidade **não confirmada**) | `config.ini`; `Cmessage_interface::Init` @0x10003940 lê `time_out` para DAT_1001650c |
| Resposta | opcode da resposta = opcode do pedido + 1. **Troca observada** (log real, `re/NOTES.md` linha 36): 100→101, 110→111, 120→121, 130→131. **Par sem troca observada (inferido)**: 140→141, 150→151, 190→191, 152→153, 170→171, 192→193, 194→195; os pedidos têm cabeçalho medido (ver abaixo) e os casos de resposta existem no dispatcher. **160 não é par +1**: 161 vai ao destinatário ("whisper recebido") e 162 é o erro devolvido ao remetente (inferido); 178 (chat de clã) segue o mesmo padrão (inferido). **Não confirmado** para GetFriendList (180): a lista de amigos chega em 183 (`NotifyFriendList`); 181 e 182 não têm caso no dispatcher | `FUN_10025120` (cases 0x65–0xc3), `re/NOTES.md` linha 36; cabeçalhos dos pedidos abaixo |

Evidência por pedido (valor escrito no cabeçalho; `FUN_10003b10` e `FUN_10003ce0` fazem `(in_AX << 5) | (net & 0x1f)`, confirmado; os demais pedidos têm o valor literal):
- Register (110): `*p = (net & 0x1f) | 0xdc0` (0xdc0 = 110<<5) @0x10003dc0.
- InMessageServer (120): `0xf00` (120<<5) @0x10003e10.
- GetChannelServerInfo (130): `0x1040` (130<<5) @0x10003f20.
- SendHeartbeat (2): `0x40` (2<<5) @0x10004230.
- CreateNickname (150): `0x12c0` (150<<5) @0x10003ea0.
- Login (100): `MOV EAX,0x64` antes de `CALL 0x10003b10` em `Cmessage_interface::Login` @0x10003d90 (100<<5).
- CheckNickname (140): `MOV EAX,0x8c` antes de `CALL 0x10003ce0` em `Cmessage_interface::CheckNickname` @0x10003e80 (140<<5).
- GetFriendList (180): `OR EBX,0x1680` @0x100040c0 (`0x1680` = 180<<5); corpo nenhum (`GetSendBuff(2)`). **Não é 182.**
- AddFriendList (181): `MOV EAX,0xb5` antes de `CALL 0x10003ce0` @0x10004110; corpo fixo de 17 bytes; cabeçalho `0x16A0 | net`.
- RefreshFriendList (190): `OR EBX,0x17c0` @0x10004320 (`0x17C0` = 190<<5); corpo de 60 bytes (15 dwords) ou vazio se a lista for nula.
- UpdateNickname (152): `MOV EAX,0x98` @0x1000428e antes de `CALL 0x10003ce0` @0x10004293, em `Cmessage_interface::UpdateNickname` @0x10004280 (helper confirmado).
- SendWhisper (160): `MOV EAX,0xa0` @0x10003f84 antes de `CALL 0x10003ba0` @0x10003f89, em `Cmessage_interface::SendWhisper` @0x10003f70. O helper `0x10003ba0` faz `(EAX << 5) \| (net & 0x1f)` (@0x10003bd7–0x10003bda, confirmado). Tamanho total = `len + 0x16`, com `len` = `u16 @0x12` da entrada (@0x10003f74); corpo = 20 bytes fixos + `len` bytes.
- GetRankingInfo (170): `OR EBX,0x1540` @0x10003fc2 (`0x1540` = 170<<5) em `Cmessage_interface::GetRankingInfo` @0x10003fa0; tamanho 2 (`PUSH 0x2` @0x10003fa7), sem corpo.
- RefreshBlackList (192): `OR EBX,0x1800` @0x100042d7 (`0x1800` = 192<<5) em `Cmessage_interface::RefreshBlackList` @0x100042a0; corpo de 60 bytes (`MOVSD.REP`, 0xf dwords) se o parâmetro não for nulo; tamanho 0x3e ou 2.
- RefreshClanList (194): `OR EBX,0x1840` @0x100043d7 (`0x1840` = 194<<5) em `Cmessage_interface::RefreshClanList` @0x100043a0; mesmo formato de 192.

Tamanho total do buffer passado a `GetSendBuff` (inclui os 2 bytes do cabeçalho):
- Sem corpo: 2.
- Login (`FUN_10003b10`, `param_4` = id_len + pw_len): `param_4 + 0x2e` (0x2e = 2 + 44).
- CheckNickname (`FUN_10003ce0`, corpo fixo): 0x13 = 2 + 17.
- CreateNickname: 0x39 = 2 + 55.
- InMessageServer: 2 sem parâmetro; 3 com 1 byte de corpo.

## 2. Callback de recepção

- `Cmessage_interface::Init` @0x10003940 grava o callback `void(ushort, char*, ushort)` em `DAT_10016500`. O objeto `CnetworkClient` fica em `DAT_10016518`, 0x18 bytes após `DAT_10016500` (mesmo bloco de estado do Message, **inferido**).
- `Cmessage_interface::Tick` @0x10003b00 chama `CnetworkClient::DispatchRecv` (`_core_network`) @0x10008040.
- `DispatchRecv` retira um item da fila e chama `vtable[3](buf, len | flag<<16)`, ou seja `this+0x0c` (`_core_network` @0x10008040). Confirmado: `(**(code**)(*this+0xc))(buf, len)`; o buffer é liberado quando o byte de flag é 0.
- A vtable base `CnetworkClient` (`_vftable_` @0x100102c4) tem slot 3 = `CnetworkClient::OnRecv` @0x10001d80, que está **vazio** (retorna sem fazer nada). Confirmado por `read_bytes` em 0x100102D0 e pela decompilação.
- Consequência: o parse do cabeçalho e a chamada do callback estão em um override de `OnRecv` que **não foi localizado** (ver lacunas, seção 8).

Relação entre os argumentos do callback (evidência indireta, `LM_Engine` FUN_10025120):
- **arg1 (`ushort`) = opcode, já sem `net_code`** (confirmado no dispatcher): `MOVZX ESI,word ptr [EBP+8]` @0x10025133 alimenta `CMP ESI,0xc3` e a string de log `"Recived from Message Server %d"` (@0x10025147). Os case labels são 0x65, 0x6f, 0x79, 0x83, ... (= 101, 111, 121, 131). Sequência observada em `re/NOTES.md` linha 36 (`Message: 0 → 101 → 111 → 121 → 131`). O parse do cabeçalho fica no override de `OnRecv`, não localizado (§8). Se arg1 fosse o `u16` cru, os valores seriam (opcode<<5)|13, por exemplo 0xCAD para 101.
- **arg2 = ponteiro para o corpo, depois dos 2 bytes do cabeçalho** (inferido): os offsets de todos os `MS_*_OUT` são lidos a partir de 0 do corpo (ex.: result i32 @0 em 121, 141, 151, 153). O lado de envio usa a mesma convenção (struct começa em `buf+2`, `FUN_10003b10`: `puVar4 = puVar2 + 1`).
- **arg3 = comprimento do corpo** (inferido): o dispatcher não o usa; só `whisper` (161/162) lê o próprio campo de comprimento.
- Heartbeat: o dispatcher não tem caso 3. Resposta ao Heartbeat (2) não é necessária para o cliente (inferido, `default: goto switchD_..._caseD_2` retorna sem efeito).

## 3. Dispatcher de respostas

`FUN_10025120` @0x10025120 (3061 bytes), chamado pelo callback. Trata `param_1` como opcode:
- `0` = conectado: chama `NotifyConnectMessageServer`, zera `_DAT_1005b198`.
- `1` = desconectado: chama `NotifyDisconnectMessageServer`.
- `default` = retorna sem efeito.
- Após o `switch`, nos casos que não retornam, `NotifyChangePlayerProperty` é chamado com um bloco zerado (efeito de propriedade do jogador; não relevante para o protocolo).
- Referência de log: `"Recived from Message Server %d"` @0x10031748, xref em 0x10025147 (dentro de `FUN_10025120`, antes do `switch` em 0x10025169). Logo, registra todo callback, inclusive o evento 0 local. A string `"Recived from Channel Server %d"` @0x10031574 é usada em `FUN_1001da60` (Channel, fora do escopo).

## 4. Respostas do Message Server (tabela)

Colunas: opcode | evento UnrealScript | struct (nome do Ghidra) | layout byte a byte do corpo | semântica | evidência

Nomes de struct: os de `LM_Engine.dll` aparecem como string (`MS_LOGIN_OUT`, `MS_REGISTER_OUT`, `MS_IN_MESSAGE_SERVER_OUT`, `MS_CHECK_NICKNAME_OUT`, `MS_CREATE_NICKNAME_OUT`, `MS_SEND_WHISPER_OUT`, `MS_SEND_WHISPER_ERROR_OUT`, `MS_RANKING_INFO_OUT`, `MS_GET_CLAN_MEMBER_OUT`, `MS_GET_BLACK_LIST_OUT`, `MS_DEL_*_OUT`). `MS_GET_CHANNEL_SERVER_OUT` e `MS_GET_CLAN_LIST_OUT` **não aparecem nos binários** (nome atribuído pela análise). Os `MS_*_IN` aparecem em `+server_interface.dll`.

| op | evento (LM_Engine.u) | struct | layout (corpo) | semântica no cliente | evidência |
|---|---|---|---|---|---|
| 0 | `NotifyConnectMessageServer()` | — | sem corpo | evento **local**: `CnetworkClient::OnConnect` @0x10007D30 (`_core_network`) monta um buffer de 4 bytes `02 00 00 00` (`MOV word [EBX],0x2`; `MOV word [EBX+2],DI`, com DI=0) e o passa a `0x100086D0` numa struct com len=4 e flag=0 (@0x10007D94, @0x10007E01). **Leitura (inferido)**: quadro sintético `[u16 len=2][u16 header=0]` (opcode 0, net 0), coerente com o framing da §1; a fila chega ao callback com opcode 0 (`re/NOTES.md` linha 48); limpa estado. **Risco (inferido, depende do override de `OnRecv`, §8.2)**: um frame do servidor com opcode 0 cairia no mesmo caso | `FUN_10025120` case 0; wrapper @0x100020f0 (confirmado) |
| 1 | `NotifyDisconnectMessageServer()` | — | sem corpo | evento **local** (origem não verificada no `_core_network`; não é pacote do servidor). `OutAllServer()`; `bRegistered=false`; `LM_LoginPage` só é aberta se a página ativa não for `LM_Intro` nem `LM_LoginPage`. **Risco (inferido, mesmo caveat de §8.2)**: opcode 1 de servidor dispara o mesmo caso | `FUN_10025120` case 1; wrapper @0x10002120; XInterface `NotifyDisconnectMessageServer` |
| 101 | `NotifyLogin(bool forced_login, int result)` | `MS_LOGIN_OUT` | `u8 @0` → `forced_login`; `i32 @4` → `result`; demais bytes não lidos | `result==0` → cliente chama `Register()` (110); `result!=0` → `bRegistered=false`. Se `result == DAT_1005b1c0` o dispatcher zera `result` antes do evento | `FUN_10025120` case 0x65; wrapper `NotifyLogin` @0x10002150 (copia `byte @0` e `int @4`); XInterface `NotifyLogin` |
| 111 | `NotifyRegister(LM_REGISTER_INFO)` | `MS_REGISTER_OUT` | `@0x00..0x24` = 37 bytes = `LM_REGISTER_INFO` (ver §4.1); `@0x25..0x45` = 33 bytes copiados para `DAT_1005AE20` (sem leitor identificado); `i32 @0x48` = `result` | `result` **é** campo `int result` de `LM_REGISTER_INFO` (UnrealScript, após os 37 bytes). Lookup de mensagem é chamado se `result < 0`, **inclusive para -500**, passado como -500 (`CMP EAX,0xfffffe0c` @0x10025238). Para `result >= 0` não há lookup | `FUN_10025120` case 0x6f; wrapper @0x10002190 (copia 37 bytes; `local_4 = *(int*)(p+0x48)`) |
| 121 | `NotifyInMessageServer(int result, string nickname, int clan_code)` | `MS_IN_MESSAGE_SERVER_OUT` | `i32 @0` = `result`; `char nickname[17] @4..@0x14` (inferido; `@4..@0x13` copiados para `_DAT_1005AD60..6C` como 4 dwords quando `result==0`; `@0x14` → `DAT_1005AD70`, sem leitor identificado); nickname = string ANSI até NUL dentro de `@4..@0x14` (máx. 16 caracteres; sem NUL, o `strlen` do wrapper lê `@0x15..`); `i32 @0x18` = `clan_code` | `result==0`: guarda nickname e clan; UI chama `GetClanList/GetClanMember` (se `clan_code>0`), `GetFriendList`, `SetName(nickname)`. `result!=0`: lookup de mensagem | `FUN_10025120` case 0x79; wrapper `NotifyInMessageServer` @0x10003a20 (converte `param+4` com `MultiByteToWideChar(CP_ACP)`; `clan` de `+0x18`); XInterface `NotifyInMessageServer` |
| 131 | `NotifyChannelServerInfo(bool bRandom)` | `MS_GET_CHANNEL_SERVER_OUT` (**nome não encontrado no binário**) | `u8 @0` = `count`; `u8 @1` → `bRandom`; entradas de 72 bytes em `@2 + 72·i` (i < count; corpo = 2 + 72·count bytes) | esvazia a lista global; insere `count` nós, cada um com cópia verbatim de 72 bytes da entrada i; chama `NotifyChannelServerInfo(bRandom)`; `_DAT_1005b180 = count`; UI chama `GetChannelServerInfo(idx)` em seguida | `FUN_10025120` case 0x83 (`MOV AL,[EBX]` count @0x100253c1; `LEA EDI,[EBX+2]` @0x100253b2; loop @0x100253d0; `ADD EDI,0x48` @0x100253e1); `FUN_10024c10(this, val)` @0x10024c10; `FUN_10024700` (copia 18 dwords de val) @0x10024700; wrapper @0x10002390 |
| 141 | `NotifyCheckNickname(int result)` | `MS_CHECK_NICKNAME_OUT` | `i32 @0` = `result` | `result==0` vira `0x27D8` (10200 = "Nome disponível") para o lookup; `DAT_1005b184 = result` | `FUN_10025120` case 0x8d; wrapper @0x100022d0 |
| 151 | `NotifyCreateNickname(int result)` | `MS_CREATE_NICKNAME_OUT` | `i32 @0` = `result` | `result!=0` → lookup de mensagem. UI: `result==0` → `InMessageServer()` (120) | `FUN_10025120` case 0x97; wrapper @0x10002310; XInterface `NotifyCreateNickname` |
| 153 | `NotifyUpdateNickname(int result)` | `MS_CREATE_NICKNAME_OUT` | `i32 @0` = `result` | `result != 0` → lookup de mensagem (como 151), **sem** gravar `DAT_1005b1a8`; a reação da UI (`NotifyUpdateNickname`) não foi lida | `FUN_10025120` case 0x99 (linhas 152–157 do `.c`); bloco = alvo `0x10025379` (índice `0x08` em `0x10025D7C+0x99`); a única escrita em `DAT_1005b1a8` (`MOV [0x1005b1a8],EAX` @0x10025361) fica no bloco 0x97 (alvo `0x1002533C`); `NotifyUpdateNickname` (wrapper e XInterface não lidos) |
| 161 | `NotifySendWhisper(string sender, string msg)` | `MS_SEND_WHISPER_OUT` | `u16 @0x12` = `len` (se `len > 0x78` descarta); texto `len` bytes @0x14, NUL-terminado | chamada nativa `FUN_10022040(0xd, 0, "\n[%s]%s\n")` passa só o texto, sem remetente; a impressão final no chat depende do `NotifySendWhisper` do UnrealScript **(não confirmado)** | `FUN_10025120` case 0xa1; remetente em `@0x00..0x11` **(inferido)** |
| 162 | `NotifySendWhisperError(int result, string receiver, string msg)` | `MS_SEND_WHISPER_ERROR_OUT` | `i32 @0` = `result`; `u16 @0x16` = `len`; texto @0x18 | `_DAT_1005b1a0 = result`; lookup de `0x27D9` (10201, "falhou ao receber a mensagem") | `FUN_10025120` case 0xa2 |
| 171 | `NotifyRankingInfo(LM_PLAYER_INFO[])` | `MS_RANKING_INFO_OUT` | entradas de `0x20` bytes a partir de **`@0`** (não `@4`): `i32 @0` = índice; `u16 @4` = result (0 encerra); nick NUL a partir de `@6` (vazio encerra); `i32 @0x18` = iTotalExp e `u16 @0x1c` = siClan (inferido pela UI); máximo 100 (constante do loop) | contagem do despacho não é repassada; o wrapper `0x10003e30` converte para `LM_PLAYER_INFO[]` (`re/LM_Engine.dll/NotifyRankingInfo_0x10003e30.c`) | `FUN_10025120` case 0xab; `NotifyRankingInfo` 0x10003e30 |
| 172 | `NotifyGetClanList()` | `MS_GET_CLAN_LIST_OUT` (**nome não encontrado no binário**) | não decodificado | insere em `DAT_1005ada0` | `FUN_10025120` case 0xac |
| 173 | `NotifyDelClan()` | `MS_DEL_CLAN_INFO_OUT` | `i32 @0`: usado como teste de erro (`!= 0`) **e** como chave de comparação com o campo `+0x28` dos membros (papel duplo, **não confirmado**) | marca membros com `+0x28 == @0` como `-1`; remoção do clã não confirmada (`FUN_10007830`, `FUN_10022350`) | `FUN_10025120` case 0xad |
| 175 | `NotifyGetClanMember()` | `MS_GET_CLAN_MEMBER_OUT` | `i16 @0` = chave; string NUL-terminada a partir de `@2` (copiada **sem limite** para `nó+0x10`); `u8 @0x14` → `+0xB0`; `i32 @0x18` → `+0x3C`; `u8 @0x1C` → `+0x23` (asm 0x10025763–0x10025772) | insere membro | `FUN_10025120` case 0xaf |
| 176 | `NotifyDelClanMember()` | `MS_DEL_CLAN_MEMBER_OUT` | `i16 @4` | marca `+0x28 = -1` se o nome coincidir; senão chama `FUN_10024BB0` (**remoção não decodificada**) | `FUN_10025120` case 0xb0 |
| 178 | `NotifySendClanMessage(string sender, string msg)` | `MS_SEND_WHISPER_OUT` (reuso) | `u16 @0x12` = `len`; texto @0x14 | chat de clã | `FUN_10025120` case 0xb2 |
| 183 | `NotifyFriendList()` | `MS_GET_BLACK_LIST_OUT` (reuso) | gate `i32 @0x28 >= 0`; i32 lidos em `@0x00, 0x04, 0x08, 0x0C, 0x10, 0x18, 0x1C, 0x20`; u8 em `@0x14, 0x24, 0x25, 0x26`; `@0x25` → `+0xB0` e `@0x26` → `+0x23` (asm 0x10025986–0x100259a4) | insere amigo | `FUN_10025120` case 0xb7 |
| 184 | `NotifyDelFriend()` | `MS_DEL_FRIEND_LIST_OUT` | `i32 @4` = resultado | remove amigo se `== 0` | `FUN_10025120` case 0xb8 |
| 188 | `NotifyBlackList()` | `MS_GET_BLACK_LIST_OUT` | igual a 183 **exceto**: não grava `@0x25` em `+0xB0`; usa a lista de bloqueados `FUN_100233E0` (183 usa `FUN_10023350`) | insere bloqueado | `FUN_10025120` case 0xbc |
| 189 | `NotifyDelBlack()` | `MS_DEL_BLACK_LIST_OUT` | `i32 @4` = resultado | remove bloqueado se `== 0` | `FUN_10025120` case 0xbd |
| 191 | `(break)` | — | `u8 @0` = count; entradas de `0x14` bytes a partir de `@4` | atualiza amigos em lote | `FUN_10025120` case 0xbf |
| 193 | `(break)` | — | `u8 @0` = count; registros de `0x14` bytes a partir de `@4`; por registro: `i32 @0` → `+0xA0`, `i32 @4` → `+0x3C`, `i32 @8` → `+0x28`, `i32 @0xC` → `+0x2C`, `u8 @0x10` → `+0x30`, `u8 @0x11` → flag `+0xB0` (0x22 ou 0) | atualiza lista em lote (nó localizado por `FUN_10007830`) | `FUN_10025120` case 0xc1: bloco = alvo `0x10025BE4` (índice `0x16` em `0x10025D7C+0xC1`); stores `MOV [EDI+0xa0],EDX` @0x10025C12, `MOV [EDI+0x28],EDX` @0x10025C27, `MOV [EDI+0x2c],EAX` @0x10025C2D, máscara `AND ECX,0x22` @0x10025C3A (`.c` linhas 567–590) |
| 195 | `(break)` | — | cabeçalho: `i32 @0` → `+0x28`, `i32 @4` → `+0x2C`, `u8 @8` → `+0x30`; `u8 @9` = count; registros de `0x0C` bytes **a partir de `@0x0C`** (não de `@0`); em cada registro: `i32 @0` → `+0xA0`, `i32 @4` → `+0x3C`, `u8 @8` → flag `+0xB0` (asm 0x10025c69–0x10025ce2, `ADD EDI,0xC`) | atualiza lista em lote (`NotifyChangePlayerProperty` no fim) | `FUN_10025120` case 0xc3 |
| 3 | — | — | — | **sem caso**: nenhuma resposta ao Heartbeat é processada | `default` de `FUN_10025120` |

### 4.1 `LM_REGISTER_INFO` (37 bytes `u8` em ordem, seguidos de `int result`)

`background`, `effect`, `voiceinfo`, `voicecharacter`, `mouseacc`, `mousesence`, `mouseinvert`, `weapon1`, `weapon2`, `weapon3`, `weapon4`, `weapon5`, `weapon6`, `weapon7`, `weapon8`, `weapon9`, `weapon0`, `moveforward`, `movebackward`, `moveleft`, `moveright`, `fire`, `altfire`, `walk`, `down`, `jump`, `changemag`, `chaff`, `booster`, `action`, `speechmenu1`, `speechmenu2`, `speechmenu3`, `object`, `mirror`, `minimap`, `screenshot`.

Offsets: campo `i` em `@i` (i = 0..36). Tamanho 37 = 0x25 (`LM_Engine.u`, `struct native LM_REGISTER_INFO`; número de linha não reproduzido, use a âncora); `NotifyRegister` copia 0x25 bytes. A struct do UnrealScript tem ainda `var int result` após os 37 bytes.

### 4.2 `MS_*_OUT` de respostas usadas por `execGetChannelServerInfo`

`execGetChannelServerInfo` @0x10007C70 lê campos de um **nó** da lista global (`FUN_10023030()`), não diretamente do corpo. O payload do nó começa em `node+0x08` e é cópia verbatim de 72 bytes da entrada `i` do 131 (`corpo + 2 + 72·i`, §6). Offsets abaixo são relativos ao início da entrada:

| offset no payload | tipo | campo `LM_SERVER_INFO` |
|---|---|---|
| 0x00 | u16 | `server_id` |
| 0x02 | u8 | `server_type` |
| 0x03 | u8 | `server_group` |
| 0x04 | u8 | `channel_mode` |
| 0x05 | u8 | `access_level` |
| 0x06..0x07 | 2 bytes | não nomeado (padding ou campo não lido) |
| 0x08 | i32 | `access_exp` |
| 0x0C | u16 | `max_client_count` |
| 0x0E | u16 | `curr_client_count` |
| 0x10 | u16 | `pick_client_count` |
| 0x12 | u16 | `service_port` |
| 0x14 | char ANSI | `service_address`: lido com `strlen` **sem limite** (`execGetChannelServerInfo` @0x10007C70); se não houver NUL nos 16 bytes, a leitura passa para o campo seguinte. O emulador deve enviar NUL dentro de 0x14..0x23 |
| 0x24 | char ANSI | `server_name`: mesmo caso, `strlen` sem limite; o nó tem 72 bytes (0x48), então o NUL deve estar em 0x24..0x47 |

A semântica dos campos vem do leitor `execGetChannelServerInfo`; o cliente não valida os campos. Offsets e larguras foram confirmados no leitor nativo (`ushort`, `byte`). UnrealScript declara `server_id` e os contadores como `int`, mas o fio usa `u16`.

## 5. Requisições do cliente (MS_*_IN)

Todas com o cabeçalho u16 da §1. Corpo a partir de `buf+2`.

### 5.1 Login (opcode 100) — `Cmessage_interface::Login` @0x10003d90

Corpo fixo de 44 bytes (`FUN_10003b10` copia 11 dwords de `MS_LOGIN_IN`), seguido de variável `id || pw`:

| offset no corpo | tipo | campo |
|---|---|---|
| 0x00 | i32 LE | `id_len` |
| 0x04 | i32 LE | `pw_len` |
| 0x08 | char[33] | `login_num` (GUID; origem provável `LoginGUID()` do `login_num=` da linha de comando **(inferido)**) |
| 0x29..0x2B | 3 bytes | padding (lixo de pilha; não usar) |
| 0x2C | `id_len` bytes | `id` |
| 0x2C + id_len | `pw_len` bytes | `pw` |

Tamanho total do corpo = `44 + id_len + pw_len`. Cabeçalho = `(100 << 5) | 13`. O `<<5` é feito em `FUN_10003b10` (`in_AX << 5`); `Login` passa `0x64` em `EAX`.

Evidência: `Login` @0x10003d90 passa `id_len + pw_len` como `param_4`; `FUN_10003b10` escreve `param_4 + 0x2e` bytes no total. O `login_num` aparece no pacote; a origem (`LoginGUID()`, NOTES.md) não foi rastreada até o envio **(inferido)**.

**GuidLogin:** XInterface `NetGuidLogin(guid, forced)` → `ServerInterface.GuidLogin` → comando `/GuidLogin` (LM_Engine.u linhas 2078-2085) → roteador `FUN_10026810` (não decompilado). `_core_network`/`+server_interface` exporta apenas `Cmessage_interface::Login` para o opcode 100. Conclusão **(inferido)**: GuidLogin também envia opcode 100 com `MS_LOGIN_IN`; o formato exato dos campos (id/pw/login_num para o caso GUID) não foi confirmado.

### 5.2 Register (opcode 110) — `Cmessage_interface::Register` @0x10003dc0

Sem corpo. Cabeçalho = `(110 << 5) | 13` = `0x0DCD`. Resposta: 111.

### 5.3 InMessageServer (opcode 120) — `Cmessage_interface::InMessageServer` @0x10003e10

Sem corpo quando o parâmetro é nulo (confirmado em `Cmessage_interface::InMessageServer` @0x10003E10: `iVar2 = 2` se `param_1 == 0`). `ServerInterface.InMessageServer()` de `LM_Engine.u` não tem parâmetro (confirmado). Se houver parâmetro: 1 byte de corpo (`MS_IN_MESSAGE_SERVER_IN`, tipo de 1 byte no Ghidra; conteúdo não identificado). Cabeçalho = `0xF00 | 13` = `0x0F0D`. Resposta: 121.

### 5.4 GetChannelServerInfo (opcode 130) — `Cmessage_interface::GetChannelServerInfo` @0x10003f20

Sem corpo. Cabeçalho = `0x1040 | 13` = `0x104D`. Resposta: 131.

### 5.5 CheckNickname (opcode 140) — `Cmessage_interface::CheckNickname` @0x10003e80 → `FUN_10003ce0`

Corpo fixo de 17 bytes (`MS_CHECK_NICKNAME_IN`), copiado por `FUN_10003ce0` como 4 dwords + 1 byte (confirmado); nenhum campo decodificado. **(inferido)**: são 17 bytes, provavelmente `char nickname[17]`; a conversão de `string` para a struct não foi localizada:

| offset no corpo | tipo | observação |
|---|---|---|
| 0x00 | i32 | dword 0 do struct |
| 0x04 | i32 | dword 1 |
| 0x08 | i32 | dword 2 |
| 0x0C | i32 | dword 3 (parte do bloco opaco) |
| 0x10 | u8 | byte extra |

Cabeçalho = `(140 << 5) | 13`. Total do buffer = 19 (0x13). Resposta: 141.

### 5.6 CreateNickname (opcode 150) — `Cmessage_interface::CreateNickname` @0x10003ea0

Corpo de 55 bytes (`MS_CREATE_NICKNAME_IN`), bloco opaco copiado como 13 dwords (`@0x00..0x33`), `u16 @0x34`, `u8 @0x36`; nenhum campo decodificado. Total do buffer = 57 (0x39). Cabeçalho = `(150 << 5) | 13` = `0x12CD`. Resposta: 151.

Semântica dos campos: **não confirmada**. A UI (XInterface comentado: `NetCreateNickname(LM_OPTION_INFO Options, string nickname)`) sugere um bloco de opções (37 bytes, mesmo formato de `LM_REGISTER_INFO`) mais o nickname, mas o layout 52+2+1 não bate com 37+nickname de forma simples. Não usar sem decodificar o roteador (`FUN_10026810`) ou `execCommand` para `/CreateNickname`.

## 6. Sequência de login observada

Fonte da sequência: código de UI (XInterface) + log de sessão real (`re/NOTES.md`: `0 → 101 → 111 → 121 → 131`).

1. Conexão aberta: evento 0.
2. Cliente envia **Login (100)**. Resposta **101**: `result`.
   - `result == 0` → cliente chama `Register()` (110).
   - `result != 0` → `bRegistered = false`; `OwnerPage.OnNotify(NType_Login)` exibe a tela de erro **(inferido: o texto vem da UI, não do lookup de `msg_error`, que o dispatcher descarta)**.
3. Cliente envia **Register (110)**. Resposta **111**: `LM_REGISTER_INFO` (opções do jogador) + `result`.
4. Nickname:
   - Se o nickname já existe, o cliente envia **InMessageServer (120)** direto (fluxo do log real: 111 → 121).
   - Se não existe: **CheckNickname (140)** → 141 (`result==0` → "nome disponível", 10200) → **CreateNickname (150)** → 151 → se `result==0`, `InMessageServer()` (120). Fluxo **(inferido a partir de XInterface)**: não há log que cubra esse ramo.
5. Resposta **121**: `result==0` → guarda nickname e clã; cliente chama `GetFriendList()` (180, confirmado pelo cabeçalho `0x1680`; resposta a 180 **não confirmada**: 181 e 182 não têm caso no dispatcher, e a lista de amigos chega em 183) e, se `clan_code>0`, `GetClanList()` e `GetClanMember()`.
6. Tela de servidores abre (`OnEndOpenAnim`, XInterface): `NetGetChannelServer()` → **GetChannelServerInfo (130)** → **131** (`FUN_10025120` case 0x83): `u8 @0` = `count`, `u8 @1` = `bRandom`, entradas de 72 bytes em `@2 + 72·i` (i < count). Ordem: esvazia a lista global (`FUN_10024560`); insere um nó por entrada (`FUN_10024c10` → `FUN_10024700`, cópia verbatim de 72 bytes); chama `NotifyChannelServerInfo(bRandom)`; `_DAT_1005b180 = count`. Em seguida a UI chama `GetChannelServerInfo(idx)` em cada índice (`execGetChannelServerInfo`), que lê os nós (§4.2). Com `count = 0` a lista fica vazia.
7. Heartbeat (2) a cada 10 s (`re/NOTES.md`, intervalo **não verificado** no binário; cabeçalho `0x40` confirmado em `SendHeartbeat` @0x10004230). Nenhuma resposta é processada.

## 7. Códigos de resultado (`msg_error`)

Tabela `msg_error(memo, code, message)` em `client_landmass.db` (cópia do `landmass.wdb`; 208 linhas, códigos de -10115 a 300000801). Textos em cp1252. Conferido por consulta: 208 linhas, mínimo -10115, máximo 300000801, -500 ausente, e os textos das linhas abaixo batem com o banco.

| code | texto (resumo) |
|---|---|
| 0 | ok |
| -10 | erro de rede |
| -11 | valor inserido inválido |
| -12 | tempo esgotado |
| -13 | erro do sistema |
| -14 / -15 / -16 | erro ao ler / salvar / deletar arquivo |
| -17 | possível tentativa de ataque ao servidor |
| -18 | erro do sistema de DB |
| -19 | contato offline |
| -20 | erro de versão |
| -160 | senha inválida |
| 10200 | nome disponível (retorno de CheckNickname com `result==0`) |
| 10201 | "%s' falhou ao receber a mensagem '%s'." |

Observações:
- `NERR_OK` = 0 (inferido: `NotifyLogin` testa `result == 0`; `NotifyInMessageServer` testa `result == NERR_OK`).
- `-500` é caso especial no dispatcher (registro, 111) mas **não existe** em `msg_error` (inferido: tratado como valor de recusa sem texto).
- `FUN_10021c80(short)` @0x10021c80 busca o código em `Cdb_table` `DAT_1005aed8` (chave `short` no registro 0, texto no registro 1). Se não achar: `sprintf` do código. O dispatcher **descarta** o retorno. Quem exibe a mensagem é desconhecido (lacuna). **A fonte de `DAT_1005aed8` não é `msg_error`**: `LM_Engine.dll` não contém a string `msg_error`; `landmass.wdb` é aberto por `FUN_10016340` (tabela `maps`) e `FUN_10024E00` (tabela `message_server`), não para textos de erro. Candidato: `error.wdb` (magic `f7 db`, formato `Cdb_table`; string `7error.wdb` @0x1002D927, **sem xref direto**) **(inferido)**. A ligação entre os códigos do lookup e os textos de `msg_error` está **não confirmada**.

## 8. Lacunas (o que ainda não está provado)

1. **GuidLogin (opcode 100 via `NetGuidLogin`)**: o roteador `FUN_10026810` (`/GuidLogin` e `/CreateNickname`, `execCommand` @0x10006920) não foi decompilado. Não está provado que o pacote use `MS_LOGIN_IN` com `login_num` = GUID nem o mapeamento de id/pw nesse caminho (ver §5.1).
2. **Override de `OnRecv` (parse do cabeçalho)**: não localizado. A vtable base tem slot 3 vazio (`CnetworkClient::OnRecv` @0x10001d80). Confirmado nesta revisão: o slot 3 aponta para 0x10001D80. Os endereços 0x1000DB00 e 0x1000DB90 (xrefs de `DAT_10016518`) **não são entradas de procedimento** no Ghidra ("No procedure exists"), então o init estático não foi decompilado. Não há leitura de `DAT_10016500` (callback) por endereço absoluto: só os writes 0x10003905 e 0x1000397f (em `Init`). Logo o leitor acessa o bloco por deslocamento relativo (**inferido**). Os xrefs de `DAT_10016518` em 0x1000db00 (init estático: `MOV ECX,0x10016518` + chamada de construtor, **inferido**) e 0x1000db90 (registro de `atexit`) indicam construção com a vtable base; o override, se existir, é trocado depois. Próximo passo: achar a escrita de vtable em runtime para `DAT_10016518` ou o `OnRecv` derivado. Se a leitura de `OnConnect` (§4, linha 0) valer, `OnRecv` recebe o quadro inteiro, com o prefixo u16 incluído (inferido).
3. **Origem do callback**: quem chama `Cmessage_interface::Init` com `FUN_10025120` não foi achado (`procedure_callers` vazio). Atribuição feita por assinatura e pelos case labels (inferido).
4. **Semântica de campos**: remetente de whisper (161), `MS_IN_MESSAGE_SERVER_IN` (1 byte), leitor de `DAT_1005AD70` (`@0x14` de 121), bytes 0x15..0x17 de 121, `DAT_1005AE20` (33 bytes de 111), blocos opacos de 140 e 150 (layout 52+2+1 de `MS_CREATE_NICKNAME_IN` não confirmado).
5. **Listas 171-195**: só contagem/gate decodificados; campos de amigo/clã/ranking não decodificados completamente.
6. **Comprimento do corpo**: o dispatcher não valida o tamanho do frame. O 131 lê `2 + 72·count` bytes do corpo; o emulador deve enviar pelo menos esse tamanho. Quadro completo do 131: `u16` de tamanho = `4 + 72·count` (cabeçalho 2 + payload `2 + 72·count`); bytes no fio = `6 + 72·count`.
7. **Canal (Channel Server)** é outro protocolo (`FUN_1001da60`, net_code 14) e não faz parte deste documento.
8. **Evento `NotifyFriendLog`** (UnrealScript, `MS_FRIEND_LOG_OUT`): existe em `LM_Engine.u` sem caso no dispatcher; opcode desconhecido.
9. **Pares sem troca observada**: 140→141, 150→151, 152→153, 170→171, 190→191, 192→193 e 194→195 têm cabeçalho de pedido medido (§1) e caso de resposta no dispatcher, mas nenhuma troca foi capturada; o `+1` é inferido. 182 não é pedido medido nesta revisão. A resposta de 180 (GetFriendList) não foi localizada: a lista de amigos chega em 183 (par não confirmado). 160 não é par +1: 161 vai ao destinatário e 162 ao remetente em erro (inferido).
10. **Envio no socket**: o `send` que consome o buffer (thread de envio de `_core_network`) não foi decompilado. O prefixo u16 está confirmado em §1 (`OVERLAPPED_IO::SetBuffer`).
