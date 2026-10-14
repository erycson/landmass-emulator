# Layouts F0 (LandMass): índice do que fechou

Escopo: fatia F0 de `docs/architecture/07-progression.md` §7. Binário analisado (somente leitura): `D:\landmass\cliente\system\LM_Engine.dll`, sha256 `4a08e7cebf2abe31cc1e6d0f73bf7734b58af5ce5cc21474987f0242fd04230f`. Ghidra 12.1.4 via REA, uma sessão, um binário. Nada foi executado nem alterado.

Marcas: **(inferido)** = não provado pelo código; **(gap)** = não decodificado.

Endereços: `FUN_1001xxxx` e `FUN_1002xxxx` são de `LM_Engine.dll` (imagem base 0x10000000); `Cchannel_interface::*` é de `+server_interface.dll`. `disp@Lx-y` = linhas de `re\LM_Engine.dll\channel_dispatch_FUN_1001da60.c`. Os valores de opcode nos `case` são hexadecimais do código; aqui se usa decimal (`0x97` = 151, `0x13d` = 317, `0x223` = 547).

## 0. Estado

| Opcode | Lado | Estado | Seção |
|---|---|---|---|
| 546 RefreshPlayerList | C→S (pedido) | fechado | §2 |
| 151 lista de jogadores do canal | S→C (resposta) | fechado (cria nós) | §1.2, §3 |
| 548 NotifyChangePlayerProperty (lista) | S→C (resposta a 546) | fechado (só atualiza) | §3 |
| 317 lista de jogadores da sala | S→C | fechado (cria nós) | §1.2, §3 |
| 549 NotifyInRoom (entrada na sala) | S→C | fechado (cria nó) | §1.2, §3 |
| 545 RefreshRoomList | C→S (pedido) | fechado (máx. 9 salas) | §4.1 |
| 547 NotifyChangeRoomProperty (lista) | S→C (resposta a 545) | fechado, exceto u16 de +0x50 (gap) | §4.2 |

Diagnóstico da lista vazia: §5.

## 1. Convenção de nós (usada pelos handlers)

- Jogadores e salas ficam em nós de lista (estilo MSVC). A chave de busca está em `nó+0x0c` (inferido: `151` compara `nó+0x0c` com a guid própria, linha 1179 de `disp`).
- `FUN_10007830` (jogador) e `FUN_10019e90` (sala) acham o **nó** e devolvem pelo out-param.
- `FUN_1001d5d0` (jogador) e `FUN_1001d640` (sala) devolvem o **valor** = `nó+0x10` (registro).
- Conversão: `nó+Y = valor+(Y-0x10)`, ou `valor+X = nó+(X+0x10)`. Handlers diferentes usam bases diferentes: 302, 403, 412, 317 (sala) e `ConvertPlayerInfo` usam **valor**; 314, 332, 342, 541, 547, 548, 549 usam **nó**. Essa diferença é a origem do conflito de §10.5 em `rooms.md`.

### 1.1 Registro do jogador (valor = nó+0x10)

Fonte: `ULM_ServerInterface::ConvertPlayerInfo` (0x10006500, decompilado) lê o registro **valor** e monta `LM_PLAYER_INFO` (`LM_Engine.src.txt` L670). A ordem dos campos é a de `LM_PLAYER_INFO`. Offsets em relação ao **valor**.

| valor+X | tipo | campo (nome da struct; * = gravado por handler) | nó+X | leitura em `ConvertPlayerInfo` |
|---|---|---|---|---|
| 0x00 | char[] | `strNick` (ANSI, lido até NUL) | 0x10 | `MultiByteToWideChar(in)`. Sem limite de 16 bytes: risco se nick tiver 16 chars sem NUL (inferido) |
| 0x10 | u8 | não lido por Convert (inferido: byte após o nick) | 0x20 | — (gravado por 151/317/549*) |
| 0x11 | u8 | `ucAccess` | 0x21 | `in[0x11]` |
| 0x13 | u8 | `ucVehicleLicence` | 0x23 | `in[0x13]` |
| 0x14 | u8 | `ucSex` | 0x24 | `in[0x14]` (não gravado por 151/317/549: inferido) |
| 0x18 | i32 | `siClan` | 0x28 | `in+0x18` |
| 0x1c | i32 | `clan_mark` | 0x2c | `in+0x1c` |
| 0x20 | u8 | `ucNest` | 0x30 | `in[0x20]` |
| 0x24 | i32 | `iHeadshot` | 0x34 | `in+0x24` |
| 0x28 | i32 | `iTutorialClear` | 0x38 | `in+0x28` |
| 0x2c | i32 | `iTotalExp` | 0x3c | `in+0x2c` |
| 0x30, 0x34, 0x38, 0x3c, 0x40, 0x44 | i32 | `iTotalGamecount`, `iTotalKill`, `iTotalDeath`, `iTotalWin`, `iTotalLose`, `iTotalSecedecount` | 0x40..0x54 | `in+0x30..0x44` |
| 0x48 | i32 | `iCash` | 0x58 | `in+0x48` |
| 0x4c | i32 | `iPoint` | 0x5c | `in+0x4c` |
| 0x50..0x59 | u8[10] | `sEventSlot[10]` | 0x60..0x69 | `in[0x50..0x59]` |
| 0x5a..0x79 | 8 × (short + byte), passo 4 | `sGate[8]` | 0x6a..0x89 | `in+0x5a+4k` (short), `in[0x5c+4k]` (byte) |
| 0x7c | i32 | `iTotalRank` | 0x8c | `in+0x7c` |
| 0x80 | u8 | `pc_room` | 0x90 | `in[0x80]` (151 não grava; 317 e 549 gravam*) |
| 0x81 | u8 | `member_grade` | 0x91 | `in[0x81]` |
| 0x84 | i32 | `premium_end` | 0x94 | `in+0x84` |
| 0x88 | i32 | `main_morats` | 0x98 | `in+0x88` |
| 0x8c | u8 | `bGift` | 0x9c | `in[0x8c]` |
| 0x90 | i32 | `client_guid` (chave da lista) | 0xa0 | `in+0x90` (`local_144[0]`) |
| 0x94 | i32 | `room_guid` (chave da sala) | 0xa4 | `in+0x94` (`local_144[1]`); 317 e 549 gravam* (sala do próprio jogador) |
| 0x9c | bit0 | `ready_game` | 0xac | `in+0x9c & 1` (402 e 317/549 gravam bit0 de nó+0xac*) |
| 0xa0 | u8 | `position` (estado: 0x22..0x25) | 0xb0 | `in[0xa0]`. Estado é gravado por 151/317/549/402* |
| 0xa2 | u8 | `select_morats` | 0xb2 | `in[0xa2]` |
| 0xa4 | i32 | `select_morats_id` | 0xb4 | `in+0xa4`; 317 e 549 gravam* |

