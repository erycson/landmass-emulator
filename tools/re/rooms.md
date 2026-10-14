# Salas e início de partida: fluxo do Channel Server

Escopo: engenharia reversa estática, sem o MCP `rea` e sem abrir o jogo. Fontes:

- `re\channel_server.md`: tabelas de pedidos (§2), respostas (§3.1, §3.2) e GS (§4).
- `re\LM_Engine.dll\channel_dispatch_FUN_1001da60.c`: dispatcher das respostas (citado como `disp@linha`).
- `re\+server_interface.dll\channel_interface.c` e `channel_helpers.c`: pedidos e tamanhos `N`.
- Bytes de `D:\landmass\cliente\system\LM_Engine.dll` (leitura apenas; citados como `asm@endereço`).
- Scratchpad `src\LM_Engine.src.txt` (UnrealScript `LM_ServerInterface`) e `src\XInterface.src.txt` (UI e eventos).

Marcas: **(inferido)** = não confirmado por bytes; **gap** = não decodificado.

---

## Lista de canais (111)

### Layout no fio

| @ (corpo) | tamanho | campo |
|---|---|---|
| 0 | `u8` | `count` (N) |
| 1+i, para i = 0..N-1 | `u8` | carga do canal i (0..255; >= 100 = FULL) |

- Passo 1 byte. Não há id, nome, usuários, máximo, nível nem exp no fio. O `LM_SERVER_INFO` (`LM_Engine.src.txt` L365) é da lista de servidores e não se aplica ao 111.
- Nome e índice da linha vêm da UI, não do servidor: a coluna de nome é `strChannel` (`localize`, seção `LM_ChannelMCL`, valor "MARZ").

### Como o cliente decodifica (asm, não o decompilado)

Caso 0x6f de `disp@978-992`, com bytes em `asm@0x1001de7d..0x1001dea2`:

1. `call FUN_100230a0` (0x1001de7d): singleton da lista. `call FUN_10024560` (0x1001de84): reset.
2. `mov al,[ebx]` com `ebx = body`: `count = body[0]`. `edi = i = 0`.
3. Por iteração: `lea ecx,[edi+ebx+1]` (= `&body[1+i]`), `push ecx`, `call FUN_100230a0`, `mov ecx,eax`, `call FUN_1001c170` (0x1001de9d). `FUN_1001c170` é `RET 4`: o ponteiro empilhado é o argumento.
4. Laço fecha com `movzx edx,[ebx]` e `cmp edi,edx`; depois `NotifyChannelInfo`.

O decompilador mostra `FUN_1001c170(puVar5)` e omite o argumento de pilha. A nota anterior de `channel_server.md` §3.1 ("o corpo não é passado") estava errada e foi corrigida.

Lista interna (singleton, `this` de `FUN_1001c170`):

- Sentinela em `+4`. Size em `+8` (dword). `FUN_10024560` zera `+8` e religa a sentinela.
- Nó de 12 bytes criado por `FUN_10019640` (`asm@0x10019640`, `push 0x0c`): `{next u32 @0, prev u32 @4, value u8 @8}`.
- `FUN_1001c170` insere antes da sentinela: `next = sentinela`, `prev = último`, `value = *(u8*)ptr`, onde `ptr = &body[1+i]`. Há um helper com argumento `1` (provável incremento de size; inferido).

Leitores:

- `FUN_10006b45`: contagem = `size` (+8) como `u8`. Base de `GetChannelCount`.
- `FUN_10007fb2`: `GetChannelInfo(index, out u8)`. Retorna falso se `index >= size`; senão percorre `index` nós a partir de `sentinela.next` e devolve `node.value`. Assinatura da UI: `GetChannelInfo(byte index, byte load_factor)` (`LM_Engine.src.txt` L954).
- `GetChannelInfoList` (`XInterface.src.txt` L18622-18640) repete `GetChannelInfo(0..N-1)` e preenche `Channels`. Se uma chamada falha, retorna falso.
- `RefreshLists` (`XInterface.src.txt` L64310) chama `GetChannelInfoList(Channels)` e depois `SetItems`. `OnChannelInfo` (L24444-24460) mostra o painel com `GetChannelCount() > 0`.

### Por que aparece "0 | MARZ | FULL" (inferido, bate com o observado)

