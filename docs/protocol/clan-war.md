# Guerra de clã: fluxo no cliente e no canal

Mapa do fluxo de clã (somente leitura do cliente, `re/LM_Engine.dll` e fontes `XInterface`/`LM_Engine`).
Estados: **confirmado** = lido no código ou na fonte; **inferido** = dedução indicada no texto;
**gap** = não decodificado.

O emulador hoje só faz o que está confirmado nesta página: o canal de clã pode ser anunciado com
`channel_mode` 6 (`LANDMASS_CHANNELS`, campo `mode`). Os opcodes 640 a 662 não são atendidos pelo
canal; o fluxo abaixo fica como referência para a implementação.

## 1. Fluxo

1. **Entrada no canal de clã.** A conexão passa por `NetInChannelServer`/`NetInChannel`
   (`XInterface` L17230 a L17262). `InChannelServer` (L21555 a L21607) liga `bInClanServer` só quando
   `server_info.channel_mode == CM_CLAN` (L21591). `CM_CLAN` vale **6** (`Core.u`, constantes
   `CM_BEGINNER` 0 a `CM_CLAN` 6; **confirmado**). O campo vem do byte @0x04 de cada entrada da
   Message 131 (`docs/protocol/message-server.md`). `NotifyInChannelServer` (L22775 a L22811)
   zera `bRegisterGroup`, põe `nMyTeamSlot = -1` e `bStartGame = true`. `OnInRoom` (L17884 a L17897)
   abre `LM_MatchRoomPage` quando `bInClanServer`. A lista de salas de clã está em `LM_CampPage`
   (L64640 a L64906); a origem dessa lista é gap (ver G9).
2. **Criar grupo (640 e 641).** Em `LM_MatchRoomPage` (L35443 a L35481) só o mestre dispara
   `RegisterGroup`. C→S 640, S→C 641 `NotifyRegisterGroup(bool)`; `OnRegisterGroup` (L35562 a L35576).
   O cliente grava `bRegisterGroup = !bRegister` (L23796 a L23801). Qual valor significa "registrado"
   é **inferido** (campo sugere que 0 é registrado).
3. **Desafiar (642 a 644).** `LM_MatchingGroupList` faz `Reset` e `GetMatchingGroupList`
   (L36379 a L36381). C→S 642 recebe S→C 643 com a lista de grupos (chave = `room_guid`).
   Ao escolher, `RequestMatch` chama `GetRequestMatch(channel_num, room_guid)` (L36481 a L36491) e
   manda C→S 644. S→C 648 `NotifyRequestMatch` leva o clã do desafiante em @0x50
   (`OnRequestMatch`, L36164 a L36182). Quem recebe 648 é gap (G4).
4. **Aceitar, recusar, cancelar, expirar (645 a 652).** `LM_RequestMatchPage` (L31132 a L31362):
   aceitar manda C→S 645 e recebe S→C 650, que abre `LM_MatchRoomPage` (`OnAcceptMatch`,
   L36199 a L36206). Recusar: C→S 646, S→C 651 (`OnRejectMatch`, msg 211000900). Cancelar pelo
   desafiante: C→S 647, S→C 652 (`OnCancelMatch`, msg 211001100). Expiração local: `TimeOver`
   (L31301 a L31309). Pedido devolvido: S→C 649 (`OnReturnRequestMatch`, L36184 a L36197; msg
   211001500 quando `group_guid <= 0`).
5. **Formação de times (650, 653, 654, 657, 658, 661, 662).** 650 traz os dois grupos (primeiro
   `home_team = 1`, segundo `home_team = 0`). `LM_MatchRoomPage.InitComponent` (L34299 a L34452)
   monta `GroupInfo[0..1]`. O time do jogador local é o grupo cujo `clan_code` é igual a
   `MyInfo.siClan`; sem casamento, cai em `GroupInfo[1]` (L35936 a L35945). Trocar de slot: o botão
   manda `ChangeGroupSlot((nTeamSlot + 1) % 2)` (L35443 a L35481) → C→S 657 (`u8` slot) → S→C 658
   (`OnChangeGroupSlot`, L36242 a L36270). Entrada de jogadores: 661 (um por vez) ou 653/654
   (roster inteiro com contagem).
