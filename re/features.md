# LandMass: funcionalidades de jogo (engenharia reversa do cliente, somente leitura)

Cliente: `D:\landmass\cliente\system` (Unreal Engine 2.5, 2008-2009). Fonte da verdade: o cliente.

## Fontes e convenções

- UnrealScript: strings UTF-16 extraídas dos `.u` com `scratchpad\src_extract.py` (preserva quebras de linha).
  - `LM_Engine.u` (classe `LM_ServerInterface`): `scratchpad\src\LM_Engine.src.txt`, 2450 linhas.
  - `XInterface.u` (UI, 65 936 linhas extraídas): `scratchpad\src\XInterface.src.txt`.
  - `XGame.u` (regras de partida, 16 868 linhas): `scratchpad\src\XGame.src.txt`.
  - `XEffects.u`: 1 linha extraída, sem fonte embutida. Não usado.
  - Números de linha citados são deste texto extraído, não do `.u` binário.
- Banco estático: `landmass.wdb` (SQLite), cópia em `scratchpad\client_landmass.db`. Nas tabelas citadas, `tabela.coluna` ou `tabela.key`.
- DLL de rede: `+server_interface.dll`. Os nomes dos métodos vêm dos símbolos C++ (`?Nome@Cmessage_interface@@`).
- Opcodes do Channel: `re\channel_server.md` (seção 2). Opcodes do Message: `re\message_server.md` (seção 5, opcodes 100 a 150). Só nomes e números de opcode são citados aqui. Layouts de pacote do Channel ficam com o outro agente.
- Banco legado: `D:\landmass\servidor\db\LM_account.sql` (UTF-16, 31 `CREATE TABLE`). Usado só como pista de nomes.
- Abreviações: **MS** = Message Server (TCP 7313, `Cmessage_interface`); **CS** = Channel Server (TCP 7314, `Cchannel_interface`); **UE2** = servidor de partida, para o qual o cliente é redirecionado por `NotifyStartGame(address, port)`.
- `(inferido)` = dedução a partir de evidência indireta. Sem marca = visto diretamente no código ou no banco.
- Este relatório não usou o MCP `rea`, não abriu o jogo e não alterou nada fora de `re\`.

Outros `.wdb` (formato proprietário, magic `f7 db 00 00 72 f3 31 01`, conforme `re\NOTES.md`; não reverificado nesta rodada): `ClientMessage.wdb`, `error.wdb` (erros), `notice.wdb` (avisos), `string.wdb` (strings). `landmass.wdb` é o único SQLite.

## 0. Como o cliente fala com os servidores

### 0.1 Cadeia de chamada (vale para todas as seções)

1. **Pedido de rede pela página**: `LM_ServerInterfacePage.NetXxx()` (XInterface, classe em 16614-17995). Ex.: `NetLogin`, `NetCreateRoom`, `NetRoomInvite`. Ou a página chama `ServerInterface.Xxx()` direto.
2. **Montagem do pedido** (`LM_ServerInterface`, LM_Engine.u): cada método `function bool Xxx(...)` monta `LM_COMMAND_PARAM` com `param.order = "/Xxx"` e chama o nativo `Command(param)`.
3. **Despacho nativo**: `Command` entrega o pedido a `+server_interface.dll`, que escolhe o método `Cmessage_interface::X` (MS) ou `Cchannel_interface::X` (CS).
4. **Resposta**: a DLL chama `LM_ServerInterfaceBridge.NotifyXxx(...)` (XInterface 22067-23926). Cada handler faz `OwnerPage.OnNotify(NType_Xxx, ...)`.
5. **Dispatch de página**: `LM_ServerInterfacePage.OnNotify` (17422) faz `switch(eNType)` e chama `OnXxx(...)`. A página ativa sobrescreve `OnXxx`.

A enum `LM_ServerInterface.eNotifyType` (LM_Engine, linhas 157-268) define os tipos de notificação. As seções MS e CS estão misturadas nela.

**Aviso sobre o script:** os blocos de `LM_ServerInterface` estão rotulados como "MessageServer Function" (linha ~1317), mas o bloco de `/SendMsg` em diante (`/SendMsg`, `/InChannel`, `/CreateRoom`, etc.) é CS. A tabela 0.2 segue a DLL, não o comentário.

**Pós-login automático**: `LM_ServerInterfaceBridge.NotifyInMessageServer` (XInterface, 22343-22372). Se `result == NERR_OK`: se `clan_code > 0`, chama `GetClanList()` e `GetClanMember()`; sempre chama `GetFriendList()`; depois `OwnerPage.OnNotify(NType_RankingInfo)` sem pedido de ranking (ver seção 9).

### 0.2 Mapa /Comando -> método da DLL -> opcode

Todos os wrappers de `LM_ServerInterface` (LM_Engine.u). Opcode indicado só quando documentado em `re\*.md`.

| /Comando (UnrealScript) | Servidor | Método na DLL | Opcode | Fonte do mapeamento |
|---|---|---|---|---|
| `/Login` | MS | `Cmessage_interface::Login` | 100 | `message_server.md` 5.1 |
| `/GuidLogin` | MS | `Login` (com GUID) | 100 | `message_server.md` linha 157 (inferido) |
| `/Register` | MS | `Register` | 110 | `message_server.md` 5.2 |
| `/InMessageServer` | MS | `InMessageServer` | 120 | `message_server.md` 5.3 |
| `/NetDisConnect` (`OutAllServer`) | MS | `Disconnect` (inferido) | - | nome não é igual |
| `/CheckNickname` | MS | `CheckNickname` | 140 | `message_server.md` 5.5 |
| `/CreateNickname` | MS | `CreateNickname` | 150 | `message_server.md` 5.6 |
| `/UpdateNickname` | MS | `UpdateNickname` | não documentado | lacuna |
| `/GetChannelServer` | MS | `GetChannelServerInfo` | 130 | `message_server.md` 5.4 |
| `/SendWhisper` | MS | `SendWhisper` | não documentado | lacuna |
| `/GetRankingInfo` | MS | `GetRankingInfo` | não documentado | lacuna; sem chamador na UI |
| `/GetClanList` | MS | `GetClanInfo` | não documentado | nome não é igual (inferido) |
| `/GetClanMember` | MS | `GetClanMember` | não documentado | lacuna |
| `/SendClanMessage` | MS | `SendClanMessage` | não documentado | lacuna |
| `/RefreshClanList` | MS | `RefreshClanList` | não documentado | lacuna |
| `/GetFriendList` | MS | `GetFriendList` | não documentado | lacuna |
| `/AddFriendList` | MS | `AddFriendList` | não documentado | lacuna |
| `/GetDelFriendList` | MS | `GetDelFriendList` | não documentado | lacuna |
| `/RefreshFriendList` | MS | `RefreshFriendList` | não documentado | lacuna |
| `/AddBlackList` | MS | `AddBlackList` | não documentado | lacuna |
| `/GetDelBlackList` | MS | `GetDelBlackList` | não documentado | lacuna |
| `/RefreshBlackList` | MS | `RefreshBlackList` | não documentado | lacuna |
| `/SendMsg` | CS | `SendMsg` | 240 | `channel_server.md` seção 2 |
| `/SendCommand` | CS | `SendCommand` | 250 | `channel_server.md` seção 2 |
| `/InChannelServer` | CS | `InChannelServer` | 100 | `channel_server.md` seção 2 |
| `/OutChannelServer` | CS | sem método nomeado (inferido: `Disconnect`) | - | lacuna |
| `/InChannel` | CS | `InChannel` | 120 | `channel_server.md` seção 2 |
| `/OutChannel` | CS | `OutChannel` | 122 | `channel_server.md` seção 2 |
| `/GetPlayerList` | CS | `GetChannelPlayerInfo` | 464 | `channel_server.md` seção 2 |
| `/DetailRoomInfo` | CS | `GetChannelRoomDetail` | 540 | `channel_server.md` seção 2 |
| `/DetailPlayerInfo` | CS | `GetChannelPlayerDetail` | 542 | `channel_server.md` seção 2 |
| `/SaveOption` | CS | `SaveOption` | 544 | `channel_server.md` seção 2 |
| `/CreateRoom` | CS | `CreateRoom` | 301 | `channel_server.md` seção 2 |
| `/InRoom` | CS | `InRoom` | 311 | `channel_server.md` seção 2 |
| `/OutRoom` | CS | `OutRoom` | 321 | `channel_server.md` seção 2 |
| `/ReadyGame` | CS | `ReadyGame` | 401 | `channel_server.md` seção 2 |
| `/ChangeRoomProperty` | CS | `ChangeRoomProperty` | 411 | `channel_server.md` seção 2 |
| `/ChangeRoomSlot` | CS | `ChangeRoomSlot` | 420 | `channel_server.md` seção 2 |
| `/RoomExpel` | CS | `RoomExpel` | 451 | `channel_server.md` seção 2 |
| `/RoomInvite` | CS | `RoomInvite` | 461 | `channel_server.md` seção 2 |
| `/RoomInviteAnswer` | CS | `RoomInviteAnswer` | 471 | `channel_server.md` seção 2 |
| `/ExitPlay` | CS | `ExitPlay` | 500 | `channel_server.md` seção 2 |
| `/ExpelPlayer` | CS | `ExpelPlayer` | 700 | `channel_server.md` seção 2 |
| `/SetRegular` | CS | `SetRegular` | 105 | `channel_server.md` seção 2 |
| `/RefreshRoomList` | CS | `RefreshRoomList` | 545 | `channel_server.md` seção 2 |
| `/RefreshPlayerList` | CS | `RefreshPlayerList` | 546 | `channel_server.md` seção 2 |
| `/RefreshMatchRoomList` | - | sem método correspondente (lacuna) | - | sem chamador na UI |
| `GetMatchClanInfo` (nativo, sem /Comando) | CS | `RefreshClanMatchInfo` (inferido) | 659 | `channel_server.md` seção 2 |
| `/ItemBuy` | CS | `ItemBuy` | 550 | `channel_server.md` seção 2 |
| `/ItemGift` | CS | `ItemGift` | 615 | `channel_server.md` seção 2 |
| `/GetGiftItem` | CS | `GetGiftItem` | 610 | `channel_server.md` seção 2 |
| `/GiftItemUsed` | CS | `GiftItemUsed` | 612 | `channel_server.md` seção 2; sem chamador na UI |
| `/ItemDestroy` | CS | `ItemDestroy` | 555 | `channel_server.md` seção 2 |
| `/ItemUsed` | CS | `ItemUsed` | 560 | `channel_server.md` seção 2 |
| `/ItemUsedByValue` | CS | sem método na DLL (inferido: `ItemUsed` com valor) | - | lacuna |
| `/ItemUnused` | CS | `ItemUnused` | 570 | `channel_server.md` seção 2 |
| `/ItemExtend` | CS | `ItemExtend` | 580 | `channel_server.md` seção 2 |
| `/GetSystemItemState` | CS | sem método na DLL | - | lacuna |
| `/EnterHanger` | CS | `InHangar` | 586 | `channel_server.md` seção 2 |
| `/LeaveHanger` | CS | `OutHangar` | 588 | `channel_server.md` seção 2; sem chamador na UI |
| `/TutorialClear` | CS | `ClearTutorial` | 600 | `channel_server.md` seção 2 |
| `/RegisterGroup` | CS | `RegisterGroup` | 640 | `channel_server.md` seção 2 |
| `/GetMatchingGroupList` | CS | `GetMatchingGroup` | 642 | `channel_server.md` seção 2 |
| `/GetRequestMatch` | CS | `RequestMatch` | 644 | `channel_server.md` seção 2 |
| `/GetAcceptMatch` | CS | `AcceptMatch` | 645 | `channel_server.md` seção 2 |
| `/GetRejectMatch` | CS | `RejectMatch` | 646 | `channel_server.md` seção 2 |
| `/CancelMatch` | CS | `CancelMatch` | 647 | `channel_server.md` seção 2 |
| `/EndMatch` | CS | `EndMatch` | 655 | `channel_server.md` seção 2 |
| `/ChangeGroupSlot` | CS | `ChangeGroupSlot` | 657 | `channel_server.md` seção 2 |
| `/Delay` | local | não é pedido de rede (`Command` local) | - | LM_Engine |

Requisições da DLL sem wrapper no UnrealScript (só pelo nativo): `RequestRoomList` (67), `SendLobbySpecInfo` (66), `RequestSubChannnelInfo` (64), `LoginServerMonitor`, `RegisterChannelServer` (68), `RequestForceUserQuit` (72). `RequestForceUserQuit` é de administração (seção 12).

### 0.3 Formato de ID de item (regra estática)

`LM_ServerInterface.GetItemClassify(ID)` (LM_Engine, ~1159-1177), com `group = ID / 1e8`, `class = (ID / 1e6) % 100`, `type = (ID / 1e4) % 100`, `index = ID % 1e4`.

- `GROUP_ITEM`: 0 NONE, 1 MORATS, 2 EQUIP, 3 ITEM, 4 EFFECT.
- `CLASS_ITEM`: 1 WEAPON, 2 GENERATOR, 3 BOOSTER, 4 CHIP, 5 RESOURCE, 6 NPC, 7 SKIN, 8 SYSTEM, 9 SPECIAL.
- `CLASS_MORATS`: 1 ASSAULT, 2 SNIPER, 3 DEFENDER, 4 ENGINEER, 5 SPECIAL.
- `TYPE_SYSTEM`: 1 ONCE, 2 BUFF, 3-7 NOTUSED0-4, 8 GIFT.
- Exemplos verificados no banco: `307010002` = "Desert" (grupo 3, classe 7 SKIN, tipo 1). `308010006` = "Item Surpresa" (grupo 3, classe 8 SYSTEM, tipo 1 ONCE). `308020001` = "Aumento de EXP" (classe 8, tipo 2 BUFF). `201030001` = "AT-01" (grupo 2 EQUIP, classe 1 WEAPON, tipo 3 RIFLE). `101000001` = "AU-TP02" (grupo 1 MORATS, classe 1 ASSAULT).

## 1. Missões (tutorial e objetivos de partida) e quests

**Quests: inexistente no cliente.** A busca `\bquest\b` (sem diferenciar maiúsculas) retorna 0 ocorrências em `XInterface.u`, `XGame.u` e `LM_Engine.u`. As 272 ocorrências do termo "quest" em XInterface são de `Question` (`GUIQuestionPage`, `LM_QuestionPage`), que é diálogo.

### 1.1 Tutorial

- **Servidor:** CS.
- **Pedido:** `ClearTutorial(CS_CLEAR_TUTORIAL_IN)` (opcode 600), via `/TutorialClear` (`ClearTutorialStep(Byte)`, LM_Engine).
- **Resposta:** `NotifyTutorialClear(int Tutorial, int Point, int Result)` (`LM_ServerInterfaceBridge.NotifyTutorialClear`, XInterface 23761) -> `OnNotify(NType_TutorialClear)` -> `OnTutorialClear`.
- **UI:** `LM_TutorialCompletePage.InternalOnClick` (XInterface 6080-6125). Pelo passo atual, `LM_Tutorial(...).m_iTutorialStep` (TS_Move, TS_Shoot, TS_Engineer), envia `ClearTutorialStep(0|1|2)` se o bit ainda não estiver marcado. Bits: `iTutorialClear & 0x0001` (movimento), `& 0x0002` (tiro), `& 0x0004` (engenheiro).
- **Estado do jogador:** `LM_PLAYER_INFO.iTutorialClear` (LM_Engine). Lido via `GetMyPlayerInfo`.
- **Telas:** `LM_TutorialMenuListPanel`, `LM_TutorialMainTextPanel`, `LM_TutorialHud` (`DrawOperationInfo` em 2300), `LM_TutorialExplainPage`, `LM_TutorialEndPage`, `LM_TutorialCompletePage`, `LM_TutorialBasePage`. Regras de partida do tutorial em `XGame.LM_Tutorial` (XGame 497-4179).
- **Dados estáticos:** nenhum no `landmass.wdb` para o tutorial (textos em `localize`, se houver).
- **Persistido (proposta):** `accounts.tutorial_flags` (inteiro com os bits acima). Sem tabela própria.
- **Regra visível:** 3 passos fixos. Cada passo marca um bit único. Não há tabela de recompensa de tutorial no cliente. `NotifyTutorialClear` recebe `Point` e `Result`, mas o valor de `Point` não foi rastreado até a UI (lacuna).

### 1.2 Missões de partida (objetivos de modo OP e BR)

- **Servidor:** UE2 (cálculo de recompensa no fim da partida, `XGame`). Não há pedido de rede para missão.
- **Recompensa OP:** em `XGame.LM_TeamOperation` (XGame ~6524-6604):
  - `missionBonusExp = pri.m_iServiceScore * GameRewardConstant.OP_MissionBonusExp` (linha 6582).
  - `Experience = killExp + takeExp + winExp + missionBonusExp` (6584).
  - `missionBonusMoney = missionBonusExp * GameRewardConstant.OP_MissionBonusPoint` (6602).
  - `Money = killMoney + takeMoney + winMoney + missionBonusMoney` (6604).
- **Recompensa BR:** `GameRewardConstant.BR_MissionBonusExp`, `BR_MissionAssistExp`, `BR_MissionBonusPoint`. Usadas no mesmo `XGame` de modo BR.
- **Dados estáticos:** `GameRewardConstant` (47 linhas, `landmass.wdb`). Valores de missão: `OP_MissionBonusExp=10`, `OP_MissionBonusPoint=1`, `BR_MissionBonusExp=10`, `BR_MissionAssistExp=15`, `BR_MissionBonusPoint=1`. Os defaults no código (`XGame.LM_DeathMatch`, linhas 15318-15333) são 10.0, 10.0 (OP), 30.0, 18.0 e 1.0. Os valores do banco sobrescrevem os defaults (inferido: carga em `XGame` com `case "BR_MissionBonusExp": ...`, linhas 15538-15557).
- **Carga das constantes:** `DBCommand("SELECT key, value FROM GameRewardConstant")` (XGame, classe `LM_DeathMatch`). Grava em `GameRewardConstant.<key>`.
- **Persistido (proposta):** nenhum. Recompensa é calculada na partida e somada em `player_stats` e `accounts` (ver seção 11). Constantes: tabela `game_reward_constants` (estática, espelho do banco).
- **Regra visível:** multiplicadores por modo (DM, TDM, OP, BR) em `GameRewardConstant`. Multiplicador global: `ExpMult`, `MoneyMult` (ambos 1). Bônus de PC-room: `PCRoomBonusExp` e `PCRoomBonusPoint` (1 e 1), ver seção 11.

## 2. Loja

### 2.1 Catálogo (estático, cliente)

- **`item` (1210 linhas, 14 itens):** consumíveis de sistema (grupo 3, classe 8) e skins (classe 7). Ex.: `308010001` "Queima de Arquivo" (cash 16800), `308010004` "Troca de Função" (cash 20000), `308010005` "Adicionar Hangar" (cash 15000), `308020001` "Aumento de EXP" (cash `[5600, 22400, 39200, 67200]`, LD `[9900, 39600, 69300, 118800]`), `308020002` "Aumento de LD", `308020003` "Ressurreição", `308010006` "Item Surpresa". Chaves por item: `item_buy_cash[0..3]`, `item_buy_point[0..3]`, `item_buy_type`, `item_name`, `item_life_time`, `item_limited_time`, `item_effect`, `item_alias`, etc.
- **`Item_Equip` (61 itens, 113 chaves):** armas, peças e geradores (grupo 2). Chaves `item_id`, `item_name`, `item_company`, `item_factory`, `item_buy_cash[0..3]`, `item_buy_point[0..3]`, `item_buy_type`, `item_required_level/nest/nest_point/clan/clan_rank/class/rank/strength/agility/precision/power`, `item_slot`, `item_type`, `item_weapon_type`, `item_newitem`, `item_life_time`, `item_limited_time`, `strToolTipDiscription`.
- **`Morats` (9 espécies, 81 a 84 linhas cada):** seções `XGame.SPECIES_AssaultA/B`, `DefenderA/B`, `EngineerA/B`, `SniperA/B`, `SpecialA`. Chaves `id`, `name`, `type`, `slot`, `power`, `hit_point`, `buy_cash[0..3]`, `buy_point[0..3]`, `buy_type`, `required_level/nest/nest_point/clan/clan_rank/class/rank/strength/agility/power`, `limited_time`, `life_time`.
- **`supply` (91 linhas):** catálogo de fabricantes. Tipos: `nest` (ids 1-3: Oddeye, Shadow, Leon), `company` (ex.: "A&T"), `factory` (`product_type` 1 weapon, 2 morats, 3 generator, 4 booster, 5 chip, 6 e 7 outros), `discount_nest` e `discount_clan` (ex.: 10 por cento, marcado como temporário no banco). **Sem leitor no UnrealScript** (lacuna: pode ser lido pelo nativo).
- **`maps` (23 linhas)**, `LevelList` (101 linhas; `event` = `select_nest` e `enable_gift` definem níveis de gate).

**Carga:** `ServerInterfaceBridge.GetETCItemClassByID` (XInterface 23940) lê `Morats`, `Item_Equip` ou `item` pela classe do ID, com `SELECT section FROM <tabela> WHERE type='<ID>' AND value='<ID>'`. `DBCommand("SELECT type, key, value FROM item")` no cache de itens.

### 2.2 Compra

- **Servidor:** CS.
- **Pedido:** `ItemBuy(CS_ITEM_BUY_IN)` (opcode 550). Parâmetros: `nItemID`, `bPoint` (true = LD), `nBuyOption`.
- **Resposta:** `NotifyItemBuy(int result)` (CS, opcode 551, XInterface 22858) -> `OnItemBuy(nResult)`. `LM_SupplyPage.OnItemBuy` (8925) chama `RefreshLD()`. Erros: `GetMessageString(nResult)` (tabela `msg_error`).
- **UI:** `LM_SupplyBuyPopPage.InternalOnClose` (XInterface 12160-12232), via `GetBuyOption()` (12148).
- **Mapeamento de opção** (`GetBuyOption` -> `InternalOnClose`):
  - `0,1,2,3`: LD (`bPoint=true`), duração índice 0-3 = 1, 7, 14, 30 dias.
  - `4,5,6,7`: cash (`bPoint=false`), duração `BuyOpt-4`.
  - `8`: LD, `nBuyOption=0`, igual à opção 0 (inferido: sem duração própria; o pacote não distingue 8 de 0).
  - `9`: cash, `nBuyOption=0`, igual à opção 0 (mesma ressalva do caso 8).
  - Duração `BUY_OPTION` (LM_Engine): `BUY_OPTION1`, `BUY_OPTION7`, `BUY_OPTION14`, `BUY_OPTION30`.
- **Morats:** `LM_SupplyMoratsBuyPopPage.InternalOnClose` (XInterface ~9258) chama `ItemBuy` com o ID de espécie. Resposta `NotifyMoratsBuy` (CS, opcode 552) -> `LM_SupplyPage.OnMoratsBuy` (8918).
- **Preço:** `LM_SupplyMoratsBuyPopPage.HandleParameters` (9198) exibe `nPoint*5 @ PointUnit`. Lógica de preço: `item_buy_cash/point[opção]` do banco, lido pelos `GetSaleItemInfo`/`GetWeaponSaleItemInfo`/`GetMoratsSaleItemInfo` (`LM_ServerInterfaceBridge`, 19138-19516). `nCash[4]` e `nPoint[4]` do `LM_SALE_ITEM` vêm daí.
- **Requisitos:** `LM_SALE_ITEM.nNeed*` (`nNeedClass`, `nNeedNest`, `nNeedPoint`, `nNeedClan`, `nNeedClanRank`, `nNeedLevel`, `nNeedRank`, `nNeedStrength`, `nNeedAgility`, `nNeedPrecision`, `nNeedPower`) vêm dos defaults das classes UnrealScript (`WeaponClass.Default.item_required_*`, `MoratsClass.Default.required_*`). Mostrados em tooltip. **Não encontrei o ponto que bloqueia o botão de compra por requisito no cliente** (lacuna; o servidor deve validar).
- **Persistido (proposta):** `item_prices` e `item_requirements` (espelho estático de servidor, para validar preço e requisito). Compra gera linha em `inventory_items` (seção 3).
- **Regra visível:** preço por opção de duração e moeda. Requisito de nível/clã/patente/etc. exibido. Presente exige patente (ver 2.3).

### 2.3 Presente

- **Servidor:** CS.
- **Pedidos:** `ItemGift(CS_ITEM_GIFT_IN)` (615), com `strNick` do destinatário. `GetGiftItem(CS_GET_GIFTITEM_IN)` (610) paginado de 12 itens por página (`LM_HangerPage`, `SupplyInvenListPanel.SlotItems.length == 12`).
- **Respostas:** `NotifyItemGift(int)` (CS, opcode 616, `channel_server.md` §3.2) -> `OnItemGift` (`LM_SupplyPage`). `NotifyGetGiftItem(result, Page)` (CS, opcode 611) -> `OnGetGiftItem` (`LM_HangerPage`, 45839).
- **Resgate (claim):** `GiftItemUsed(CS_GIFTITEM_USED_IN)` (612) tem wrapper, mas **nenhum chamador na UI**. Os handlers `OnGiftItemUsed` (45853) e `OnGiftMoratsUsed` (45874) só recarregam a lista. Não há pedido `GiftMoratsUsed` (lacuna: resgate de morat presente não tem request no cliente).
- **Regra visível:** presente exige patente mínima. Mensagem `231000304` = "Para mandar presente a sua patente mínima tem que ser %s", com `LevelInfos[EnableGiftLevel].LevelName` (XInterface, 12024 e 22970). `EnableGiftLevel` vem de `LevelList` com `event = 'enable_gift'` (`PrecessLevelList`, LM_Engine).
- **Dados estáticos:** `item` / `Item_Equip` (catálogo). `LM_GIFT_INFO` (siIdx, siItemIdx, strItemGuid, Buy_Option, strNick).
- **Persistido (proposta):** `gifts` (sender_account_id, receiver_account_id, item_id, buy_option, claimed_at), **pendente até o resgate**. Não é log.
- **Regra visível:** o presente não cria item no inventário do remetente. Vira item pendente para o destinatário.

### 2.4 Gacha / item surpresa

- **Servidor:** CS (`NotifyGetGatchaPrize`, opcode 591, `channel_server.md` §3.2), empurrado pelo servidor. Não há pedido no cliente (inferido: disparado pelo uso do item `308010006` "Item Surpresa").
- **Resposta:** `NotifyGetGatchaPrize(array<LM_GATCHA_PRIZE>)` (XInterface 23916) -> `OnGetGatchaPrize` (`LM_HangerPage`, 45889) -> abre `LM_GatchaPopupPage` (48864-48980, `SetListItems`).
- **Estrutura** `LM_GATCHA_PRIZE`: `item_id`, `size` (quantidade, "LD" nos comentários), `buy_option`, `description`.
- **Persistido (proposta):** o prêmio entra em `inventory_items` (ou em `accounts.point_balance` quando for LD). Sem tabela de sorteio.

## 3. Inventário, hangar e itens

### 3.1 Hangar (entrada e saída)

- **Servidor:** CS.
- **Entrada:** `EnterHanger()` (`/EnterHanger` -> `InHangar`, opcode 586). Chamado em `LM_RoomPage` (28986) e `LM_MatchRoomPage` (35522). Resposta `NotifyEnterHanger(bool)` -> `OnEnterHanger`.
- **Saída:** `LeaveHanger()` (`/LeaveHanger` -> `OutHangar`, opcode 588) tem wrapper, mas **nenhum chamador na UI**. Resposta `NotifyLeaveHanger` -> `OnLeaveHanger` (`LM_RoomPage` 29020, `LM_MatchRoomPage` 35555). Lacuna: o cliente não envia a saída do hangar.
- **Tela:** `LM_HangerPage` (XInterface 44869-45905), `LM_HangerItemMCL`, `LM_HangerInvenListPanel` (46259-46920), `LM_HangerGateInvenPanel` (46920-47540), `LM_HangerGateInfoPanel` (47540-47775).

### 3.2 Uso (equipar no gate) e remoção do gate

- **Equipar:** `ItemUsed(nItemIndex, nGateIndex)` (`/ItemUsed`, opcode 560). UI: `LM_HangerInvenListPanel.InternalOnDblClick` (46895). Resposta `NotifyItemUsed(result)` -> `LM_HangerPage.OnItemUsed` (45723) -> atualiza lista. `NotifyItemUsedGate` -> `OnItemUsedGate` (45868).
- **Remover do gate:** `ItemUnused(nItemIndex, nGateIndex)` (`/ItemUnused`, opcode 570). UI: `LM_HangerGateInvenPanel.SetGateInven` (47234), 13 chamadas. Resposta `NotifyItemUnused` -> `OnItemUnused` (45738).
- **Uso de sistema:** `NotifyItemUsedSystem(result)` -> `OnItemUsedSystem` (45755). Estado dos slots de sistema: `GetSystemItemState()` (`/GetSystemItemState`) sem método na DLL (lacuna). Resposta `NotifyGetSystemItemState(EVENT_SLOT slot[10])` -> `OnGetSystemItemState` (`LM_MainMenuBasePage` 31922 e `LM_CampPage` 36924). Chamadores: `LM_CampPage` e `LM_MainMenuBasePage` (37310, 65199).
- **Mudança de morat principal:** `ItemUsedByValue(nItemIndex, nGateIndex, nValue)` (`/ItemUsedByValue`, sem método na DLL). UI: `LM_ChangeMainMoratsPage.InternalOnClose` (64521). Resposta `NotifyItemUsedChangeMainMorats` -> `OnItemUsedChangeMainMorats` (45770).
- **Regra visível:** 8 gates por jogador (`LM_PLAYER_INFO.sGate[8]`, `GetMoratsInfoByGate` usa `MAX_PLAYER_MORATS`). 10 slots de sistema (`sEventSlot[10]`, `EVENT_SLOT`).

### 3.3 Destruir e renovar

- **Destruir:** `ItemDestroy(nItemID, nIndex)` (`/ItemDestroy`, opcode 555). UI: `LM_HangerPage.OnCloseMoratsDestroy` (45597, 45613, 45619) e `LM_ItemRenewPage.AllDestroy` (44137, 44149). Resposta `NotifyItemDestroy(result, nIndex, nUsedGate)` -> `OnItemDestroy` (45708). `NotifyMoratsDestroy` -> `OnMoratsDestroy` (45680). Não existe pedido separado de destruição de morat (inferido: `ItemDestroy` cobre morat).
- **Renovar prazo:** `ItemExtend(nItemID, nItemIndex, bPoint, nBuyOption)` (`/ItemExtend`, opcode 580). UI: `LM_HangerBuyItemPopPage`, `LM_HangerBuyMoratsPopPage` (47878), `LM_HangerRenewMoratsPopPage` (44735), `LM_SupplyBuyPopPage` (12204-12219). Resposta `NotifyItemExtend(result, nIndex, bItem)` -> `OnItemExtend`.
- **Fim de prazo:** `NotifyItemEndtime(nIndex, bItem, premium)` (CS, opcode 585) -> `OnItemEndtime` abre `LM_ItemRenewPage` (XInterface 8943-8950 e 29785, 36156, 44208, 65195).
- **Regra visível:** `item_life_time` / `item_limited_time` (`Item_Equip`) e `apply_flag`/`apply_value` do inventário (`LM_ITEM_INFO.ucApplyFlag`, `iApplyValue`) definem prazo ou uso. Sem log de prazo.

### 3.4 Item do jogador (estado)

- **Servidor:** CS (inferido: `NotifyGetItem`, opcode 102, `channel_server.md` §3.2, carrega o cache lido por `GetItemCount`/`GetItemInfo`). `LM_ITEM_INFO`: `siIdx`, `siItemIdx`, `strItemGuid`, `ucApplyFlag`, `iApplyValue`.
- **Persistido (proposta):** `inventory_items` (account_id, item_id, item_guid UNIQUE, apply_flag, apply_value, expires_at, timestamps). Substitui `tbl_item`. Itens apagados vão para o próprio registro (sem tabela de log).
- **Gates de morat:** `morat_gates` (account_id, gate_index 0..7, inventory_item_id, enabled) e `morat_gate_parts` (morat_gate_id, inventory_item_id, slot_name). Substitui `tbl_morats`.

## 4. Quickslot: removido do cliente

- **Evidência:** `LM_QUICK_SLOT` (struct) comentado em `LM_Engine` (linhas 647-655). `QuickLink` e `QuickMemo` (wrappers, linhas 2061-2081) comentados. `NType_QuickLink` e `NType_QuickMemo` comentados (linhas 214-215). `NotifyQuickLink` / `NotifyQuickMemo` comentados (2344-2345, 23315-23319). `OnQuickLink` comentado (17833).
- **Contagem:** 0 linhas não comentadas que mencionem quickslot, quicklink ou quickmemo em `XInterface`, `XGame` e `LM_Engine` (busca case-insensitive).
- **Substituto no cliente:** a equipação em gate (`/ItemUsed`, seção 3.2) e `sGate[8]`/`sEventSlot[10]`. (inferido)
- **Persistido:** nada. `tbl_quickslot` (`account_code`, `slot_idx`, `enable`, `memo`, `gate_idx`) é tabela legada sem uso no cliente. Não criar tabela.

## 5. Chat

### 5.1 Lobby e geral (CS)

- **Envio:** `LM_ChatPanel.SendChat` (XInterface 63374) -> `ServerPageOwner.NetSendMsg(0, strChat)` -> `ServerInterface.SendMsg(msg_type, msg)` -> `/SendMsg` (CS, opcode 240, `CS_SEND_MESSAGE_IN`).
- **Tipos de chat** (`LM_ServerInterfaceBridge.SendMsgEx`, 21518-21530): `chatType` 0 = geral (`SendMsg(msg_type, msg)`), 1 = equipe (`SendMsg(MT_TEAM, ...)`, só se `bTeamGame`), 2 = clã (`SendClanMessage`). Valores numéricos de `MT_TEAM` não estão nos fontes lidos (lacuna).
- **Recebimento:** `NotifySendMsg(int sender, byte msg_type, string msg)` (CS, opcode 241, XInterface 23353). Aplica `SlangFiltering(msg)` antes de exibir. Retorna sem exibir se a posição do remetente (`Player.position`) for diferente da minha (`MyInfo.position`); trata `POS_PLAY` à parte.
- **Página de chat:** `LM_ChatPanel` (62801), `LM_ChatBasePage` (63427-63994, com `OnSendMsg` 63803), `LM_TabChat` (7173), `LM_FontsChat` (48980). Abas: `SMT_GLOBAL`, `SMT_WHISP`, `SMT_CLAN` (62811-62814; `SMT_MESSENGER` comentado).
- **Persistido (proposta):** nada. Chat não é gravado (sem tabela de log).

### 5.2 Whisper (MS)

- **Envio:** `LM_ChatPanel.SendChat` (63340) -> `NetSendWhisper(Listener, strChat)` -> `ServerInterface.SendWhisper(nickname, msg)` (MS, método `SendWhisper`).
- **Resposta:** `NotifySendWhisper(sender, msg)` (XInterface 22410) -> `OnSendWhisper` (63865). `NotifySendWhisperError(result, receiver, msg)` (22461) -> `OnSendWhisperError` (63901).
- **Regra visível:** `LM_ChatPanel.SendChat` não envia se o destinatário estiver vazio (`goto Failed`) ou se for o próprio jogador (mensagem `261000401`, XInterface 63330-63342).
- **Persistido (proposta):** nada.

### 5.3 Clã (MS)

- **Envio:** `LM_ChatPanel.SendChat` (63363) -> `ServerPageOwner.ServerInterface.SendClanMessage(strChat)` (MS).
- **Resposta:** `NotifySendClanMessage(sender, msg)` (22530) -> `OnSendClanMessage` (63922).
- **Regra visível:** só se `clan_code > 0` no login (seção 0.1).
- **Persistido (proposta):** nada.

### 5.4 Chat de partida (dentro do jogo)

- **Caminho:** o chat em partida vai pelo mesmo `/SendMsg` (CS). A mensagem recebe o sufixo `"//GAMECHAT"` (`msg @= "//GAMECHAT"`, SendMsgEx 21508-21525). O Channel repassa ao jogo (inferido).
- **Mensagens de partida:** `NotifySendMsg` trata `POS_PLAY` (posição de jogo). Chat de equipe usa `MT_TEAM`.
- **Persistido (proposta):** nada.

### 5.5 Filtro de palavras e comandos de administrador

- **Filtro:** `LM_ServerInterfaceBridge.LoadSlangFiltering` (18459) lê `SELECT slang, filter FROM filtering WHERE onlynick = 0`. `SlangFiltering(out string)` (20388) substitui no texto. Nomes: `SELECT slang, onlyNick FROM filtering WHERE onlynick = 1 OR onlynick = 2`. Tabela `Filtering` (271 linhas) no banco.
- **Comandos GM** (`LM_ServerInterfaceBridge.SendMsg`, 21255-21290): só com `MyInfo.ucAccess >= 9`. Comandos: `/ALLNOTIFY`, `/NOTIFY` (-> `SendCommand`, 250), `/EXPEL` (-> `ExpelPlayer`, 700), `/SHOWFPS`, `getall`.
- **Persistido (proposta):** `filtered_words` (estático, espelho da tabela `filtering`: slang UNIQUE, replacement, only_nick).

## 6. Salas e partida (matchmaking)

### 6.1 Salas (CS)

- **Criar:** `CreateRoom(name, pw, scale, mode, map_num, max_player, team_count, limit_time, limit_score)` (`/CreateRoom`, 301). UI: `LM_CreateRoomPage.InternalOnClose` (60166, `NetCreateRoom`). Resposta: `NotifyCreateRoom` -> `OnCreateRoom`.
- **Entrar:** `InRoom(num, pw)` (`/InRoom`, 311). UI: `LM_RoomListPanel` (30307-30447), `LM_RoomMCL` (29824-30307) e `LM_RoomPasswordPage` (27216). Resposta `NotifyInRoom(room_guid, client_guid, slot_num)`.
- **Sair:** `OutRoom` (321). UI: `LM_RoomPage`, `LM_MatchRoomPage`. Resposta `NotifyOutRoom`.
- **Propriedades:** `ChangeRoomProperty` (411). UI: `LM_RoomSettingPage.InternalOnClose` (26322). Resposta `NotifyChangeRoomProperty`.
- **Slot/time:** `ChangeRoomSlot` (420) pela Bridge (`ChangeTeam`, 21787). `NetChangeRoomSlot` sem chamador. Resposta `NotifyChangeRoomSlot`.
- **Pronto:** `ReadyGame(selected_morats)` (401). UI: `LM_RoomPage` (28682), `LM_MatchRoomPage` (35325). Resposta `NotifyReadyGame` / `NotifyReadyGameError`.
- **Expulsar:** `RoomExpel` (451). UI: `LM_RoomPage.InternalOnClick` (28952). `ExpelPlayer` (700) só por `/EXPEL` (GM).
- **Convidar:** `RoomInvite` (461). UI: `LM_RoomInvitePage.InviteByPlayerName` (30614). Aceite: `RoomInviteAnswer` (471), UI em `LM_CampPage` (65220, 65259). Resposta `NotifyRoomInvite(room_guid, nickname)`, `NotifyResultRoomInvite`.
- **Detalhes:** `DetailRoomInfo` (540, `GetChannelRoomDetail`) em `LM_RoomInfoPage` (30766). `DetailPlayerInfo` (542, `GetChannelPlayerDetail`) em `LM_PlayerInfoPage` (32688) e `LM_MatchRoomPage` (34504). Respostas `NotifyDetailRoomInfo` / `NotifyDetailPlayerInfo`.
- **Saída de jogo:** `ExitPlay` (500). UI: `LM_InGameMenuPage.InternalOnClick` (44410, `NetExitPlayer`).
- **Lista de salas:** `RefreshRoomList(channel, guids)` (545), UI `LM_RoomListPanel`.
- **Persistido (proposta):** nada. Sala é estado em memória do Channel. Não persistir.

### 6.2 Partida: grupo, pedido e início (CS)

- **Entrar em grupo:** `RegisterGroup` (640). UI: `LM_MatchRoomPage.InternalOnClick` (35455). Resposta `NotifyRegisterGroup(bool)`.
- **Listar grupos:** `GetMatchingGroup` (642). UI: `LM_MatchingGroupListPage.InitComponent` (36381). Resposta `NotifyMatchingGroupList`.
- **Pedir partida:** `RequestMatch` (644, via `GetRequestMatch`). UI: `LM_MatchingGroupListPage.RequestMatch` (36488). Resposta `NotifyRequestMatch` / `NotifyReturnRequestMatch`.
- **Aceitar / recusar / cancelar:** `AcceptMatch` (645, `GetAcceptMatch`), `RejectMatch` (646, `GetRejectMatch`), `CancelMatch` (647). UI: `LM_RequestMatchPage.InternalOnClick` (31276, 31282, 31290).
- **Encerrar:** `EndMatch` (655). UI: `LM_MatchRoomPage.InternalOnClick` (35472).
- **Slot do grupo:** `ChangeGroupSlot` (657). UI: `LM_MatchRoomPage`.
- **Início:** `NotifyStartGame(address, port)` (CS, opcode 403, XInterface 23684) -> `OnNotify(NType_StartGame, port, , , address)`. O cliente conecta ao servidor UE2 indicado (inferido: troca de nível com `address:port`).
- **Partida em si:** o cliente de partida é `XGame` (`LM_DeathMatch`, `LM_TeamGame`, `LM_TeamOperation`, `LM_Tutorial`). Login da partida: `LoginPlayer` no `LM_Engine.dll` (seção de `re\NOTES.md`).
- **Persistido (proposta):** resultado de partida atualiza `player_stats` e `nest_stats` (seção 9). Nenhuma tabela de partida.

## 7. Clã

- **Servidor:** MS.
- **Pedidos:** `GetClanList` (`GetClanInfo`), `GetClanMember`, `SendClanMessage`, `RefreshClanList(guids)`. **Não há pedido de criar, entrar ou sair de clã no cliente** (busca por `CreateClan`, `JoinClan`, `LeaveClan` com 0 resultados em `LM_Engine` e `XInterface`). Gestão de clã está fora do cliente (inferido).
- **Respostas (MS: 172, 173, 175, 176, 178; XInterface):** `NotifyGetClanList` (22506), `NotifyGetClanMember` (22518), `NotifyDelClan` (22512), `NotifyDelClanMember` (22524), `NotifySendClanMessage` (22530), `NotifyClanInsertPlayer` (CS, opcode 902, bloco misto com `NotifyChargePoint` e `NotifyTutorialClear`; 23900 -> `OnClanInsertPlayer`).
- **Pós-login:** `GetClanList` e `GetClanMember` só se `clan_code > 0` (`NotifyInMessageServer`, 22343-22372).
- **UI:** chat de clã em `LM_ChatPanel.SendChat` (63363). Lista de clã em `LM_ClanRoomPlayerListPanel` (62224-62801, `AddFriendList` em 62377 e `AddBlackList` em 62403). Marca do clã: `LM_ServerInterfaceBridge.GetClanIcon` (XInterface 20134) com `PI.siClan` / `Player.nClanMark`. Nome do clã em `LM_PlayerInfoPage` (32813+). Partida de clã: struct `LM_MATCHING_GROUP_INFO` tem `clan_mark` e `clan_name` (uso na página não verificado).
- **Dados estáticos:** nenhum no `landmass.wdb`. Ícones são materiais do pacote.
- **Dados de estado:** `LM_CLAN_INFO` (id, name, master, mark). `LM_PLAYER_INFO.siClan` e `clan_mark`. `LM_PLAYER_DETAIL_INFO.nClanMark`, `strClanName`.
- **Persistido (proposta):** `clans` (name UNIQUE, master_account_id, mark_id, timestamps), `clan_members` (clan_id, account_id, grade, timestamps). Substitui `tbl_clan`, `tbl_clanmember`. Não criar `clan_logs` (`tbl_clanlog` é log).
- **Regra visível:** `member_grade` em `LM_PLAYER_INFO`. Chat de clã só para membros (`clan_code > 0`).

## 8. Amigos e lista de bloqueio

- **Servidor:** MS.
- **Pedidos:** `GetFriendList` (automático no login), `AddFriendList(nick)`, `GetDelFriendList(nick)` (remover), `AddBlackList(nick)`, `GetDelBlackList(nick)`, `RefreshFriendList(guids)`, `RefreshBlackList(guids)`. `QueryFriendLog(index)` (nativo, `LM_Engine`).
- **Respostas (MS: 183, 184, 188, 189):** `NotifyFriendList` (22574), `NotifyDelFriend` (22580), `NotifyBlackList` (22592), `NotifyDelBlack` (22598). `NotifyFriendLog` (22586) **sem servidor identificado**: `message_server.md` §8 diz "opcode desconhecido" (lacuna).
- **UI:** `LM_PlayerListPanel` (32097-32479):
  - `AddFriendList`: 32254 (`InternalContextOnSelect`).
  - `GetDelFriendList`: 32250.
  - `AddBlackList`: 32291 (`AddBlackListMsgboxOnClick`).
  - `GetDelBlackList`: 32261.
  - `RefreshFriendList`: 32163; `RefreshBlackList`: 32171.
  - `LM_RoomPlayerListPanel`: `AddFriendList` 26894, `AddBlackList` 26920.
- **Estado:** `GetFriendPlayerCount`, `GetFriendPlayerInfo(index)`, `GetBlackPlayerCount`, `GetBlackPlayerInfo(index)` (natives de `LM_ServerInterface`).
- **Persistido (proposta):** `friendships` (account_id, friend_account_id, last_seen_at, timestamps). `blocked_accounts` (account_id, blocked_account_id, timestamps). Substitui `tbl_friends` (`gubun` = tipo) e `tbl_friends_del`. `last_seen_at` cobre o "friend log" sem tabela de log (inferido: o log de amigo é o estado de conexão do amigo).
- **Regra visível:** `ucAccess` (nível de acesso) de cada jogador em `LM_PLAYER_INFO`. Lista de bloqueio por nick.

## 9. Ranking

- **Servidor:** MS (wrapper `GetRankingInfo`). **Sem pedido no cliente.**
- **Evidência de não uso:** `GetRankingInfo` tem 0 chamadas em `XInterface` (só comentário em `LM_ServerInterfaceBridge.NotifyInMessageServer`, linha ~22348: `//GetRankingInfo();`).
- **Resposta:** `NotifyRankingInfo(LM_PLAYER_INFO ranking[MAX_LANK_LIST])` (MS 171, XInterface 22466) preenche `RankPlayers` e chama `OwnerPage.OnNotify(NType_RankingInfo)` -> `OnRankingInfo()` (`LM_ServerInterfacePage` 17700, vazio). A implementação em `LM_ServerChannelPage` (24332) está comentada. A carga em `LM_RankMCLBPanel` (31545) e a chamada em `LM_ServerChannelPage` (24027, 24070) estão comentadas.
- **Conclusão:** a tela de ranking existe, mas não é alimentada. O recebimento de `NotifyRankingInfo` depende de o servidor enviar sem pedido (inferido: sem essa push, a tela fica vazia).
- **Dados estáticos:** nenhum.
- **Persistido (proposta):** nenhuma tabela de ranking. Ranking é consulta ordenada sobre `player_stats` (total_experience) e `nest_stats` (por nest). Substitui `tbl_ranking` (que guardava `total_rank` e `oddeye/shadow/leon` rank/exp).
- **Regra visível:** `LM_PLAYER_INFO.iTotalRank` existe, mas não é usado para exibir ranking.