- Com `count = 1` e sem byte em @1, `body[1]` lê o byte seguinte ao frame. O caso 0x6f não tem guarda de tamanho (`disp@978-992`, `asm@0x1001de7d..`). O valor é lixo do buffer de recepção.
- Se o lixo for >= 100: `Channels[0] >= 100`. A UI faz `strLoadFactor = strLoadFactors[6]` ("FULL") e `CurMenuState = MSAT_Disabled` (`XInterface.src.txt` L64059-64062).
- Colunas de `InternalOnDrawItem` (L64096-64140): coluna 0 = `i $ ""`; coluna 1 = `i @ strChannel` (pelo código, "0 MARZ"; o relato mostra "MARZ", verificar se é só resumo); coluna 2 = `strLoadFactor`.
- Não há mais nenhum valor de canal no fio. O FULL depende do byte que cair fora do pacote.

### Faixas de carga (UI)

Em `InternalOnDrawItem` (`XInterface.src.txt` L64035-64071), com `strLoadFactors[7]` (L64003, localizados em `localize`):

| `Channels[i]` | texto (índice) | `CurMenuState` |
|---|---|---|
| >= 100 | "FULL" ([6]) | `MSAT_Disabled` (não clicável) |
| > 80 | "Tumulto" ([5]) | ativo |
| > 50 | "Bom" ([4]) | ativo |
| demais | "Ótimo" ([3]) | ativo |

Os índices [0..2] estão comentados (L64074-64089).

### Clique: pedido 120 IN_CHANNEL

- UI (`XInterface.src.txt` L64203-64215): `if (Channels[Index] < 100)` então `NetInChannel(Index)`. Se falhar, mostra a mensagem 121000201 com `%c` = Index.
- `NetInChannel(num)` (L17258) → `ServerInterface.InChannel(num)` (L21631), que seta `ConnectedChannel = num` após sucesso.
- Pedido 120 (`channel_interface.c` L59-60, `0x10002390`): `lit 0xf00`, `N = p ? 6 : 2`, corpo `u32 @0` = `Index` (linha 0-based da UI). Ou seja, 6 bytes = cabeçalho 2 + 4 bytes do corpo. (inferido: o id enviado é a posição na lista.)
- Se `Channels[Index] >= 100`, o botão está `MSAT_Disabled` e nada é enviado.
- Resposta 121 `NotifyInChannel` (`disp@2772-2824`): `i32 @0` = id. `< 0` é erro (`FUN_10021c80`). `>= 0` cria ou acha o nó do canal e guarda `_DAT_1005aa88 = i32 @0`.

### Proposta de payload para o servidor (inferida do código)

`[u8 N][u8 carga_0]...[u8 carga_{N-1}]`, com carga 0..100 normal e >= 100 = FULL. Sem nome nem id no 111. Nome = `strChannel` + índice local. Se a intenção for mostrar a carga real, o servidor precisa mandar os N bytes; com N=1 e um byte só, o cliente lê o byte certo.

---

## Convenções

- Frame: `u16` LE tamanho, `u16` cabeçalho = `(opcode << 5) | net_code`. Channel usa `net_code = 14` (`channel_helpers.c` cabeçalho; `channel_server.md` §1).
- Pedidos: `channel_interface.c`. `N` é o tamanho total do pacote.
- Respostas: `channel_dispatch_FUN_1001da60.c`. Envelope `0x36`: `u16 @0` = opcode real, `i32 @4` = erro. Erro diferente de 0 dispara `NotifyErrorMessage`, e o dispatch continua no mesmo buffer (inferido).

---

## 1. Criar sala

1. UI: `CreateRoom` (`XInterface.src.txt` L60120-60192) → `NetCreateRoom(name, pw, scale, mode, map_num, max_player, team_count, limit_time, limit_score)` (L17277).
2. UnrealScript `LM_ServerInterface.CreateRoom` (`LM_Engine.src.txt` L1603-1617): comando `/CreateRoom` com 9 parâmetros nesta ordem.
3. Pedido 301 (`FUN_10001580`, `AX = 0x12d`, `N = 76`): corpo de 74 bytes = 18 dwords (@0..@71) + `u16 @72` (`channel_helpers.c` L47-52; `channel_server.md` §2 L69). Corpo decodificado (`tools/re/LM_Engine.dll/FUN_10017530_CreateRoom.c`, `tools/re/layouts_f0.md` §7.1): `u16 map_num @0` (p4); `char[51] name @2` (p0, sem limite); `char[13] pw @0x35` (p1, sem limite); `u8 game_scale @0x42` (p2); `u8 game_mode @0x43` (p3); `u8 team_count @0x44` (p6); `u8 max_player @0x45` (p5); `u8 limit_time @0x46` (p7); `u16 limit_score @0x48` (p8).
4. Resposta 302 `NotifyCreateRoom`: o corpo vai para `FUN_1001d640` (insere a sala) e depois notifica (`disp@1312-1347`). Layout do registro de sala: **gap**.