Notas:
- `ConvertPlayerInfo` grava `result = 0` (campo `result` não vem do registro).
- Lê `in+0x80` como `pc_room`, mas o campo que 317 grava em `nó+0x90` vem de `R+0x2b` (§1.2).
- Os nomes de `iHeadshot`, `iTutorialClear`, `iTotalGamecount` etc. vêm da ordem de `LM_PLAYER_INFO`, não de um handler (inferido).

### 1.2 Registro de jogador nos pacotes 151, 317 e 549 (R = início do registro)

Os três handlers gravam o mesmo registro nos nós. Diferenças: 151 grava só os campos de identidade e estado `0x22`; 317 grava tudo e cria nó; 549 grava tudo, cria nó, e chama `NotifyInRoom`.

| R+ | tipo | campo | destino (nó) | 151 | 317 | 549 |
|---|---|---|---|---|---|---|
| 0x00 | i32 | `client_guid` | nó+0xa0 | disp@1223 | disp@1439 | disp@651 |
| 0x04 | i32 | `iTotalExp` | nó+0x3c | disp@1224 | disp@1440 | disp@652 |
| 0x08..0x17 | char[16] | `strNick` (4 dwords) | nó+0x10..0x1f | disp@1231-1234 | disp@1458-1461 | disp@664-667 |
| 0x18 | u8 | byte após o nick (inferido) | nó+0x20 | disp@1235 | disp@1463 | disp@670 |
| 0x19 | u8 | `ucVehicleLicence` | nó+0x23 | disp@1226 | disp@1441 | disp@653 |
| 0x1a | u8 | `ucAccess` | nó+0x21 | disp@1227 | disp@1442 | disp@654 |
| 0x1c | i32 | `siClan` | nó+0x28 | disp@1229 | disp@1447 | disp@660 |
| 0x20 | i32 | `clan_mark` | nó+0x2c | disp@1230 | disp@1448 | disp@661 |
| 0x24 | u8 | `ucNest` | nó+0x30 | disp@1228 | disp@1443 | disp@655 |
| 0x28 | u8 | índice do slot na sala (inferido) | slot da sala | — | `piVar22[idx+0x14]` = guid (disp@1466) | `nó_sala+(idx+0x18)*4` = guid (disp@675) |
| 0x29 | bit0 | `ready` | nó+0xac bit0 | — | disp@1444-1446 | disp@656-658 |
| 0x2a | u8 | flag de estado (0 → 0x23, ≠0 → 0x25) | nó+0xb0 | — | disp@1451-1457 | — (grava 0x23 fixo, disp@659) |
| 0x2b | u8 | `pc_room` | nó+0x90 | — | disp@1450 | disp@663 |
| 0x2c | i32 | `select_morats_id` | nó+0xb4 | — | disp@1449 | disp@662 |

Campos gravados por handler, fora da tabela:
- `nó+0xb0` = `0x22` fixo em 151 (disp@1225).
- `nó+0xa4` (sala do próprio jogador): 317 grava `pUStack_88c` (disp@1438, vem de `nó_próprio+0xa4`, ou `-1` se o próprio jogador não existe). 549 grava o mesmo (disp@650). 151 **não** grava `+0xa4`.
- `nó+0x20` na 317 e 549 é o byte `R+0x18`. Não tem nome confirmado.

Estrutura de cada pacote:

| Opcode | Corpo | Contagem | Passo | Cria nó? | Pré-condição |
|---|---|---|---|---|---|
| 151 | `u16 count` @0, registros a partir de @2 | `u16` (disp@1189-1240) | 0x28 (40 bytes) | sim (zera, `FUN_1001d5d0`, disp@1198-1218) | se o próprio status `== '#'` (0x23): remove nós com status 0x22 (`FUN_10019ad0`, disp@1158-1164); senão zera o status dos outros (disp@1177-1181) |
| 317 | `u8 count` @0, registros a partir de @1 | `u8` (disp@1404-1471) | 0x30 (48 bytes) | sim (disp@1413-1434) | o próprio jogador existe (`DAT_1005ada0`) e a sala dele está na lista de salas; senão nada é processado |
| 549 | sem contagem; um registro a partir de @0 | — | — | sim (disp@627-647) | só se o próprio jogador não existe, ou se a sala dele tem `+0xa4 ≠ 0` (disp@616-619) |

Obs.: 317 e 549 usam o mesmo registro de 48 bytes (`R+0x00..R+0x2f`); 151 usa o registro reduzido de 40 bytes (`R+0x00..R+0x27`).

## 2. 546 RefreshPlayerList (pedido, C→S)

Montagem: `FUN_10018540` (`/RefreshPlayerList`, router `FUN_10026810`) monta `CS_REFRESH_PLAYER_LIST_IN` em `local_50` (64 bytes) e chama `Cchannel_interface::RefreshPlayerList` (`0x10002c40`) → helper `FUN_10001ae0` (`AX = 0x222`, `N = 66`, corpo de 64 bytes = 16 dwords).

| @ (corpo) | tipo | campo | evidência |
|---|---|---|---|
| 0 | i32 | `nChannel` (atoi de `param[0]`). Se `< 0`, nada é enviado | `FUN_10018540`: `local_50 = atoi(param_1+0x28)`; `if (local_50 < 0) return 1` |
| 4 | u8 | `count` = atoi de `param[1]`, máximo 14 (0x0e). Se 0, nada é enviado | `FUN_10018540`: `local_4c[0]`; `if (>0xd) local_4c[0]=0x0e` |
| 5..7 | — | zero (padding) | `local_4c[1..3]` zerados |
| 8 + 4·i | i32 | `client_guid[i]`, i < count, até 14 | `local_48[14]`; parse de `param[2]` separado por espaço (`strchr 0x20`, `atoi`) |
| 8 + 4·i (i ≥ count) | i32 | zero | laço de zeragem |

Observações:
- O parse só guarda um token que é **seguido de espaço**. Um GUID único sem espaço final **não é enviado**. Por isso `00000000 01000000 01000000` (count = 1, guid = 1) exige que a string da UI termine em espaço (`"1 "`).
- Sem limite de quantidade no parse de `param[2]`: mais de 14 tokens escreve além de `local_48[14]` (**risco de estouro no cliente**).
- Resposta esperada: 548 (ver §3). Pedido com `count = 0` não gera resposta.

## 3. Respostas de lista de jogadores

### 3.1 548 NotifyChangePlayerProperty (resposta a 546)

Dispatcher: `case 0x224` (548), `disp@577-607`. Evento: `NotifyChangePlayerProperty(int client_guid, int property, int value)` (`LM_Engine.src.txt` L2365). Chamada em `disp@604`, endereço `0x1001f674` (xref do wrapper `0x10003040`; atribuição ao case pela ordem do código, inferido).

Corpo (cabeçalho de 4 bytes, depois entradas de 20 bytes):

| @ (corpo) | tamanho | campo | destino (nó do jogador) | evidência |
|---|---|---|---|---|
| 0 | u8 | `count` (laço `< (u8)*param_2`; `count = 0` não lê entradas) | — | `disp@579`, `@599` |
| 1..3 | — | não lidos | — | — |
| 4 + 20·i | i32 | `client_guid` (chave de busca) | `FUN_10007830` (nó com chave = guid) | `pCVar6 = pCVar16 - 4` (`disp@582`) |
| 8 + 20·i | i32 | `iTotalExp` (inferido) | `nó+0x3c` (= valor+0x2c) | `disp@594` (`*(pCVar6+0x3c) = *pCVar16`) |
| 12 + 20·i | i32 | `siClan` (inferido) | `nó+0x28` (= valor+0x18) | `disp@594` |
| 16 + 20·i | i32 | `clan_mark` (inferido) | `nó+0x2c` (= valor+0x1c) | `disp@595` |
| 20 + 20·i | u8 | `ucNest` (inferido) | `nó+0x30` (= valor+0x20) | `disp@593` (`pCVar16[0xc]`) |
| 21..23 + 20·i | — | não lidos | — | — |

Notas:
- Passo = 20 bytes (`pCVar16 += 0x14`, `disp@598`). Corpo mínimo `4 + 20·count`. Cliente não valida tamanho.
- **Não cria jogador.** Só atualiza quando `FUN_10018aa0(achado, fim)` diz "existe" (`disp@590-591`). Jogador sem nó é ignorado em silêncio.
- **Não traz nick, rank nem nome de clã.** Nick vem de 151, 317 ou 549 (§1.2).
- Evento: o dispatcher passa um struct **zerado** (`disp@601-605`). O payload não tem dado para a UI; ela deve reler a lista.

### 3.2 151, 317 e 549 (criação de nós)