## 10. Morats (unidades de combate)

**Divergência com o pedido:** no cliente, "morats" são **unidades de combate** (robôs, espécies `SPECIES_*`), não moeda. A moeda é LD e Cash (seção 11). Os itens são comprados com LD ou Cash, como qualquer item.

- **Identidade:** `101000001` = "AU-TP02" (grupo 1 MORATS, classe 1 ASSAULT). Classe das espécies: `CLASS_MORATS` (1 ASSAULT, 2 SNIPER, 3 DEFENDER, 4 ENGINEER, 5 SPECIAL) e `XGame.SPECIES_*` (`SpeciesType`).
- **Catálogo:** tabela `Morats` (ver 2.1). Os valores são lidos por `GetMoratsSaleItemInfo` (19320) e pelas classes `XGame.SPECIES_*.Default`.
- **Compra:** `ItemBuy` (550) pela `LM_SupplyMoratsBuyPopPage` (9258). Resposta `NotifyMoratsBuy` (CS, opcode 552) -> `LM_SupplyPage.OnMoratsBuy` (8918).
- **Equipar no gate:** `ItemUsed` (560) com o ID do morat (seção 3.2).
- **Morat principal:** `ItemUsedByValue` (sem método na DLL) em `LM_ChangeMainMoratsPage` (64521). Resposta `NotifyItemUsedChangeMainMorats`. Campo `LM_PLAYER_INFO.main_morats`.
- **Morat regular (nest):** `SetRegular(nest, morat)` (`/SetRegular`, CS, opcode 105), com `nest` limitado a 1-3 (Oddeye, Shadow, Leon) e `morat` (classe) limitado a 1-4 (LM_Engine `SetRegular`, linhas 1843-1851). O segundo argumento é `SelectedMorats` de `LM_JoinNestPage`, escolhido por botões que atribuem 1 a 4 (XInterface 43621-43663): é classe de morat (1 ASSAULT, 2 SNIPER, 3 DEFENDER, 4 ENGINEER), não gate. SPECIAL (5) não é selecionável. UI: `LM_JoinNestPage.OnCloseExit` (43754). Resposta `NotifySetRegular` (CS, opcode 104, Bridge 22695) -> `OnNotify(NType_NestJoin)`. `NotifyChangeNest(result)` (CS, opcode 569, Bridge 23931) -> `OnChangeNest` (`LM_JoinNestPage`, 43779).
- **Criação:** `NotifyMoratsCreated(result)` (CS, opcode 108, `channel_server.md` §3.2). Sem pedido no cliente (inferido: criação no cadastro de nest).
- **Morat selecionado na sala:** `ReadyGame(selected_morats)` (401). `LM_PLAYER_INFO.select_morats` e `select_morats_id`.
- **Dados de estado:** `LM_MORATS_INFO` (siIdx, siItemIdx, strItemGuid, ucApplyFlag, iApplyValue, siMainWeapon, siSubWeapon, siMeleeWeapon, siEtcWeapon00-02, siBooster, siGenerator, siHead, siBody, siArm, siLeg, siEtcItem00-03, siSkinID[3]).
- **Persistido (proposta):** `morat_gates` e `morat_gate_parts` (seção 3.4). Escolha regular em `accounts.regular_nest_id` e `accounts.regular_morat_class` (1-4). Substitui `tbl_morats` e `tbl_morats_del`.
- **Regra visível:** requisitos de nível, nest, clã etc. em `Morats.required_*`. Espécies `A` e `B` (ex.: AssaultA, AssaultB) são variantes.