6. **Início (401 a 403 e conexão).** Pré-condições da contagem (L35784 a L35805): sala em
   `RS_PLAYING`, os dois líderes com `ready_game`, cada cliente com o nó do líder adversário
   (vindo de 653, 654, 661 ou 662). Sem isso não há `ClientTravel`. Contagem de 10 s e `EnterGame`
   (L35852 a L35876). `EnterGame` monta `protocolo://endereço:porta?name=...?key=room_guid?team=...?voice=...`
   (L35984 a L35990) e chama `ClientTravel(url, TRAVEL_Absolute)` (L36008). `key` é o `room_guid`
   do grupo do próprio jogador (L35988). Endereço e porta vêm de 403 (`OnStartGame`, L36028 a L36057).
   O canal decide quando mandar 403 (**gap**: o opcode que dispara 401/403 no canal não está em
   640 a 659, G10).
7. **Resultado e fim (655, 656, 660).** Clã: S→C 660 `NotifyMatchResult` (`OnMatchResult`,
   L36288 a L36325) grava `clan_point`, `point`, `win` e `lose` na sala e no grupo; a UI não mostra
   placar. Fim da partida: C→S 655 (`EndMatch`), S→C 656 `NotifyEndMatch` (`OnEndMatch`,
   L36208 a L36228), que zera a tabela de slots da sala. Depois vem o roster (653 ou 654).

## 2. Opcodes 640 a 662