Ver §1.2 (campos e pré-condições). Resumo: 151 é a lista do canal (status `0x22`); 317 é a lista da sala; 549 é a entrada de um jogador na sala. Nenhum deles usa o stride de 548.

## 4. Salas: pedido 545 e resposta 547

### 4.1 Pedido 545 (decompilado: `FUN_100183d0`, `disp` não aplicável)

`/RefreshRoomList` → `FUN_100183d0` (router), `Cchannel_interface::RefreshRoomList` (`0x10002c10`) → helper `FUN_10001a40` (`AX = 0x221`, `N = 46`, corpo de 44 bytes).

| @ (corpo) | tipo | campo | evidência |
|---|---|---|---|
| 0 | i32 | `nChannel` (atoi de `param[0]`, se `paramcount > 0`). `< 0` → nada enviado | `FUN_100183d0`: `local_3c = atoi(param+0x28)`; `if (local_3c < 0) return 1` |
| 4 | u8 | `count` = atoi de `param[1]` (`param+0xa1`). `> 8` → 9. `0` → nada enviado | `local_38`; `if (8 < iVar3) local_38 = 9` |
| 5..7 | — | zero | struct de 44 bytes (`local_3c`, `local_38`, `local_34[9]`) |
| 8 + 4·i | i32 | `room_guid[i]`, i < count, **máximo 9** | `local_34[9]`; parse de `param[2]` (`param+0x11a`) separado por espaço |
| 8 + 4·i (i ≥ count) | i32 | zero | `local_34[0..8] = 0` |

Observações:
- Máximo confirmado: **9 salas** por pedido (`local_34[9]`, `if (8 < iVar3)`). Pedido com `paramcount ≤ 1` não envia nada.
- Sem limite de tokens no parse de `param[2]`: mais de 9 tokens escreve além de `local_34[8]` (**risco de estouro**, mesmo padrão de 546).
- Mesmo critério de espaço final do 546: último GUID sem espaço não é enviado.

### 4.2 Resposta 547

Dispatcher: `case 0x223` (547), `disp@541-576`. Evento: `NotifyChangeRoomProperty(...)`, chamado com struct **zerado** (`disp@569-573`). Chamada em `disp@573`, endereço `0x1001f5e2` (xref do wrapper `0x10003090`; atribuição ao case pela ordem do código, inferido; `0x1001f245` = 412).

Corpo (cabeçalho de 4 bytes, entradas de 16 bytes):

| @ (corpo) | tamanho | campo | destino (nó da sala) | evidência |
|---|---|---|---|---|
| 0 | u8 | `count` (laço `< (u8)*param_2`; `0` = nada) | — | `disp@543`, `@567` |
| 1..3 | — | não lidos | — | — |
| 4 + 16·i | i32 | `room_guid` (chave) | `FUN_10019e90` (nó com chave = guid) | `pCVar6 = pCVar16 - 4` (`disp@546`) |
| 8 + 16·i | u8 | `state` (0 vazio, 1 esperando, 2 jogando; inferido pela struct `LM_ROOM_INFO`, L758) | nó+0x48 | `disp@556` |
| 9 + 16·i | u8 | `game_mode` (inferido) | nó+0x49 | `disp@557` |
| 10 + 16·i | u8 | `team_count` (inferido) | nó+0x4a | `disp@558` |
| 11 + 16·i | u8 | `curr_player` (inferido) | nó+0x4b | `disp@559` |
| 12 + 16·i | u8 | `curr_spectator` (inferido) | nó+0x4c | `disp@560` |
| 13 + 16·i | u8 | `max_player` (inferido) | nó+0x4d | `disp@561` |
| 14 + 16·i | u8 | `open` (inferido) | nó+0x4e | `disp@562` |
| 16 + 16·i | u16 | `map_num` (inferido: `LM_ROOM_INFO` tem `map_num` logo após `open`) | nó+0x50 (= valor+0x40) | `disp@563` (`*(u16*)(pCVar6+0x50) = *(u16*)(pCVar16+8)`) |
| 18..19 + 16·i | — | não lidos | — | — |

Notas:
- Passo = 16 bytes (`pCVar16 += 0x10`, `disp@566`). Corpo mínimo `4 + 16·count`.
- Não cria sala: só atualiza sala que já existe (`FUN_10019e90` + `FUN_10018aa0`, `disp@548-555`).
- Sobrescreve `nó+0x4b`/`nó+0x4c` (contadores que 549 incrementa, `disp@677-682`) com o valor do pacote.
- Conflito com 302: 302 grava `valor+0x10` como `map` u16 (nó+0x20), e 547 põe o campo de mapa em nó+0x50. Um dos dois está errado ou são campos diferentes. Marcado (gap) até confirmação.

## 5. Diagnóstico da lista de jogadores vazia (para o coordenador)

Fatos provados pelo código:

1. **A lista do lobby é a lista de nós de canal** (`FUN_10023470`). Os nós nascem em **151** (lista do canal, status 0x22, disp@1147-1245), em **317** (lista da sala, disp@1389-1473) e em **549** (entrada na sala, disp@608-691).
2. **548 só atualiza nó existente.** Se o nó com a chave do pedido 546 não existe, 548 não muda nada e a UI fica vazia (`disp@590-591`).
3. **151 cria nós só se `count ≥ 1`** (`disp@1189`). Com `count = 0`, nenhum nó é criado.
4. **Chave:** a guid do pedido 546 (`body@8+4·i`) tem que ser igual à guid de um registro de 151 (`R+0x00`) que tenha chegado antes. A chave do nó é `nó+0x0c` e `nó+0xa0`.
5. **317 tem pré-condição dupla:** o próprio jogador precisa existir (`DAT_1005ada0`) e a sala dele precisa estar na lista de salas (disp@1401-1404). Sem isso, a lista da sala não cria nada.
6. **549 cria o nó do jogador que entra** (sem contagem), e só roda se o próprio jogador não existe ou se a sala dele tem `+0xa4 ≠ 0` (disp@616-619).
7. **151 com o próprio status `0x23` remove os nós de status 0x22** (`FUN_10019ad0`, disp@1158-1164) antes de inserir. Com outro status, só zera o status dos outros (disp@1177-1181).
8. **O evento de 548 não traz dados** (payload zerado). A UI redesenha a partir dos nós.

Consequência para a lista vazia: a causa mais provável é que o servidor não envia 151 com `count ≥ 1` contendo a guid pedida antes do 546, ou envia 151 com `count = 0`. Não se deve procurar a causa no 548, porque ele só atualiza. Verificação pendente: ver §6 (checar o que o emulador envia em 151).

## 6. Pendências desta rodada

- Confirmar o nome do u16 de `nó+0x50` em 547 (`map_num` ou outro) e o conflito com 302 (`valor+0x10`). Depende de `tools/re/rooms.md`.
- Byte `valor+0x10` (nó+0x20) gravado por 151/317/549 e sem leitura em `ConvertPlayerInfo`: nome não confirmado.
- Chave do mapa em `nó+0x0c` para jogadores: inferido por 151 (disp@1179). Confirmar em `FUN_10007830` e `FUN_1001d5d0`.
- `FUN_10019ad0` (remoção de nó, usado por 151): nome e efeito inferidos pelo uso. Não decompilado.
- Fechado nesta rodada (P1 restante e P2): ver §7.
- Pendentes: 512 (completo, só parcial em `channel_server.md` §3.1), 180-195 (em `message_server.md` §4, sem revisão nesta rodada), 332, 342, 421, 462, 543 (raw), resposta real de 451 (sem `case` 452 no dispatcher).

## 7. Fechado nesta rodada (P1 restante e P2)

Arquivos de pseudocódigo: `tools/re/LM_Engine.dll/FUN_10017530_CreateRoom.c` (301), `FUN_10018540_RefreshPlayerList.c` (546), `FUN_100183d0_RefreshRoomList.c` (545), `ConvertPlayerInfo_0x10006500.c`, `NotifyStartGame_0x10004440.c` (403), `NotifyRankingInfo_0x10003e30.c` (171).

### 7.1 Pedido 301 `/CreateRoom` (`FUN_10017530`)

Corpo de 74 bytes (`CS_CREATE_ROOM_IN`, helper `FUN_10001580`, AX=0x12d, N=76). Parâmetros em `LM_COMMAND_PARAM`: p0 @0x28, p1 @0xa1, p2 @0x11a, p3 @0x193, p4 @0x20c, p5 @0x285, p6 @0x2fe, p7 @0x377, p8 @0x3f0 (passo 0x79).

| @ (corpo) | tipo | campo (param) | evidência |
|---|---|---|---|
| 0x00 | u16 | `map_num` (p4) | `local_50 = atoi(p+0x20c)` |
| 0x02 | char[51] | `name` (p0), sem limite | cópia até NUL para `local_4e` |
| 0x35 | char[13] | `pw` (p1), sem limite | cópia até NUL para `local_1b` |
| 0x42 | u8 | `game_scale` (p2) | `local_e = atoi(p+0x11a)` |
| 0x43 | u8 | `game_mode` (p3) | `local_d = atoi(p+0x193)` |
| 0x44 | u8 | `team_count` (p6) | `local_c = atoi(p+0x2fe)` |
| 0x45 | u8 | `max_player` (p5) | `local_b = atoi(p+0x285)` |
| 0x46 | u8 | `limit_time` (p7) | `local_a = atoi(p+0x377)` |
| 0x48 | u16 | `limit_score` (p8) | `local_8 = atoi(p+0x3f0)` |

Risco: `name` com 51 ou mais caracteres e `pw` com 13 ou mais estouram o buffer (sem limite de cópia). Byte 0x47 é padding.

### 7.2 Pedidos 311 e 411

- 311 `/InRoom` (resumo da rodada anterior, não reverificado nesta rodada): corpo de 20 bytes, `i32 num @0`, `char pw[16] @4`.
- 411 `/ChangeRoomProperty` (`FUN_10017820`, decompilado nesta rodada). Corpo de 10 bytes (`CS_CHANGE_ROOM_PROPERTY_IN`, helper `FUN_100016e0`, AX=0x19b, N=12):