## 2. Entrar na sala

1. UI: `NetInRoom(num, password)` (L17284) → `InRoom(num, pw)` (`LM_Engine.src.txt` L1619): `/InRoom` com 2 parâmetros.
2. Pedido 311 (`FUN_10001620`, `AX = 0x137`, `N = 22`): corpo de 20 bytes = 5 dwords (`channel_helpers.c` L55-61). Mapeamento: `i32 num @0`, `char pw[16] @4` (resumo da rodada anterior; `tools/re/layouts_f0.md` §7.2).
3. Resposta 312 `NotifyInRoom` (`disp@1348-1349` e `2858-2934`):
   - `i32 @0` = resultado. Se `< 0`: código `i16 @0` via `FUN_10021c80`; copia `u8 @8..@0x0e` para o nó `+0x48..+0x4e`; `i16 @0x10` para `+0x50`; grava `-1` em `i32 @4` e `i32 @8` (inferido: marca registro inválido).
   - Envelope `0x36` com erro `0xfffff04b` retorna sem notificar.
   - Ramo de sucesso: **gap**.
4. Estado da sala após entrar:
   - 314 `NotifyRoomInfo` (`disp@1350-1388`): `i16 @0 → +0x54`; `u8 @2..4 → +0x56..+0x58`; `i32 @8 → +0x5c`; a partir de `@0x0c`: `u8 @0x10 → +0x48`, `@0x11 → +0x49`, `@0x12 → +0x4a`, `@0x13 → +0x4d`, `@0x14 → +0x4e`; `i16 @0x16 → +0x50`; `i32 @0x2c → +0x178`; `i32 @0x30 → +0x17c`; `i16 @0x34 → +0x180`; `i16 @0x36 → +0x182`. A chave de busca é o corpo a partir de `@0x0c` (`FUN_10019e90`; tipo não decodificado).
   - 317 `NotifyRoomPlayerInfo` (`disp@1389-1473`): `u8 @0` = count; `i32 @1` = chave da lista; registros de 0x30 bytes em `B = 0x1a + 0x30·i`. Campos principais: `i32 @(B-0x19) → +0xa0`, `u8 @B → +0x23`, `u8 @(B+0x0f)` = índice de inserção. Atualiza ou insere com `FUN_1001d640` e notifica.
   - 549 `NotifyInRoom` (`disp@608-691`, outra rota com o mesmo evento): `u8 @0x28` = índice do jogador; `i32 @0` gravado em `sala + 0x60 + 4·idx`; contador `sala+0x4b` se `idx < 0x3c`, senão `sala+0x4c` (`disp@670-681`).
   - Conflito de offset de slots: ver seção 10.

## 3. Sair da sala

1. UI: `OutRoom()` (`LM_Engine.src.txt` L1628) → pedido 321 (`0x100024d0`, `lit 0x2820`, `N = 2`, sem corpo; `channel_interface` L64 e tabela §2).
2. Resposta 322 `NotifyOutRoom` (`disp@173-248`): `i32 @0 → _DAT_1005aa74` (lido; uso não decodificado); corpo passado ao evento.
3. Troca de dono: 332 `NotifyChangeRoomMaster` (`disp@256-284`): layout **gap**. Conflito de offset (seção 10).
4. Sala removida: 342 `NotifyRemoveRoom` (`disp@285-298`): layout **gap**.
5. Saída durante a partida: pedido 500 `ExitPlay()` (`0x10002740`, `lit 16000`, `N = 2`, sem corpo) → resposta 501 `NotifyExitPlay` (`disp@424-427`): `i32 @0 → _DAT_1005aa58`.

## 4. Slot e time