| Op | Dir | Nome | Corpo (offsets) | Fonte | Estado |
|---:|:---:|------|-----------------|-------|--------|
| 640 | C→S | RegisterGroup | 2 bytes; conteúdo não decodificado | `channel_interface.c` L96 a L106 (`lit 0x5000`) | opcode e tamanho confirmados; conteúdo gap (G2) |
| 641 | S→C | NotifyRegisterGroup | `u8 @0` (bool). Erro de envelope `0xfffff03b` suprime o evento | dispatch L1479 a L1481, L1632 a L1636; XInterface L23796 a L23801 | confirmado |
| 642 | C→S | GetMatchingGroup | 2 bytes; `lit 0x5040` | `channel_interface.c` | opcode confirmado; corpo inferido |
| 643 | S→C | NotifyMatchingGroupList | `u16 count @0`; registros de 0x24 a partir de `@2`: `i32 channel @0`, `i32 room_guid @4` (chave), `u16 map_num @8`, `u8 game_mode @0xa`, `u8 curr_player @0xb`, `i32 clan_mark @0xc`, nome ANSI NUL-terminado em `@0x10` (até 0x14 bytes) | dispatch L1667 a L1700 (laço 1682 a 1693); `10009ce0` L77 a L107 | confirmado |
| 644 | C→S | GetRequestMatch | `i32 channel @0`, `i32 room_guid @4` (`atoi` de `param[0]` e `param[1]`); 10 ou 2 bytes | wrapper `100188c0`; `lit 0x5080` | campos confirmados; tamanho inferido |
| 645 | C→S | GetAcceptMatch | igual a 644 | wrapper `10018920`; `lit 0x50a0` | wrapper confirmado; tamanho inferido |
| 646 | C→S | GetRejectMatch | não decodificado | wrapper `10018980`; `lit 0x50c0` | opcode confirmado |
| 647 | C→S | CancelMatch | `channel = atoi(param+0x28)`; `group_guid = atoi(param+0xa1)` (struct `CS_REQUEST_MATCH_IN`); `lit 0x50e0` | wrapper `FUN_10018a40` | confirmado no código do wrapper; forma no fio inferida |
| 648 | S→C | NotifyRequestMatch | bytes `0x00` a `0x4f` não decodificados; clã de 80 bytes em `@0x50` (0x14 dwords) copiado para `DAT_1005adb0` | dispatch L1701 a L1711 | cópia confirmada; prefixo gap (G3) |
| 649 | S→C | NotifyReturnRequestMatch | clã de 80 bytes em `@0` copiado para `DAT_1005adb0`; guardas `0xfffff042`, `41`, `40`, `3f` | dispatch L1712 a L1737 | confirmado |
| 650 | S→C | NotifyAcceptMatch | dois registros em `@0` e `@0x40`, cada um de 0x40 bytes (staging de 0x44). Por registro: `i32 channel @0`, `i32 room_guid @4` (chave), `u8 team @0x34`; `home_team` em `+0x40` do staging: 1 no primeiro, 0 no segundo | dispatch L1738 a L1861 | layout parcial confirmado |
| 651 | S→C | NotifyRejectMatch | sem corpo lido | dispatch L1862 a L1865 | evento confirmado |
| 652 | S→C | NotifyCancelMatch | sem corpo lido | dispatch L1866 a L1869 | evento confirmado |
| 653 | S→C | roster (termina em `NotifyRoomPlayerInfo`) | `u8 count @0`; registros de 0x30 a partir de `@1` (`R = body + 1 + 0x30·i`): `u32 chave R+0`, `R+4 → nó+0x3c`, `R+8..R+0x14 → nó+0x10..0x1c`, `u8 R+0x18 → nó+0x20`, `u8 R+0x19 → nó+0x23`, `u8 R+0x1a → nó+0x21`, `u32 R+0x1c → nó+0x28` (clan_code), `u32 R+0x20 → nó+0x2c`, `u8 R+0x24 → nó+0x30`, `u8 R+0x28` = slot (índice `[slot+0x5d]`), `R+0x29`, `R+0x2a`, `R+0x2b` e `u32 R+0x2c` → flags `nó+0xac`, `nó+0xb0`, `nó+0x90`, `nó+0xb4`. Antes zera a tabela de slots `nó+0x184..0x27f` (0x3c dwords = -1) | dispatch L1870 a L1973; saída para `LAB_10020a0e` (L2116) | layout confirmado pelo código; nomes gap (G5) |
| 654 | S→C | roster (variante de 653) | mesmo registro de 653. Diferença: a sala é achada pelo nó do próprio jogador (`nó+0xa4`) e a chave é comparada com ele; sem guarda de `clan_code` | dispatch L1974 a L2076; saída para L2116 | confirmado; diferença fina inferida |
| 655 | C→S | EndMatch | 2 bytes; `lit 0x51e0` | wrapper `100189e0` | opcode confirmado |
| 656 | S→C | NotifyEndMatch | sem corpo além da busca. Zera a tabela de slots `nó+0x184..0x27f`. Se `nó+0xa0 == sala+0x5c` (mestre), limpa bit0 de `nó+0xac` | dispatch L2077 a L2114 (`return` em L2112 a L2114) | confirmado |
| 657 | C→S | ChangeGroupSlot | `u8 slot @0` (low byte de `atoi(param[0])`); 2 ou 3 bytes; `lit 0x5220` | wrapper `10018a00` | confirmado |
| 658 | S→C | NotifyChangeGroupSlot | `u8 @0` = slot de casa; `u8 @1` = slot de fora. Para cada grupo: `nó+0x44` (team) = `body[1]` se `nó+0x50` (`home_team`) == 0; senão `body[0]` | dispatch L1640 a L1667 (guarda `0xfffff03c` em L1642) | confirmado |
| 659 | C→S | RefreshClanMatchInfo (requisição) | `count = atoi(param+0x28)` (máx. 8; acima de 8 vira 9); até 9 tokens a partir de `param+0xa1`; `AX = 0x293`, 42 bytes | wrapper `10018740`; `channel_interface.c` | confirmado |
| 659 | S→C | NotifyRefreshMatchRoomList | `u8 count @0`; registros de 0x30 a partir de `@4` (12 dwords) copiados para `nó+0x10` da sala. A chave é sempre `body+4` (L2124), mesmo com `count > 1` | dispatch L2119 a L2154 (evento L2152) | confirmado; nomes dos campos gap (G6) |
| 660 | S→C | NotifyMatchResult | dois registros de stride 0x14, chaves em `@0` e `@0x14`. Em cada: `i32 clan_point @4` (`@0x18` no segundo), `i32 point @8` (`@0x1c`), `u16 win @0xc` (`@0x20`), `u16 lose @0xe` (`@0x22`); `@0x10..0x13` não lidos. Escreve na sala `+0x178`, `+0x17c`, `+0x180`, `+0x182` e no grupo `+0x20`, `+0x3c`, `+0x40`, `+0x42` | dispatch L2155 a L2210 (evento L2208) | confirmado |
| 661 | S→C | NotifyClanInsertPlayer | registro único; alcance máximo até `@0x2f`, então pelo menos 0x30 bytes (inferido). `u32 chave @0`, `@4 → nó+0x3c`, `@8..0x14 → nó+0x10..0x1c`, `u8 @0x18/@0x19/@0x1a → nó+0x20/+0x23/+0x21`, `u32 clan_code @0x1c`, `u32 @0x20 → nó+0x2c`, `u8 @0x24 → nó+0x30`, `u8 @0x28` = slot, `u8 @0x29/@0x2a/@0x2b`, `u32 @0x2c` | dispatch L2211 a L2296 (ramo 2293; `break` 2296); tail 2431 a 2436 | fluxo confirmado; campos e tamanho inferidos |
| 662 | S→C | NotifyClanInsertPlayer (variante) | mesmo padrão de 661; `goto LAB_10021279` em L2319, L2350 e L2380 | dispatch L2297 a L2382 | inferido pela estrutura; campos não decodificados |