| @ | tipo | campo | condição |
|---|---|---|---|
| 0 | u8 | `flags` (p0) | bits: MAP 0x01, MODE 0x02, LIMIT_PLAYER 0x04, LIMIT_SCORE 0x08, LIMIT_TIME 0x10 |
| 1 | — | não usado | — |
| 2 | u16 | `map_num` (p1) | só se `flags & 0x01` |
| 4 | u8 | `game_mode` (p2) | só se `flags & 0x02` |
| 5 | u8 | `team_count` (p3) | só se `flags & 0x02` |
| 6 | u8 | `max_player` (p4) | sempre |
| 7 | u8 | `limit_time` (p5) | sempre |
| 8 | u16 | `limit_score` (p6) | sempre |

Obs.: no decompilado, `((byte)flags | 4) != 0`, `| 0x10` e `| 8` são sempre verdadeiros (artefato do Ghidra, igual ao já notado). A leitura de `max_player`, `limit_time` e `limit_score` é incondicional.

### 7.3 `CERR_*` (valores de `Core.u`)

Fonte: `scratchpad/dump_Core.txt` L1212-1340 (`const CERR_* = valor`). Os valores são inteiros negativos.

```
-2405 CERR_LOGOUT            -2406 CERR_FULL_ROOM          -2407 CERR_NOT_NICKNAME
-2408 CERR_NOT_ROOM          -2410 CERR_FULL_PLAYER        -2411 CERR_IN_ROOM
-2412 CERR_CANNOT_INVITE     -2413 CERR_PASSWORD           -2414 CERR_EXPEL_PLAYER
-2420 CERR_LOBBY_NOT_PLAYER  -2430 CERR_FULL_GAMEROOM      -2440 CERR_CLOSE_ROOM
-2450 CERR_FULL_SPECTATOR    -2460 CERR_FIND_PLAYER
-4000 CERR_CHANGE_ROOM_SLOT_READY   -4001 CERR_CHANGE_ROOM_SLOT_PLAY   -4002 CERR_CHANGE_ROOM_SLOT_FULL
-4010 CERR_READY_GAME_DURABILITY   -4011 CERR_READY_GAME_CLOSE    -4012 CERR_READY_GAME_TEAMREADY
-4013 CERR_READY_GAME_TEAMBALANCE  -4014 CERR_READY_GAME_READY    -4015 CERR_ROOM_STATE_PLAYING
-4016 CERR_READY_CLOSE_CHANNEL
-4020 CERR_CREATE_ROOM_MEMBER_GRADE   -4021 CERR_IN_ROOM_CLAN_MEMBER
-4030 CERR_ROOM_STATE_MATCHING     -4031 CERR_ROOM_STATE_EMPTY      -4032 CERR_READY_LEADER
-4033 CERR_SYSTEM_NETWORK          -4034 CERR_GROUP_INFO            -4035 CERR_GROUP_MEMBER_INFO
-4036 CERR_ROOM_STATE_WAITING      -4037 CERR_LIMIT_MIN_PLAYER
-4050 CERR_BUY_PREMIUM             -4051 CERR_DESTROY_NOT_REGULAR   -4052 CERR_USED_BUFF_OVERLAPED
-4053 CERR_NOTEXTEND_BUFF_DISABLE  -4054 CERR_NOTEXTEND_ONCE_ITEM   -4055 CERR_BUY_CASH_SHORTAGE
-4056 CERR_BUY_POINT_SHORTAGE      -4057 CERR_CHANGE_MAINMORATS_NOTNEST
-4058 CERR_CHANGE_MAINMORATS_DISABLE   -4059 CERR_CHANGE_MAINMORATS_EMPTY
-4060 CERR_CREATE_ROOM_NOT_ADMIN   -4061 CERR_INVITE_ROOM_NOT_ADMIN
-4070 CERR_GIFT_FULL_GATESLOT      -4071 CERR_GIFT_FULL_INVENSLOT
-4080 CERR_CHANGE_MAINMORATS_SPECIAL  -4081 CERR_CHANGE_MAINMORATS_MORATS
-4082 CERR_CHANGE_MAINMORATS_DURABILITY  -4083 CERR_ADD_GATE_LIMIT
-4084 CERR_GIFT_LEVEL             -4085 CERR_CHANGE_NEST_CLAN       -4086 CERR_CHANGE_NEST_BEGINNER
-32   CERR_NOT_CLAN_INFO
```

Códigos vistos no despacho (`channel_dispatch_FUN_1001da60.c`), conferidos com a tabela:
- `0xfffff04b` = -4021 `CERR_IN_ROOM_CLAN_MEMBER`
- `0xfffff04c` = -4020 `CERR_CREATE_ROOM_MEMBER_GRADE`
- `0xfffff024` = -4060 `CERR_CREATE_ROOM_NOT_ADMIN`
- `0xfffff023` = -4061 `CERR_INVITE_ROOM_NOT_ADMIN`
- `0xffffffe0` = -32 `CERR_NOT_CLAN_INFO`
- `0xfffff02e` = -4050 `CERR_BUY_PREMIUM` (usado em 551/552 como erro)
- Sem nome em `Core.u`: -23 (`0xffffffe9`), -26 (`0xffffffe6`), -29 (`0xffffffe3`), -30 (`0xffffffe2`), testados em 101 (**gap**).

Os valores batem com os códigos observados no despacho. Que o servidor envie exatamente esses valores no envelope 0x36 é (inferido).