## 11. Moeda: LD, Cash, premium e bônus de PC-room

- **Moedas:** `LM_ServerInterface.PointUnit` = **"LD"** e `CashUnit` = **"Cash"** (tabela `localize`, seção `LM_ServerInterface`). Saldos: `LM_PLAYER_INFO.iPoint` (LD) e `iCash` (Cash).
- **Compra:** `bPoint = true` gasta LD (`item_buy_point`); `bPoint = false` gasta Cash (`item_buy_cash`). Ver 2.2.
- **Carga de Cash/LD:** servidor empurra `NotifyChargeCash` (CS, opcode 900, 23877 -> `OnChargeCash`, `LM_MainMenuBasePage` 36708), `NotifyChargePoint` (CS, opcode 902, bloco misto, 23883 -> `OnChargePoint`, 36714) e `NotifyChargePremium` (CS, opcode 901, 23889 -> `OnChargePremium`, `LM_ItemRenewPage` 44286). O corpo base de `LM_ServerInterface.NotifyChargeCash` só faz `log`. Não há pedido de carga no cliente (inferido: carga é feita fora do cliente).
- **Premium:** `LM_PLAYER_INFO.premium_end` (data de fim) e `member_grade`. Tela de renovação: `LM_ItemRenewPage`.
- **PC-room:** `LM_PLAYER_INFO.pc_room` (bool). Bônus `PCRoomBonusExp` e `PCRoomBonusPoint` (GameRewardConstant, valor 1 e 1) multiplicam `pri.Experience` e `pri.Money` no fim da partida (`XGame`, linhas 6625-6626 e 16296-16297). A consulta `SELECT key, value FROM PCRoomBonus` está **comentada** (XGame 15692), então a tabela `PCRoomBonus` não é consultada e não faz falta no wdb.
- **Persistido (proposta):** `accounts.cash_balance`, `accounts.point_balance` (LD), `accounts.premium_until`, `accounts.pc_room` (bool). Sem tabela de transação (seria log).