Opcodes 644 a 647 e 655 e 657 (C→S) não têm case S→C no dispatcher: ao chegar do servidor caem no
`default` (L1698 a L1700) e não geram evento. Isso é esperado; não são respostas.

## 3. Bloco de clã e canal de partida

- `648` e `649` gravam o clã de 80 bytes em `DAT_1005adb0`. `execGetMatchClanInfo` (`100070b0`)
  lê esse bloco e monta `LM_MATCH_CLAN_INFO`: `channel_num @0`, `room_guid @4`, `curr_player` u8
  `@8`, `clan_code @0xc`, `clan_mark @0x10`, `ranking @0x14`, `win @0x18`, `lose @0x1c` (lido de
  `src 0x20`), `clan_point @0x20` (lido de `src 0x28`), `clan_name` FString `@0x24` (ANSI em
  `src 0x2c`, até 17 bytes), `leader_name` FString `@0x30` (ANSI em `src 0x3d`). `src 0x1c` e
  `src 0x24` não são lidos. Confirmado pelo código.
- O GS de clã recebe as opções pela linha de comando. A `Init` nativa (`100163d0`, L112 a L231) lê
  `channel` (L112), `room_guid` (L117, vira `+0x0`), `port` (L122), `map_num` (L127), `game_type`
  (L196, vira `+0x5e4`; padrão 1 em L102), `home_clan` (L201, `+0x5ec`), `away_clan` (L206, `+0x5f0`),
  `home_clan_point` (L211, `+0x5f4`), `away_clan_point` (L216, `+0x5f8`), `away_channel` (L221, byte
  `+0x5fc`), `away_room` (L226, `+0x600`) e `away_team` (L231, byte `+0x5e9`). Não há parse nativo de
  `home_team`, `team`, `key` ou `name`. `home_team` é lido só pelo UnrealScript:
  `LM_DeathMatch`, `GetIntOption(Options, "home_team", 0)` (XGame L15664).
- `game_type == 6` é o teste nativo de modo de clã (`1000bcd0` L39 a L40 e L59 a L60; `LoginPlayer`
  L18; `GameOutPlayer` `1000c020` L103 a L108). `6` é `CM_CLAN`: a equivalência está confirmada pelos
  dois lados (**confirmado** na constante, **inferido** no uso como tipo de partida).
- A chave de um jogador visitante é o `room_guid` do grupo visitante; no modo 6 ela só é aceita se
  bater com `away_room` (`+0x600`). Logo `away_room` precisa ser o `room_guid` desse grupo.

## 4. Lacunas

- **G2.** Conteúdo dos corpos de 640, 642, 645, 646, 655 e 657 (só tamanhos e wrappers conhecidos).
  O significado do bool de 640 não foi decodificado.