1. UI: `NetChangeRoomSlot(num)` (XInterface L17330) → `ChangeRoomSlot(num)` (`LM_Engine.src.txt` L1680): `/ChangeRoomSlot`, 1 parâmetro.
2. Pedido 420 (`lit 0x3480`, `N = p ? 3 : 2`): `u8 @0` = num (`channel_server.md` L74; `channel_interface.c` L66-67). A troca de grupo (657, `lit 0x5220`) usa o mesmo corpo e não entra no fluxo de sala.
3. Resposta 421 `NotifyChangeRoomSlot` (`disp@382-406`): layout **gap**. Evento de UI `NotifyChangeRoomSlot(client_guid, slot_num)` (`XInterface.src.txt` L23714-23717) → `OnChangeRoomSlot(nParam0, byte nParam1)` (L17522).
4. `ChangeRoomSlot` tem chamador: `ChangeTeam()` (`XInterface` L21737-21790), que exige `MyInfo.position == 0x23` e jogador não pronto. Calcula `MyTeam = i % MyRoom.team_count` e envia `ChangeRoomSlot(++MyTeam % team_count)`. Logo o `u8` do 420 é o grupo, não o slot; o servidor escolhe o primeiro slot livre do grupo (D66). **(inferido do UnrealScript, não observado no cliente.)** `tools/re/features.md` §6.1 (L287) já cita `ChangeTeam`; `NetChangeRoomSlot` segue sem chamador.
5. Propriedades da sala (modo, mapa, limites):
   - Pedido 411 (`FUN_100016e0`, `AX = 0x19b`, `N = 12`): corpo de 10 bytes; empacotamento abaixo (corrige a versão anterior `u32 @0`, `u32 @4`, `u16 @8`).
   - UnrealScript `ChangeRoomProperty` (`LM_Engine.src.txt` L1636-1678) envia **7** valores em `/ChangeRoomProperty`: `flags, map_num, game_mode, team_count, max_player, limit_time, limit_score`. Empacotamento decodificado (`FUN_10017820`, `tools/re/layouts_f0.md` §7.2): `u8 flags @0`; `u16 map @2` (se MAP); `u8 game_mode @4` e `u8 team_count @5` (se MODE); `u8 max_player @6`, `u8 limit_time @7`, `u16 limit_score @8` (sempre). 10 bytes.
   - Flags (`dump_Core.txt` L1194-1212): `ROOM_PROPERTY_MAP = 0x01`, `MODE = 0x02`, `LIMIT_PLAYER = 0x04`, `LIMIT_SCORE = 0x08`, `LIMIT_TIME = 0x10`, `STATE = 0x20`, `OPEN = 0x40`. `TEAM_DAMAGE = 0x0F` no dump, valor suspeito (conferir).
   - Resposta 412 `NotifyChangeRoomProperty` (`disp@352-381`): `u8 @4` é máscara: bit0 → `i16 @6`; bit1 → `u8 @8`, `u8 @9`; bit2 → `u8 @10`; bit3 → `i16 @0xc`; bit4 → `u8 @0xb`; bit5 → `u8 @0xf`; bit6 → `u8 @0xe`.
   - Evento de UI `NotifyChangeRoomProperty(map_num, game_mode, max_player, limit_time, limit_score)` (`XInterface.src.txt` L23704) recebe 5 campos e não a máscara: mapeamento bit → campo é **gap**.
   - Lista de salas: 547 (`disp@541-576`, `u8 @0` = count, entradas de 16 bytes a partir de `@4` (room_guid @4; state @8 … open @14; `u16 @0x10` → +0x50, gap; `tools/re/layouts_f0.md` §4.2)).

## 5. Pronto (jogador)

1. UI: `NetReadyGame(selected_morats: byte)` (XInterface L17379) → `ReadyGame` (`LM_Engine.src.txt` L1715): `/ReadyGame`, 1 parâmetro (decimal).
2. Pedido 401 (`lit 0x3220`, `N = p ? 3 : 2`): `u8 @0` = `selected_morats` (**inferido**: máscara de morats).
3. Resposta 402 `NotifyReadyGame` (`disp@299-300`, `2825-2853`):
   - Sem erro no envelope: acha o nó da sala pelo corpo (`FUN_10007830`), testa `FUN_10018aa0` e, se verdadeiro, chama `FUN_1001d640` sobre `nó+0xa4`.
   - `u8 @4` = flag: bit0 faz XOR em `+0xac`; `i32 @8 → +0xb4`.
   - `+0xb0` = `0x24` se flag ≠ 0 e `registro+0x38 == 1`; `0x23` se flag = 0 (**inferido**).
   - Chama `NotifyReadyGame(corpo, erro)` e zera `_DAT_1005aa84`.