## 12. Penalidades

O cliente não tem tela de penalidade nem lista de punições. A lista está só no servidor (`tbl_penalty_list`: `penalty_kind`, `penalty_item`, `penalty_start`, `penalty_end`, `penalty_state`, `account_code`). No cliente, a penalidade aparece como:

- **Expulsão de canal (admin):** `EXPEL_ADMIN` (CS, opcode 123, `LM_ServerInterfaceBridge.NotifyOutChannel`, 23524-23528). Mensagem `121000402` = "Você foi desconectado de canal %s." Leva à `LM_ServerChannelPage`.
- **Bloqueio de acesso ao canal (regra, não punição):** `EXPEL_EXPBLOCK` (`NotifyOutChannel`, XInterface 23529) marca `bExpeledChannel = true`. Ao abrir `LM_RoomPage.InternalOnOpen` (27418) ou `LM_MatchRoomPage.InternalOnOpen` (34539), o cliente mostra o texto fixo em inglês "u r not a freshman. reselect other server plz." e devolve à escolha de canal. Ligado a `LM_SERVER_INFO.access_level` e `access_exp` (LM_Engine 376-378), campos que não são lidos na UI (inferido: regra de acesso por experiência, avaliada pelo Channel).
- **Retorno à lista:** `EXPEL_REQUEST` (23531) só volta para `LM_ServerChannelPage`.
- **Expulsão de sala:** `RoomExpel` (451) pela sala (`LM_RoomPage.InternalOnClick`, 28952). `ExpelPlayer` (700) pelo comando GM `/EXPEL` (`LM_ServerInterfaceBridge.SendMsg`, 21281 e 21438), só com `ucAccess >= 9`.
- **Taxa de abandono (secede):** `LM_PLAYER_INFO.iTotalSecedecount` existe, mas o percentual exibido é calculado no cliente em `LM_PlayerInfoPage.OnDetailPlayerInfo` (32813): `(nTotalGamecount - nTotalWin - nTotalLose) * 100 / nTotalGamecount`. Partidas sem vitória nem derrota contam como abandono (inferido).
- **Admin (não é penalidade):** `RequestForceUserQuit` (72) força a saída de usuário (DLL). Sem chamador na UI.
- **Valores de `EXPEL_*`:** os nomes aparecem em XInterface, mas os valores numéricos não estão nos `.u` lidos (são enum nativo). Lacuna.
- **Persistido (proposta):** `penalties` (account_id FK, kind, penalty_item, starts_at, ends_at, state, timestamps), para sanção temporal do legado `tbl_penalty_list`. Não há `kind` identificado no cliente. Expulsão (`EXPEL_ADMIN`, `/EXPEL`) é ação e não persiste. Bloqueio por experiência é regra de acesso e não persiste.