### 7.4 403 `NotifyStartGame` (`0x10004440`) e o despacho (`disp@301-346`)

- Corpo de 18 bytes: `char[16] address` (ANSI, NUL) em @0; `u16 port` em @0x10.
- Wrapper: `FString(p as char*)` = endereço; `port = *(u16*)(p+0x10)`. Evento `NotifyStartGame(string address, int port)` (`LM_Engine.src.txt` L2364). **Provado** pelo decompilado da conversão; a ligação exata aos parâmetros do evento é (inferido).
- Antes do evento, o despacho: procura o próprio jogador (`DAT_1005ada0`), acha a sala por `+0xa4`, e em cada um dos 60 slots de `sala+0x50` com jogador: se `+0x9c` bit0 (pronto), grava `+0xa0` = `0x24` no valor do jogador. Depois grava `+0xb0 = 0x24` no próprio nó (disp@315-330).
- Globais `_DAT_1005ac34..44` recebem a cópia do corpo. Nenhum leitor achado por xref (só escritor em 0x1001f144). (**gap**).
- Quem envia 403: o servidor do canal. O cliente só recebe.

### 7.5 451 `/RoomExpel` e 700 `/ExpelPlayer`

- 451: pedido de 20 bytes (18 úteis; `FUN_10001830`, AX=0x1c3). **Não há `case` 452 no despacho** (grep de `0x1c4`/`452` em `tools/re/` vazio). A resposta real de expulsão de sala é **gap**.
- 700: pedido de 20 bytes (`FUN_10001830`, AX=0x2bc). Resposta `701` `NotifyExpelPlayer(i32 result)` em `disp@2386-2387` e `disp@428-431`, `i32 @0` → `_DAT_1005aa54`.

### 7.6 P2: jogador, progressão e notificações (`FUN_1001da60`)

| op | evento | corpo (offsets) | efeito no nó do próprio jogador (`DAT_1005ada0`) | disp |
|---|---|---|---|---|
| 101 | `NotifyInChannelServer` | `[0..0xa8)` = registro do jogador (ver §1.1); `i32 @0xa8` = resultado; `i32 @0xac` → `_DAT_1005ae08` | resultado 0: copia 0xa8 bytes para o nó (`FUN_1001d5d0`) e grava `DAT_1005ada0 = guid @0x90` | 853-882 |
| 102 | `NotifyGetItem` | `u16 key @0`; registro de 0x34 bytes em @0..0x33 (key dentro do registro); `u8 @0x35` ≠ 0 zera `i32 @0x30` | insere/atualiza item por `key` (`FUN_1001d6b0`), sempre | 883-899 |
| 103 | `NotifyGetMorats` | `u16 key @0`; registro de 0x5c em @0..0x5b; `u8 @0x5d` ≠ 0 zera `i32 @0x30` | gate: `nó+0x6a+4·key = key` (**inferido**, sGate de 8 slots); insere morat se ausente | 901-933 |
| 551 | `NotifyItemBuy` | `u16 key @0`; registro 0x34 @0..0x33; `i32 @0x38` cash; `i32 @0x3c` point; `i32 @0x40` result | se result = 0: insere item; `nó+0x58` (iCash) ← @0x38; `nó+0x5c` (iPoint) ← @0x3c | 692-719 |
| 552 | `NotifyMoratsBuy` | `u16 key @0`; registro 0x5c @0..0x5b; `i32 @0x5c` cash; `i32 @0x60` point; `i32 @0x64` result | se 0: insere morat; cash/point como 551; gate como 103 | 720-748 |
| 553 | `NotifyItemUsedGate` | `u16 key @0`; `u16 idx @2`; `i32 @4` result | se 0: remove item (`FUN_10019ee0`, **inferido**); `nó+0x6c+4·idx = 1` | 749-775 |
| 601 | `NotifyTutorialClear` | `i32 @0` → `nó+0x38` (iTutorialClear); `i32 @4` → `nó+0x5c` (iPoint) | — | 2440-2449 |
| 611 | `NotifyGetGiftItem` | `i32 @0` (1º parâmetro do evento); `i32 @4` = count; registros de 0x48 a partir de @8 (`u16 key @0` de cada) | primeiro registro sempre inserido; os demais só se `count > 1`; lista limpa se `@4 ≠ 0` (`FUN_1001a4b0`) | 1483-1522 |
| 616 | `NotifyItemGift` | `i32 @0` result; `i32 @4` cash; `i32 @8` point | se 0: `nó+0x58` ← @4; `nó+0x5c` ← @8 | 1608-1625 |
| 900 | `NotifyChargeCash` | `i32 @0` | `nó+0x58` (iCash) ← @0 | 2388-2401 |
| 901 | `NotifyChargePremium` | `i32 @0` | `nó+0x94` (premium_end) ← @0 | 2402-2415 |
| 902 | `NotifyChargePoint` | `i32 @0` | `nó+0x5c` (iPoint) ← @0 | 2416-2429 |
| 171 | `NotifyRankingInfo` | entradas de 0x20 bytes a partir de **@0** (não @4): `i32 @0` índice; `u16 @4` result (0 encerra); nick NUL a partir de @6; `i32 @0x18`, `u16 @0x1c` | evento de ranking; ver `NotifyRankingInfo_0x10003e30.c` | msg 0xab |