4. Evento de UI `NotifyReadyGame(client_guid, ready, result)` (`XInterface.src.txt` L23652-23681):
   - `result` de erro vira diálogo: `CERR_ROOM_STATE_PLAYING` → 212000200; `CERR_READY_CLOSE_CHANNEL` → 300000502; `CERR_READY_GAME_DURABILITY` → 241002501; `CERR_READY_GAME_CLOSE` → 211002102; `CERR_READY_GAME_TEAMREADY` → 241002502; `CERR_READY_GAME_TEAMBALANCE` → 241002602; `CERR_READY_GAME_READY` → 241002702.
   - Sem erro: `OwnerPage.OnNotify(NType_ReadyGame, client_guid, ready)`.
   - Valores numéricos dos `CERR_*`: resolvidos (`dump_Core.txt` L1212-1340; `tools/re/layouts_f0.md` §7.3). Correspondência entre `(corpo, erro)` nativo e `(client_guid, ready, result)` do evento: **gap**.

## 6. Chat da sala

1. UI/UnrealScript: `SendMsg(msg_type, msg)` (`LM_Engine.src.txt` L1547) → `/SendMsg`, 2 parâmetros, `msg_type` como decimal.
2. Pedido 240 (`FUN_10001790`, `AX = 0xf0`, `N = len + 4`): corpo `u16 @0` = `p[0..1]`, `len = p[1]`, texto a partir de `@2` (`channel_server.md` L67; `channel_helpers.c` L71-78). O tipo de mensagem `p[0]` e o escopo (sala ou canal) **não estão decodificados**: gap.
3. Eco 241 `NotifySendMsg` (`disp@1246-1280`): `u8 @5 = len`; texto a partir de `@8`. Ramo `len > 0x78` não decodificado (gap).

## 7. Convite e expulsão

- Convite:
  - UI: `NetRoomInvite(nickname)` → `RoomInvite` (`LM_Engine.src.txt` L1697): `/RoomInvite`, 1 parâmetro.
  - Pedido 461 (`FUN_10001420`, `AX = 0x1cd`, `N = 19`): 17 bytes = 4 dwords + `u8 @16` (`channel_interface.c` L117-126). Mapeamento de nickname: **inferido**.
  - Resposta 463 `NotifyRoomInvite` (`disp@416-423`): `i32 @0 → DAT_1005aa90`. Resposta 462 `NotifyResultRoomInvite` (`disp@407-415`): layout **gap**.
  - Aceite: `NetRoomInviteAnswer(yes_no, room_guid)` → `RoomInviteAnswer` (L1705): `"Y"/"N"` como string e `room_guid` como decimal. Pedido 471 (`lit 0x3ae0`, `N = 10`): `u32 @0` = yes/no, `u32 @4` = room_guid (**inferido**).
- Expulsão pelo dono:
  - UI: `NetRoomExpel(nickname)` → `RoomExpel` (`LM_Engine.src.txt` L1689): `/RoomExpel`, 1 parâmetro → pedido 451 (`FUN_10001830`, `AX = 0x1c3`, `N = 20`): 18 bytes = 4 dwords (@0..@12) + `u16 @16` (`channel_server.md` L75).
  - Resposta a 451: não há `case` 452 no dispatcher; a resposta de expulsão de sala é **gap** (`tools/re/layouts_f0.md` §7.5). A expulsão confirmada pelo cliente é 701 (resposta a 700).
  - `NetExpelPlayer(position, nickname)` (`XInterface.src.txt`, logo após `NetExitPlayer` L17387) → `ExpelPlayer` (`LM_Engine.src.txt` L1730, `/ExpelPlayer`, 2 parâmetros) → pedido 700 (mesmo `FUN_10001830`, `AX = 0x2bc`, `N = 20`).
  - Resposta 701 `NotifyExpelPlayer` (`disp@2386-2387`, `428-431`): `i32 @0 → _DAT_1005aa54`, compartilha código com 501.
  - Mapeamento de `position` em 700 e `u16 @16`: **gap** (a versão de 451 não tem posição).

---

## 8. Início de partida (dono)