## 13. Lacunas e divergências

- **Quest:** inexistente no cliente (seção 1).
- **Quickslot:** removido (seção 4).
- **Ranking:** a tela existe, sem pedido (seção 9).
- **`GiftItemUsed`, `GiftMoratsUsed`, `LeaveHanger`, `GetSystemItemState`, `RefreshMatchRoomList`:** sem chamador na UI ou sem método na DLL. Ver seção 0.2.
- **`ItemUsedByValue`:** sem método na DLL (inferido: `ItemUsed`).
- **`/OutChannelServer` e `/NetDisConnect`:** sem método nomeado na DLL.
- **Requisito de compra:** não localizei o bloqueio no cliente. O servidor deve validar.
- **`MT_TEAM`, `EXPEL_*`:** valores numéricos não localizados nos `.u`.
- **Opcodes do Message acima de 150:** não documentados em `re\message_server.md`. Sem número para `/UpdateNickname`, `/SendWhisper`, `/GetRankingInfo`, `/GetClanList`, `/GetFriendList` etc.
- **`msg_error` (208 linhas):** texto em português, com codificação quebrada na leitura (acentuação corrompida). Os códigos estão corretos.
- **`NotifyFriendLog`:** sem opcode em `message_server.md` (§8) nem na tabela de rótulos do Channel: servidor não identificado.
- **`XEffects.u`:** sem fonte embutida.
- **Morats:** o pedido diz "morats (moeda)", mas no código são unidades. A moeda é `LD`/`Cash` (seção 10).