Obs.: 601 e 616 gravam nos campos de dinheiro e pontos conforme o código (601 grava `iPoint` a partir de `@4`, valor a confirmar com o servidor real).

### 7.7 Conclusões para o diagnóstico de progressão

- Os campos de progressão do próprio jogador (`iCash` +0x58, `iPoint` +0x5c, `premium_end` +0x94, `iTutorialClear` +0x38) são atualizados por 900-902, 551/552, 616 e 601. Nenhum deles cria o nó: se o nó do próprio jogador não existe, o efeito é nulo (`FUN_10018aa0`/`if` de existência em 900-902, 551, 552).
- O próprio nó é criado por 101 (`DAT_1005ada0`, disp@853-882) e 151/317/549 (§1.2).
- 601 não tem guarda de existência (disp@2443-2446): se o próprio nó não existe, grava no sentinela da lista (inferido).

## 8. Inventário e morat regular (F4 e F5)

Fontes: `tools/re/protocol_full.md` §2.1, §3.1 e §3.2 (102, 103, 104 e 105), `LM_PLAYER_INFO` em §1.1 (nest e `sGate`) e `GetMoratsInfoByGate` no dump de `LM_Engine` (L2288–2298). Código: `protocol/inventory.py` e `PlayerRecord` em `protocol/progression.py`.

**(RE)** = visto no dump ou no dispatcher. **(inferido)** = o emulador escreve assim, sem prova no cliente real.

| Mensagem | Campo | Offset | Tipo | Marca |
|---|---|---|---|---|
| 101 | `ucNest` | 0x20 | u8 | (RE) §1.1 |
| 101 | `sGate[k].siIdx` | 0x5A + 4k | i16 | (RE) §1.1; o emulador grava `siIdx = k` |
| 101 | `sGate[k].bEnable` | 0x5C + 4k | u8 | (RE) §1.1; 1 quando o gate está habilitado (D95, `enabled_gates`); habilitar sem morat não corrige a sala (linha 377) |
| 102 | chave `siIdx` | 0 | u16 | (RE) §3.2 |
| 102 | id do catálogo | 4 | i32 | (inferido) |
| 102 | GUID | 8 | char[37] | (inferido) |
| 102 | `apply_flag` | 0x2D | u8 | (inferido) |
| 102 | `apply_value` | 0x30 | i32 | (RE) §3.2 |
| 102 | zerar `apply_value` | 0x35 | u8 | (RE) §3.2; o emulador manda 0 |
| 103 | chave (gate) | 0 | u16 | (RE) §3.2 |
| 103 | id, GUID, `apply_flag`, `apply_value` | 4, 8, 0x2D, 0x30 | — | (inferido), igual ao 102 |
| 103 | peças (`siMainWeapon` ...) | 0x34 a 0x53 (16 × i16) | i16 | (inferido) |
| 103 | skins | 0x54 a 0x59 (3 × i16) | i16 | (inferido) |
| 103 | zerar | 0x5D | u8 | (RE) §3.2 |
| 104 | corpo | — | vazio | (RE) §3.2, L934–937 |
| 105 | `nest`, classe | 0, 1 | u8, u8 | (RE) §3.1 |

### Peças, skins e índices

- Índice de item começa em 1. O morat usa o gate (0 a 7) como índice ([D30](../../docs/decisions/README.md)).
- Peça -1 é o padrão: o `GetWeaponInfo` do XInterface usa o índice explícito quando é `>= 0` e cai no `DefaultSet` da espécie quando é negativo (dump do XInterface, `GetWeaponInfo` e `SetMorats`). Peça 0 não resolve (`GetItemInfoByID(0)` falha) e deixa a arma vazia.
- Skin: o emulador grava 0 (o kit antigo deixa NULL). Com 0, o botão de skin pode ficar vazio (inferido). Com -1, o cliente mostraria a skin do `DefaultSet`. Não alterado: decidir com captura no cliente.
- Morat no gate 0 tem chave 0. Não verificado se `GetMoratsInfoByID(0)` resolve.

### Gates e conta sem morat

- O 101 habilita `sGate[k]` só para os gates com morat, e o 103 vem para cada um. Teste: `test_kit_aplicado_vai_no_login_com_gates_habilitados`.
- Conta sem morat trava a sala no cliente (observado ao vivo pelo coordenador, `LM_RoomPage`, "Infinite script recursion"). `GetMoratsInfoByGate` devolve false quando `bEnable` é 0 e também quando o `siIdx` não tem morat (dump, L2288–2298). Por isso habilitar gate sem morat não corrige: é preciso um morat. Dúvida 24 em [07-progression](../../docs/architecture/07-progression.md).
- Nada disso foi confirmado no cliente real.

### Divergências com o RE

- `sEventSlot[10]`: o dump declara `LM_GATE_SLOT` (passo 4); a §1.1 lê `u8[10]` em 0x50..0x59. Resolver antes da F6 (equipar).
- 569 (`NotifyChangeNest`) não é enviado. O nest sai só no 101 (inferido).
- Layouts de 550, 555, 560, 570 e 580 (`tools/re/protocol_full.md` §2.1) são de F6 a F8. Ainda não há codec: ao implementar, usar esses layouts.