1. O dono envia 401 (seção 5). Gatilho exato na UI (`DoReady`, `XInterface.src.txt` L28649 e L35301) não lido em detalhe: **gap**.
2. 402 atualiza os flags (seção 5).
3. Quando o Channel decide iniciar, envia 403 `NotifyStartGame` (`disp@301-346`, label `case 0x193`):
   - Corpo de 18 bytes: 4 dwords @0..@15, copiados para `_DAT_1005ac34..40`; `u16 @16` → `_DAT_1005ac44`.
   - Pré-condição (**inferido**): o cliente já tem o próprio nó de jogador (key `DAT_1005ada0`, vindo do 101) com a chave da sala em `+0xa4`. Quem grava `+0xa4`: 317 e 549 (sala do próprio jogador, `disp@1438`/`disp@650`); 312 grava `body@0` (`tools/re/layouts_f0.md` §1.2).
   - `FUN_10007830(FUN_10023470(), &it, &DAT_1005ada0)` acha o próprio jogador (`it`); `FUN_10018aa0` testa `it != fim`. Se não achar, nada é feito (o `if` engloba o laço e as gravações abaixo).
   - Se achar: `FUN_1001d640(FUN_10023500(), it+0xa4)` devolve a sala. Os slots de jogador ficam em `sala+0x50` (`piVar22 + 0x14`), 0x3c entradas. Para cada slot diferente de -1, `FUN_1001d5d0` devolve o jogador; se o bit0 de `+0x9c` estiver setado, grava `0x24` em `+0xa0` (valor, ver §10.5).
   - Depois grava `it+0xb0 = 0x24` no próprio jogador (estado "jogando", **inferido**) e copia os dwords e o `u16` para `_DAT_1005ac34..44`.
   - Chama `ULM_ServerInterface::NotifyStartGame(g_server_interface, body)` → evento `NotifyStartGame(string address, int port)` (`XInterface.src.txt` L23684-23687): `OwnerPage.OnNotify(NType_StartGame, port, , , address)`.
   - Conversão fechada: `address` = C-string de `body[0..15]` (`FString(char*)`) e `port` = `u16 body[0x10]` (`tools/re/LM_Engine.dll/NotifyStartGame_0x10004440.c`). Ligação aos parâmetros do evento: (inferido).
4. Cliente: `OnStartGame(strAddress, nPort)` (`XInterface.src.txt` L29632-29667): `super.OnStartGame`; se o endereço está vazio ou `port < 0`, ou se `GetMyPlayerInfo` falha, chama `OnReadyGameError(0)`. Senão grava `PendingAddress = strAddress` e `PendingPort = nPort`.
   - `OnReadyGameError` (L29668+): `KillTimer`, reabilita botões, zera `Pending*`, mostra erro por código.
5. Conexão ao servidor de jogo com `PendingAddress:PendingPort`: caminho não lido (**gap**; ver `bStartGame` L22800 e L64824-64838).

## 9. GS: 1010, 1011, 1020, 1002 e resultado

Detalhe completo em `channel_server.md` §4.

- 1010 `GS_IN_PLAYER` (Channel → GS): `u8 @0x84` flag; `u8 @0x85` slot; `i32 @0x88` room guid; `i32 @0x8c` chave; registro `@0x90..0xa0`. Corpo mínimo 0xa1 bytes. Valida room guid contra `ServerRoom+0`.
- 1011 reply (GS → Channel): 16 bytes: `i32 @0` resultado (0 ou −4000, `0xfffff060`), `i32 @4` room guid (eco), `i32 @8` chave (eco), `u8 @12` flag (eco), `u8 @13` slot (eco). Frame de 18 bytes. Bytes 14..15 não escritos (**inferido**: lixo da pilha).
- 1020 `GS_OUT_PLAYER` (Channel → GS): `i32 @0` room guid, `i32 @4` chave. Sem resposta. Remove o jogador por chave (`CServerRoom::OutPlayer`, `0x100171c0`).
- 1002 (Channel → GS): `i32 @0`; se 0, `GIsRequestingExit = 1`.
- Resultado da partida: 512 `NotifyGameResult` (`disp@432-487`), corpo `CS_GAME_RESULT_OUT`: `i32 @0` comparado com `DAT_1005ada0`; `i32 @4 → +0x3c`; `i32 @8 → +0x5c`; `i16 @0xc`; `i32 @0x10 → +0x40`. Evento de UI `NotifyGameResult(client_guid)` (`XInterface.src.txt` L23708-23712 → L17521 `OnGameResult`).
- Origem do 512 no GS: **gap**. `FUN_1000bcd0` não tem o opcode 512 (`channel_server.md` §6.6).

---

## 10. Lacunas, conflitos e perguntas para o REA