## 14. Estrutura de tabelas proposta (Laravel, sem tabelas de log)

- `accounts`: id, login UNIQUE, nickname UNIQUE, clan_id FK nullable, cash_balance, point_balance, tutorial_flags, regular_nest_id FK nullable, regular_morat_class tinyint nullable (1-4), main_morat_gate_id FK nullable, premium_until nullable, pc_room bool, access_level, timestamps.
- `items`: id, code UNIQUE (ex.: 307010002), group, class_code, type_code, name, timestamps.
- `item_prices`: id, item_id FK, currency (cash|point), buy_option_index (0-3, valor que chega no pacote), duration_days (1, 7, 14, 30; nulo quando não há duração própria), price, timestamps. Os casos 8 e 9 chegam como `nBuyOption=0` e não têm índice próprio (inferido).
- `item_requirements`: id, item_id FK, required_level, required_nest, required_nest_point, required_clan, required_clan_rank, required_rank, required_class, required_strength, required_agility, required_precision, required_power, timestamps.
- `inventory_items`: id, account_id FK, item_id FK, item_guid UNIQUE, apply_flag, apply_value, expires_at nullable, timestamps.
- `morat_gates`: id, account_id FK, gate_index (0-7), inventory_item_id FK nullable, enabled, timestamps.
- `morat_gate_parts`: id, morat_gate_id FK, inventory_item_id FK, slot_name, timestamps.
- `system_slots`: id, account_id FK, slot_index (0-9), inventory_item_id FK nullable, enabled, timestamps.
- `gifts`: id, sender_account_id FK, receiver_account_id FK, item_id FK, buy_option, claimed_at nullable, timestamps.
- `friendships`: id, account_id FK, friend_account_id FK, last_seen_at nullable, timestamps.
- `blocked_accounts`: id, account_id FK, blocked_account_id FK, timestamps.
- `clans`: id, name UNIQUE, master_account_id FK, mark_id, timestamps.
- `clan_members`: id, clan_id FK, account_id FK, grade, timestamps.
- `player_stats`: id, account_id FK UNIQUE, total_experience, total_games, total_wins, total_losses, total_kills, total_deaths, headshots, timestamps.
- `nest_stats`: id, account_id FK, nest_id FK, experience, kills, deaths, wins, losses, games, contribute, timestamps.
- `penalties`: id, account_id FK, issued_by_account_id FK nullable, kind, starts_at, ends_at, timestamps.
- `nests`: id, name (estático: 1 Oddeye, 2 Shadow, 3 Leon), timestamps.
- `maps`, `levels`, `game_reward_constants`, `filtered_words`: estáticos, espelho do cliente, timestamps.