- **G3.** Prefixo de 648 (bytes `0x00` a `0x4f`) e o clã de 80 bytes de 649.
- **G4.** Quem recebe 648 e 649 (o mestre do grupo, todos os membros?).
- **G5.** Nomes e semântica do meio de 650, de 653 e 654 (nomes dos campos do registro de 0x30 e a
  diferença exata entre 653 e 654) e de 661 e 662.
- **G6.** Campos nomeados do registro de 0x30 de 659 S→C; só o primeiro dword (`room_guid`) é inferido.
- **G7.** Caminho GS → canal que gera 660. Não consta em `channel-server.md` §4.
- **G8.** Chamador de `Cmanager_interface::SetResultClanMatch` (`+manager_interface 0x10007f00`,
  `FUN_10004140`, cabeçalho `(net & 0x1f) | (0x488 << 5)`, corpo de 12 bytes, N = 14, porta 7310).
  Sem chamador no cliente; a semântica dos 12 bytes é desconhecida.
- **G9.** Origem da lista de salas de clã (opcodes 142, 143 e 144, usados por `LM_CampPage`) e quem
  chama 659. O único painel de clã extraído é `LM_ClanRoomPlayerListPanel` (`XInterface` L62224).
- **G10.** Opcode de `Ready` (`DoReady`, L35301 a L35330) e o opcode que gera 401 e 403 no canal.
  Ambos ficam fora de 640 a 659.
- **G11.** Como se calculam `clan_point`, `win` e `lose`. Não há lógica no cliente. Recompensa de
  clã também não foi encontrada: o clã não tem regra de recompensa confirmada.
- **G12.** Opcodes `0x25A` a `0x281` caem num fall-through artefato da guarda (L1479 a L1481).
- **G13.** `FUN_1001d640` (inserção no array de slots) não foi verificado. Os índices
  `[slot+0x14]` e `[slot+0x5d]` assumem base `nó+0x10`, o mesmo padrão confirmado em `1001d9c0` e
  `1001d910`. Logo `nó+0x60` e `nó+0x184`.
- **G1 resolvida.** `CM_CLAN` = 6 em `Core.u`.

## 5. Correções ao `re/protocol_full.md` (registro)

- L167 (linha 640) e §6 item 4 (L331): dizem que 641 não é tratado. Errado: 641 chama
  `NotifyRegisterGroup(body[0])` em L1636 (guarda em L1479 a L1481).
- L276 e L277 (653 e 654, "sem evento"): errado. Ambos saem por `break` para `LAB_10020a0e` (L2116),
  que chama `NotifyRoomPlayerInfo` (L1473 a L1474).
- L278 e §6 item 5 (656): "senão `goto LAB_10020a0e` (L2116)" está errado. 656 retorna em L2112 a
  L2114 e não usa `goto`. O `goto` de L2116 é a saída de 653 e 654.
- L282 e L283 (661 e 662, "sem evento; `goto LAB_10021279`"): o evento existe.
  `LAB_10021279` chama `NotifyClanInsertPlayer` (L2435 a L2436).
- L281 (660): o evento está certo, mas 660 também escreve os nós de grupo (`+0x20`, `+0x3c`, `+0x40`,
  `+0x42`), não só a sala.
- Layouts de 643 (L270) e 650 (L273) estão corretos em linha geral, mas sem os offsets descritos aqui.

## 6. O que o emulador faz

- `channel_mode` do LM_SERVER_INFO vem de `LANDMASS_CHANNELS[].mode` (padrão 0). Com 6, o canal é
  anunciado como clã (D199).
- Os opcodes 640 a 662 não são roteados pelo canal. Nenhum evento de clã é enviado. Um cliente que
  entra num canal de clã vê a tela de clã sem partidas: esse é o limite atual.
- Para implementar o fluxo, a ordem sugerida é: 640/641 e 642/643 (grupos), 644 a 652 (pedido e
  resposta), 657/658, 655/656 e 660. Antes de codificar 640, 642, 645 e 648, resolver G2 e G3 com
  captura do cliente real.