1. Mapeamento dos dwords de 301 (CreateRoom, 74 bytes) e de 311 (InRoom, 20 bytes) para os parâmetros do UnrealScript.
2. 411 (ChangeRoomProperty): 10 bytes para 7 valores. Como empacota `flags`, `map_num`, `game_mode`, `team_count`, `max_player`, `limit_time`, `limit_score`?
3. Layout completo do registro de sala (302, 314 além dos bytes lidos) e de 317.
4. Layouts ainda sem decodificação: 342, 421, 462, 543 (raw), 332. 412 (máscara) e 547 (passo) foram fechados em `channel_server.md` §3.1 e `tools/re/layouts_f0.md` §4.2.
5. Offset de slots, resolvido por bytes de retorno (inferido): `FUN_1001d640` e `FUN_1001d5d0` devolvem `nó+0x10` (valor; `add eax,0x10` em `asm@0x1001d640` e `asm@0x1001d5d0`), enquanto `FUN_10019e90` e `FUN_10007830` devolvem o nó pelo out-param. Logo `+0x50` relativo ao valor = `+0x60` relativo ao nó (317 e 421 vs 312, 314, 322, 549). Os pares 402/403 (`+0xac/+0xb0` vs `+0x9c/+0xa0`) batem com a mesma regra. Não verificado: o par 101/121 (`guid` em `+0` do valor vs `+0xa0`).
6. Estado e dono (resolvido em parte). Estado: `+0x38` (302, 314, 412 @0x0F, 547 @0x04), com valores `RS_WAITING = 0` e `RS_PLAYING = 1` dos UConst de `Core.u` (D65). Dono: `master` (302 @0x4C), comparado a `MyInfo.client_guid` em `RefreshPlayers` (`XInterface` L34690–34830); o 332 troca o `master`.
7. Conversão de 403 fechada (`tools/re/LM_Engine.dll/NotifyStartGame_0x10004440.c`).
8. Quem envia 403 e sob qual condição. O binário cliente só recebe; a decisão de iniciar fica no Channel server. `+0xa4` gravado por 317, 549 e 312 (`tools/re/layouts_f0.md` §1.2).
9. `CERR_*` resolvidos (`tools/re/layouts_f0.md` §7.3); `MT_*` e `GM_*` continuam sem valor.
10. Resposta de 451 (RoomExpel): sem `case` 452 no dispatcher (`tools/re/layouts_f0.md` §7.5); aberto.
11. 111 sem guarda de tamanho: confirmar se o framing do Channel garante que o corpo tem pelo menos `count + 1` bytes antes do dispatch (`FUN_10025120`/entrada de rede não analisada).
12. Origem do 512 (resultado) no GS.
13. Envelope `0x36`: se o corpo real começa em `@0` do mesmo buffer (**inferido**).
14. Correção aplicada: `channel_server.md` linha 139 (111) e linhas 323 e 329 (layout lido e gap) foram ajustadas a partir deste documento.
15. Revisão de D40 (549 e 312): não é a causa de o dono ver os botões desabilitados. Na criação, `_joined` roda com `others=[]`, então o criador recebe o 312 e grava o próprio `+0xa4` e `+0xb0 = 0x23`. Confirmado no servidor; no cliente real, não testado.
16. Lista de salas e de jogadores em sessão: o caso 0x97 (151) põe `+0xb0 = 0x22` em todo nó da lista, inclusive o do próprio jogador (`channel_dispatch_FUN_1001da60.c` L1223-1225). Logo um 464 de quem está numa sala tira a posição 0x23 dele. O servidor não responde a esse caso (D67).

## 11. Dono sem pronto: Config (411) e Mudar grupo (420)