Sem tabela para: chat, sala, grupo de partida, sorteio de gacha, transações de moeda, logs de clã ou de login (`tbl_clanlog`, `tbl_loginlog`, `tbl_item_del`, `tbl_morats_del` não são replicados).

## 15. Tabela final: funcionalidade -> servidor -> pedidos -> tabelas

| Funcionalidade | Servidor | Pedidos (/Comando -> método, opcode) | Tabelas (estáticas no cliente / persistidas proposta) |
|---|---|---|---|
| Tutorial (3 passos) | CS | `/TutorialClear` -> `ClearTutorial` (600) | cliente: nada / `accounts.tutorial_flags` |
| Missões de partida (OP/BR) | UE2 | nenhum (recompensa na partida) | cliente: `GameRewardConstant` / `player_stats`, `accounts` |
| Quests | - | inexistente | - |
| Loja: compra | CS | `/ItemBuy` -> `ItemBuy` (550) | cliente: `item`, `Item_Equip`, `Morats`, `supply` / `item_prices`, `item_requirements`, `inventory_items` |
| Loja: presente | CS | `/ItemGift` (615), `/GetGiftItem` (610) | cliente: `item`, `Item_Equip` / `gifts` |
| Loja: resgate de presente | CS | `/GiftItemUsed` (612): sem chamador | - / `gifts.claimed_at` |
| Gacha / item surpresa | CS (push) | nenhum no cliente | cliente: `item` (308010006) / `inventory_items`, `accounts` |
| Inventário e hangar | CS | `/EnterHanger` (586); `/LeaveHanger` (588) sem chamador | - / `inventory_items` |
| Equipar no gate | CS | `/ItemUsed` (560), `/ItemUnused` (570) | - / `morat_gates`, `morat_gate_parts` |
| Destruir / renovar item | CS | `/ItemDestroy` (555), `/ItemExtend` (580) | `Item_Equip.item_life_time` / `inventory_items.expires_at` |
| Sistema (buffs, slots) | CS | `/ItemUsed` (560); `/GetSystemItemState` (sem método) | - / `system_slots` |
| Quickslot | - | removido (comentado) | - / nada (`tbl_quickslot` legada) |
| Chat lobby/geral | CS | `/SendMsg` (240) | - / nada (sem log) |
| Chat partida | CS | `/SendMsg` (240) com `//GAMECHAT` | - / nada |
| Chat equipe | CS | `/SendMsg` (240), `MT_TEAM` | - / nada |
| Whisper | MS | `/SendWhisper` (MS) | - / nada |
| Chat de clã | MS | `/SendClanMessage` (MS) | - / `clan_members` |
| Filtro de palavras | - | leitura de `filtering` | `Filtering` / `filtered_words` |
| Comandos GM | CS | `/SendCommand` (250), `/ExpelPlayer` (700) | - / `penalties` (quando aplicado) |
| Salas: criar/entrar/sair | CS | `/CreateRoom` (301), `/InRoom` (311), `/OutRoom` (321) | - / nada (estado em memória) |
| Salas: propriedades/slot/pronto | CS | `/ChangeRoomProperty` (411), `/ChangeRoomSlot` (420), `/ReadyGame` (401) | `maps` / nada |
| Salas: convite/expulsão | CS | `/RoomInvite` (461), `/RoomInviteAnswer` (471), `/RoomExpel` (451) | - / nada |
| Partida: grupo e pedido | CS | `/RegisterGroup` (640), `/GetMatchingGroupList` (642), `/GetRequestMatch` (644), `/GetAcceptMatch` (645), `/GetRejectMatch` (646), `/CancelMatch` (647), `/EndMatch` (655) | - / nada |
| Partida: início | CS | `NotifyStartGame(address, port)` | - / `player_stats`, `nest_stats` |
| Clã | MS | `/GetClanList`, `/GetClanMember`, `/RefreshClanList` | - / `clans`, `clan_members` |
| Amigos | MS | `/GetFriendList`, `/AddFriendList`, `/GetDelFriendList`, `/RefreshFriendList` | - / `friendships` |
| Lista de bloqueio | MS | `/AddBlackList`, `/GetDelBlackList`, `/RefreshBlackList` | - / `blocked_accounts` |
| Ranking | MS | `/GetRankingInfo` sem chamador (push possível) | - / consulta sobre `player_stats` |
| Morats (unidades): compra | CS | `/ItemBuy` (550) | `Morats`, `item` / `item_prices` |
| Morats: equipar e principal | CS | `/ItemUsed` (560), `/ItemUsedByValue` (sem método) | - / `morat_gates`, `morat_gate_parts` |
| Morats: nest regular | CS | `/SetRegular` (105) | - / `accounts.regular_*` |
| Moeda: LD e Cash | CS (push) | `NotifyChargeCash/Point/Premium` (900, 902, 901) | `localize` (`PointUnit`=LD, `CashUnit`=Cash) / `accounts.cash_balance`, `point_balance`, `premium_until` |
| PC-room | UE2 | nenhum (bônus no fim da partida) | `GameRewardConstant` (PCRoomBonusExp/Point) / `accounts.pc_room` |
| Acesso ao canal (EXPEL_EXPBLOCK) | CS (push, opcode 123) | `NotifyOutChannel` | regra de acesso (`LM_SERVER_INFO.access_*`) / nada |
| Expulsão de canal pelo admin (EXPEL_ADMIN) | CS (push, opcode 123) | `NotifyOutChannel` | - / nada (ação) |
| Penalidade: taxa de abandono | MS/CS (dados) | dados de `GetMyPlayerInfo` | - / `player_stats` (contadores) |