1. Config: `LM_RoomPage.InternalOnClick`, `case SettingBtn` (XInterface 28955–28968), abre `LM_RoomSettingPage` só com `MyRoom.state == 0 && !MyInfo.ready_game && MyRoom.master == MyInfo.client_guid`. Quem não é dono não abre o diálogo (guarda de dono, por design). `LM_MatchRoomPage` (35497–35504) abre sem guarda; é a página da sala de partida (uso de clã não verificado em detalhe).
2. Mudar grupo: `ChangeTeam` (XInterface 21734–21755) não envia o 420 se `MyInfo.position != 0x23 || MyInfo.ready_game`. O botão (28909) chama sem checar.
3. Opções e Sair: `OptionBtn` (28893) e `ExitBtn` (28902) também dependem de `!ready_game`.
4. Causa do bloqueio do dono: o servidor criava o dono com `ready=1`. As três guardas barravam sem pacote. O entrante tem `ready=0` e passa em Mudar grupo.
5. Início: `EnterGame` (XInterface 29464) aborta se `!MyInfo.ready_game` quando o endereço chega (403). A contagem (29351) só começa com um 402 em estado PLAYING cujo `client_guid` é o do jogador ou o do dono. O servidor manda o 402 do dono pronto junto do 403 e, com ele, a contagem começa em todos os clientes da sala.
6. Efeito do 402 no nó (`da60.c`, dispatcher do canal, linhas 2835–2845): o bit0 de `+0xac` recebe o flag de forma absoluta (`X ^ ((flag ^ X) & 1)` deixa só o bit0 igual ao flag); `+0xb4` recebe os morats; `+0xb0` vira 0x24 se o estado é PLAYING e o flag é não zero, e 0x23 no caso de flag zero. Na espera, flag zero devolve a posição 0x23.
7. Iniciar do dono: no ramo do dono (XInterface 28116–28147), o botão fica ativo por `IsReadyToStart` (27164), que conta o dono pelo `client_guid`. O critério de início não depende do pronto do dono.

Status: causa confirmada pelo código do cliente. Não confirmada no cliente real (roteiro em `docs/operations/game-server.md`).

Config para quem não é dono (D156): o `SettingBtn` não é desabilitado no ramo `!bSetGroup` para não-dono, e o guard do clique em `LM_MatchRoomPage` está comentado. É regra do cliente. O emulador recusa o 411 de não-dono sem resposta; nada muda no servidor.

## 12. Depósito (586 e 587)

1. Botão: `OnHanger` (XInterface 28984–28989 na sala e 35520–35524 na sala de partida) chama `EnterHanger()`, que envia 586 (`InHangar`, sem corpo; `protocol_full.md` §3.1).
2. Resposta 587 `NotifyEnterHanger(bool)` (`protocol_full.md` §3.2): `i32 @0` = chave; o evento recebe `(i32 @0 == DAT_1005ada0)`, ou seja, se a chave é a do próprio jogador.
3. `OnEnterHanger` (XInterface 28991–29018): com `MoveHanger` verdadeiro, troca a página por `xInterface.LM_HangerPage`; caso contrário, só atualiza a lista de jogadores.
4. Servidor: 586 de quem está em sala responde 587 com o próprio guid, só ao pedinte (`RoomHandlers.enter_hangar`). Fora de sala não há resposta; o cliente não tem caso para resposta negativa.
5. Inventário: `LM_HangerPage` usa o cache do login (102/103), e o servidor não reenvia. Não confirmado no cliente real.
6. Inferido: 588 (`LeaveHanger`) chega do cliente; o emulador não tinha handler para ele, e o cliente ficava no depósito (sem linha de log citada). O emulador responde 589 com a chave e `u8 @4 = 0x23` (D151). O 589 só é aplicado com o nó na posição 0x25 (`case 0x24d` do dispatcher, `tools/re/LM_Engine.dll`). Validação no cliente pendente.
7. Botão: `MainMenuBtns[4]` fica desativado para o dono com pronto (XInterface 28149–28153). O índice do botão Depósito está no defaultproperties, que não foi extraído do `.u`.

## 13. Ficha do jogador (543)

1. Layout: `LM_PLAYER_DETAIL_INFO` (`dump_LM_Engine.txt`, 2023–2050): `strNickName`, `nTotalRank`, `nTotalGamecount`, `nTotalWin`, `nTotalLose`, `nTotalKill`, `nTotalDeath`, `nHeadshot`, `nTotalExp`, `ucNest`, `nClanMark`, `strClanName`. O dispatcher passa o corpo direto como `PLAYER_INFO_DETAIL*` (`da60.c`, 531–536).
2. Rótulos (`LM_PlayerInfoPage`, XInterface 32801–32805): `MilitaryRecordLbl` recebe `%t` = `nTotalGamecount` (Partida), `%w` = `nTotalWin` (V) e `%l` = `nTotalLose` (D).
3. Offsets (inferidos da ordem da struct, com `char[20]` no nick e `i32` nos inteiros): jogos @0x18, vitórias @0x1C, derrotas @0x20.
4. Porcentagem de abandono (XInterface 32813): `(jogos − vitórias − derrotas) × 100 / jogos`. Empates entram nessa conta como abandono.
5. Estado: o emulador envia zero para os três campos. Preencher a partir de `match_players` fica para depois.