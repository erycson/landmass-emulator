# Channel Server (TCP 7314, `net_code` 14)

Implementação: `protocol/channel.py` (codec), `domain/lobby.py` (presença), `domain/rooms.py` (salas em memória), `handlers/channel/` (comportamento; salas em `rooms.py`), `ports/options.py` (opções, gravadas pelo 544), `net/server.py` (transporte). Evidências e layouts completos: [`../../re/channel_server.md`](../../re/channel_server.md) e [`../../re/rooms.md`](../../re/rooms.md).

Este documento cobre o que o emulador implementa: marco 2 (entrada, lobby, chat), F1 (opções, 544), marco 3 (salas: criar, entrar, sair, slots, pronto, início, configuração, convite e expulsão pelo 451) e F2 e F3 (tutorial, saldos e exp). Os demais opcodes da tabela completa seguem como não tratados: logados com hexdump e ignorados, sem derrubar a conexão.

## Grupos de opcodes

| Faixa | Assunto | Estado |
|-------|---------|--------|
| 1xx | Entrada no canal, lobby, lista de jogadores e de salas | marco 2 (100, 120, 122); lista de salas no 141 pelo marco 3 |
| 2 | Heartbeat | marco 2 |
| 2xx | Chat | marco 2 (240/241); escopo da sala pelo marco 3 |
| 3xx | Salas: criar, entrar, sair, mudança de dono e remoção | marco 3 (301 a 342) |
| 4xx | Sala: pronto, início, slot, configuração (411/412), expulsão (451) e convite (461 a 471) | marco 3 (401 a 471) |
| 5xx | Itens, loja, hangar, presentes | marco 5 |
| 7xx | Expulsão pelo console (700/701) | decodificado; não executado (item 20) |
| `GS_*` | Game Server Host ↔ Channel (autenticado por `ch_pw`) | não usado pelo DM (`re/game_server_host.md` §11) |

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
| `301` CreateRoom, 74 bytes | `302` ao lobby (registro da sala), `312` ao lobby (criador no slot 0), `314` e `317` ao criador | Cria a sala em memória; o criador é o dono e fica sem pronto (D77). Nome curto: envelope `54` com `302` e código 211000202. Outro erro: código 211000201. |
| `311` InRoom, 20 bytes | `312` ao canal, menos quem já está na sala; `549` a quem já está na sala; `314` e `317` ao entrante | Entra no primeiro slot livre. Recusa: `312` com código negativo só ao entrante, com 1001 (sala não existe), 1202 (cheia), 1701 (senha) ou 200 (partida já iniciada). Estar em sala já: sem resposta. |
| `321` OutRoom, vazio | `322` ao lobby; `332` se trocou o dono; `342` se a sala esvaziou | Sai da sala. |
| `401` ReadyGame, `u8 morats`, de jogador não dono | `402` aos membros da sala | Alterna o estado de pronto. |
| `401` ReadyGame, do dono | `412` ao lobby; depois `402` do dono pronto e `403` aos membros da sala (endereço e porta da partida) | Inicia a partida se houver outro jogador e todos os outros estiverem prontos. Se não, envelope `54` com `404` e código 241002702 (condições não atendidas). Se o servidor da partida não abre a porta, a sala volta à espera (`412` ao lobby, `402` aos não-donos) e o dono recebe envelope `54` com `404` e código 241000201. |
| `420` ChangeRoomSlot (mudar grupo), `u8 grupo` | `421` aos membros da sala, com o slot escolhido | Vai ao primeiro slot livre do grupo (D66). Sem vaga ou grupo inválido: sem resposta. |
| `586` InHangar, vazio | `587` só a quem pediu, com a própria chave | Abre o hangar no cliente. Quem não está em sala: sem resposta (D78). |
| `464` GetChannelPlayerInfo, vazio | `151` a quem pediu | Lista de jogadores do lobby. Quem não está no lobby ou está numa sala: sem resposta (D67). |
| `542` PlayerDetail, `char nick[17]` | `543` a quem pediu | Ficha com nick, posição, exp, nest e clã do banco; estatísticas saem zero até haver resultado (D107). Nick fora do canal: envelope 54 com 543. |
| `411` ChangeRoomProperty, 10 bytes, do dono | `412` ao lobby | Muda só os campos marcados em `flags`, com os limites da criação. Sala jogando, dono com pronto, quem não é dono ou configuração inválida: sem resposta (D77). |
| `451` RoomExpel, 18 bytes, do dono | `322` ao lobby | Expulsa pelo nick. Sem resposta a quem pediu; quem não é dono é ignorado. Sem caminho de UI confirmado (item 20). |
| `461` RoomInvite, nick de 17 bytes, do dono | `462` ao dono (`i32`); `463` ao convidado | Convite pendente até o 471. Resultado: 0 enviado; -2460 nick fora do canal; -2411 já em sala; -2406 sala cheia; -2412 partida iniciada. Quem não é dono: envelope `54` com 462 e -4061 (o cliente não mostra nada). |
| `471` RoomInviteAnswer, `i32 room_id`, `u8 accept` | aceite: `549` a quem está na sala, `312` ao canal, `314` e `317` ao entrante | Aceite entra sem senha, e só com convite pendente para a sala. Recusa ou sem convite: sem resposta. |
| `700` ExpelPlayer, `u8 kind` e nick | nenhuma | Console `/EXPEL`: decodificado, não executado (item 20). |
| `544` SaveOption, 37 bytes | nenhuma | Grava as 37 opções da conta logada em `account_options`. Sem login: ignorado. Payload curto: logado e ignorado. |
| (queda da conexão) | `123` aos demais | Saída implícita; antes, sai da sala como em `321`. |
| servidor, a cada 10 s | `2` heartbeat | O cliente responde com `2`; o servidor ignora essa resposta. |

Opcodes sem handler (inclusive 64, 66 e 67): logados com hexdump e ignorados. Pedido com payload inválido: logado sem hexdump e ignorado.

## Identificação do cliente

O cliente não envia nickname nem token ao entrar no canal. Envia no `100` a chave de sessão que recebeu no `111` do Message (`char[33]` @0x25; [message-server.md](message-server.md)). O canal resolve a chave com `SessionKeyRegistry` (`ports/session_keys.py`, implementado em `domain/session_keys.py`) e usa `account.id` como `client_guid` de toda a sessão. O canal não acessa o banco. Regras da chave em [authentication.md](authentication.md).

Evidências: o corpo do `100` tem 33 bytes (teste com o cliente real; `u8 @32` é o NUL do `char[33]`). O `ChannelServer.exe` original loga `in->guid=%s` logo após `InChannelServer(`. Inferido: o `num` de `InChannelServer(int num)` do UnrealScript não viaja no pacote.

## Opcodes

| Opcode | Direção | Nome (`CsOp`) | Corpo | Estado |
|-------:|---------|---------------|-------|--------|
| 2 | C↔S | `HEARTBEAT` | vazio | implementado |
| 54 | S→C | `ERROR` (envelope) | 8 bytes: opcode real e código | implementado |
| 100 | C→S | `IN_CHANNEL_SERVER` | `char session_key[33]` | implementado |
| 101 | S→C | `IN_CHANNEL_SERVER_OUT` | 176 bytes | implementado (progressão de `@0x28` a `@0x4C`, F2 e F3; nest em `@0x20` e gates em `@0x5A`, com `bEnable` em `@0x5C`, F5, habilitados por R-GATE-01 (F10); ver Layouts) |
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
| 591 | S→C | `GACHA_PRIZE_OUT` | `u16 key` @0, `i32` quantidade @4, `i32 result` @8; registros de 0x110 a partir de @0xC (`i32` item_id, `i32` size, `i32` buy_option, texto UTF-8 NUL) | implementado (F11): resposta ao 560 com `308010006`; até 2 prêmios |
| 610 | C→S | `GET_GIFT_ITEM_IN` | `i32 page` @0 (0 a n) | implementado (F10): resgata os pendentes (D100, 102 de cada) e responde 611 |
| 611 | S→C | `GET_GIFT_ITEM_OUT` | `i32 page` @0, `i32 count` @4; registros de 0x48 a partir de @8 (`u16` chave @0, `i32` catálogo @0x14, `item_guid` @0x18, `u8` prazo @0x40) | implementado (F10): página de 12; vazio manda um registro zerado |
| 612 | C→S | `GIFT_ITEM_USED_IN` | `i32 key` @0 | implementado (F10): resgata o pendente; sem chamador de UI (D100 resgata pelo 610) |
| 613 | S→C | `GIFT_ITEM_USED_OUT` | registro de 102 em @0..0x33 (zerado com recusa), `i32 result` @0x34, `i32 key` @0x38 | implementado (F10): medido no dispatcher 0x265 (L1526–1561) |
| 615 | C→S | `ITEM_GIFT_IN` | 24 bytes: `i32 catalog_id` @0, `u8 bPoint` @4 (1 LD, 0 Cash), `u8 option` @5, `char[18] nick` @6 | implementado (F10): responde 616 |
| 616 | S→C | `ITEM_GIFT_OUT` | 12 bytes: `i32 result` @0, `i32 cash` @4, `i32 point` @8 | implementado (F10): recusa com código de R-GIFT-01 |
| 617 | S→C | `GET_GIFT_OUT` | corpo vazio | implementado (F10): aviso ao destinatário online |
| 900 | S→C (push) | `CHARGE_CASH_OUT` | `i32` Cash | implementado (F3): enviado depois do 111 no login |
| 902 | S→C (push) | `CHARGE_POINT_OUT` | `i32` LD | implementado (F3): enviado depois do 111 no login; bloco misto no dispatcher (shortcut) |
| 102 | S→C (push) | `GET_ITEM_OUT` | 56 bytes | implementado (F4): um por item, no login, depois de 900 e 902 |
| 103 | S→C (push) | `GET_MORATS_OUT` | 96 bytes | implementado (F5): um por morat com gate, no login. Morat sem gate não sai |
| 104 | S→C | `SET_REGULAR_OUT` | vazio | implementado (F5): resposta do 105 |
| 105 | C→S | `SET_REGULAR_IN` | `u8 nest` @0, `u8 classe` @1 | implementado (F5): faixa validada (nest 1 a 3, classe 1 a 4); grava `accounts.regular_nest_id` e `regular_morat_class` |
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
| 403 | S→C | `START_GAME_OUT` | 18 bytes | implementado (shortcut: sai só depois de a porta da partida abrir, D47) |
| 404 | S→C | `READY_GAME_ERROR` (dentro do envelope 54) | sem corpo próprio | implementado |
| 411 | C→S | `CHANGE_ROOM_PROPERTY` | 10 bytes | implementado (shortcut: só campos com bit ligado) |
| 412 | S→C | `CHANGE_ROOM_PROPERTY_OUT` | 16 bytes | implementado (shortcut: máscara e campos) |
| 420 | C→S | `CHANGE_ROOM_SLOT` | `u8 grupo` | implementado (mudar grupo; D66) |
| 421 | S→C | `CHANGE_ROOM_SLOT_OUT` | 8 bytes | implementado |
| 451 | C→S | `ROOM_EXPEL` | 18 bytes | implementado (shortcut: nick inferido; sem resposta) |
| 461 | C→S | `ROOM_INVITE` | nick de 17 bytes | implementado (shortcut: nick inferido) |
| 462 | S→C | `ROOM_INVITE_OUT` | `i32 result` | implementado |
| 463 | S→C | `ROOM_INVITE_NOTIFY` | 21 bytes | implementado (shortcut: nick de @4 inferido) |
| 471 | C→S | `ROOM_INVITE_ANSWER` | `i32 room_id`, `u8 accept` | implementado |
| 500 | C→S | `EXIT_PLAY` | sem corpo | implementado (shortcut: fim da partida quando todos saem, D48; o cliente real não confirmou). O 311 de quem volta à sala também encerra a partida para o último em jogo (D150) |
| 501 | S→C | `EXIT_PLAY_OUT` | `i32 result` | implementado (shortcut: `result` 0 não confirmado no cliente) |
| 542 | C→S | `PLAYER_DETAIL_IN` | `char nick[17]` | implementado (D107): responde 543 |
| 543 | S→C | `PLAYER_DETAIL_OUT` | 77 bytes | implementado (D107): valores do banco; shortcut: tamanho do nick e do clã inferido |
| 549 | S→C | `ROOM_ENTRY_OUT` | entrada de jogador, 48 bytes | implementado (shortcut: divisão com 312) |
| 586 | C→S | `ENTER_HANGAR` | vazio | implementado (D78): só quem está em sala |
| 587 | S→C | `ENTER_HANGAR_OUT` | `i32 client_guid` @0 | implementado (D78): só ao pedinte |
| 588 | C→S | `LEAVE_HANGAR` | vazio | implementado (D151): só quem está em sala |
| 589 | S→C | `LEAVE_HANGAR_OUT` | `i32 client_guid` @0, `u8` 0x23 @4 (8 bytes) | implementado (D151): só ao pedinte |
| 550 | C→S | `ITEM_BUY_IN` | 12 bytes: `i32 id` @0, `u8 bPoint` @4 (1 LD, 0 Cash), `u8 nBuyOption` @5 (0 a 3) | implementado (F8): debita e cria a unidade numa transação; preço e venda vêm de `shop_items` (D191); recusa com result ≠ 0 |
| 551 | S→C | `ITEM_BUY_OUT` | 68 bytes: registro de 102 em @0..0x33, `i32 cash` @0x38, `i32 point` @0x3c, `i32 result` @0x40 | implementado (F8): sucesso manda 551, 102, 900 e 902; recusa vai sem registro e com saldos zero |
| 552 | S→C | `MORATS_BUY_OUT` | 104 bytes: registro de 103 em @0..0x5b, `i32 cash` @0x5c, `i32 point` @0x60, `i32 result` @0x64 | implementado (F8): sucesso manda 552, 103, 900 e 902 |
| 554 | S→C | `ITEM_USED_SYSTEM_OUT` | 60 bytes: registro de 102 em @0..0x33, `u16 slot` @0x34 (0 a 9), `i32 result` @0x38 | implementado (F6): item de sistema vai ao `sEventSlot` |
| 555 | C→S | `ITEM_DESTROY_IN` | 8 bytes (6 usados): `i32 id` @0, `u16 index` @4 | implementado (F7) |
| 556 | S→C | `ITEM_DESTROY_OUT` | 12 bytes: `u16 index` @0, `u16 gate` @2, `u8 mounted` @4, `i32 result` @8 | implementado (F7); recusa com result ≠ 0 (ex.: último morat) |
| 557 | S→C | `MORATS_DESTROY_OUT` | 8 bytes: `u16 gate` @0, `i32 result` @4 | implementado (F7) |
| 559 | S→C | `ITEM_DESTROY_SYSTEM_OUT` | 12 bytes: `u16 index` @0, `u16 slot` @2, `u8` 1 @4, `i32 result` @8 | implementado (F7) |
| 560 | C→S | `ITEM_USED_IN` | 8 bytes: `u16 index` @0, `u16 gate` @2, `i32 value` @4 | implementado (F6, F15); `value` ≠ 0 só em Alistar e Troca de Função (D133, D134); outros recusam com 561 |
| 561 | S→C | `ITEM_USED_REFUSED_OUT` | 12 bytes: `i32 result` @8 | implementado (F6): recusa, sem registro |
| 562 | S→C | `ITEM_USED_PIECE_OUT` | 12 bytes: `u16 gate` @0, `u16 index` @2, `u16 slot` @6 (0 a 15), `i32 result` @8 | implementado (F6) |
| 565 | S→C | `SKIN_MOUNTED_OUT` | 12 bytes: `u16 gate` @0, `u16 index` @2 (índice da pintura, vai a `siSkinID[k]`), `u16 k` @4 (0 em F15), `i32 result` @8 | implementado (F15, D136) |
| 568 | S→C | `ITEM_CONSUMED_OUT` | 8 bytes: `u16 index` @0 (o consumido), `i32 result` @4 | implementado (F15, D131 e D132): o cliente tira o item da lista |
| 569 | S→C | `CHANGE_NEST_OUT` | 8 bytes: `u16 index` @0, `u8 nest` @2, `i32 result` @4 | implementado (F15, D133): o cliente troca o nest e tira o item |
| 570 | C→S | `ITEM_UNUSED_IN` | 4 bytes: `u16 index` @0, `u16 gate` @2 | implementado (F6); item de sistema recusa com -4; pintura responde 573 |
| 572 | S→C | `ITEM_UNUSED_PIECE_OUT` | 12 bytes: `u16 gate` @0, `u16 slot` @4, `i32 result` @8 | implementado (F6) |
| 573 | S→C | `SKIN_UNUSED_OUT` | 12 bytes: `u16 gate` @0, `u16 k` @4, `i32 result` @8 | implementado (F15, D136) |
| 580 | C→S | `ITEM_EXTEND_IN` | 8 bytes: `i32 id` @0, `u16 index` @4, `u8 point` @6 (1 = LD), `u8 option` @7 | implementado (F7); morat recusa com -4 |
| 582 | S→C | `ITEM_EXTEND_OUT` | 20 bytes: `u16 index` @0, `i32 apply_value` @4 (fim em segundos Unix), `i32 cash` @8, `i32 point` @0xc, `i32 result` @0x10 | implementado (F7) |
| 585 | S→C | `ITEM_ENDTIME_OUT` | 4 bytes: `u8 0` @0, `u8 bItem` @1 (1), `u16 index` @2 | implementado (F7): no login, para item vencido |
| 590 | S→C | `CHANGE_MORAT_CLASS_OUT` | 8 bytes: `u16 index` @0, `u8 classe` @2, `i32 result` @4 | implementado (F15, D134): sem guarda de resultado no cliente, a recusa vai por 561 |
| 700 | C→S | `EXPEL_PLAYER` | `u8 kind`, nick de 17 bytes | só codec: não executado (console) |
| 701 | S→C | `EXPEL_PLAYER_OUT` | `i32` 0 | só codec: nenhum handler envia |
| 464 | C→S | `GET_CHANNEL_PLAYER_INFO` | vazio | implementado: responde 151 a quem está no lobby e fora de sala (D67) |
| 64, 66, 67 | C→S | pedidos de lista | — | não tratados |

## Salas

Estado em `domain/rooms.py`, só em memória (D12, D24). `handlers/channel/rooms.py` monta as respostas. Regras:

- **Criar.** O criador entra no slot 0, sem pronto, e é o dono (D77). Nome de 3 a 50 bytes; senha de até 12 bytes (shortcut). Valores numéricos fora da faixa são limitados e logados, não recusados: `scale`, `game_mode`, `team_count` e `limit_time` em 0..255; `map_num` e `limit_score` em 0..32767; `max_player` em 1..70.
- **Entrar.** A sala precisa existir, não ter começado, ter slot livre e, se tiver senha, a senha certa. Entra no primeiro slot livre. Quem entra não sai do lobby: continua recebendo a lista e o chat do canal.
- **Pronto.** Jogador que não é dono alterna o estado com `401`. O dono fica sem pronto na espera (D77): o `401` dele inicia a partida, e ele fica pronto só ao iniciar.
- **Iniciar.** Só o dono. Exige ao menos um outro membro e todos os outros prontos. A sala passa a jogando (estado 1, D65) e não aceita novas entradas. O dono fica pronto e o 402 dele sai antes do 403 (D77). O `403` leva `LANDMASS_GAME_HOST` com a porta fixa `LANDMASS_GAME_PORT`, ou com a porta da partida lançada pelo emulador (`LANDMASS_MATCH_SERVER_DIR`). Ver [05-configuration](../architecture/05-configuration.md) e [game-server](../operations/game-server.md).
- **Sair.** Se o dono sai e ainda há membros, o dono passa ao primeiro membro na ordem de entrada (`332`). Sala sem membros é removida (`342`).
- **Configurar.** Só o dono, sem pronto e com a sala esperando (D77). Quem não é dono não abre o diálogo no cliente (XInterface 28962). Muda os campos marcados em `flags` (411) e avisa o canal (412). Valores fora da faixa são limitados; `max_player` abaixo de quem já está sentado é ignorado.
- **Convidar.** Só o dono. O convidado do canal recebe o convite (463) e responde com 471. O convite fica pendente até a resposta e não expira (shortcut). O aceite entra sem senha.
- **Expulsar.** Só o dono, pelo nick (451). O expulso sai da sala (`322`).
- **Fim da partida.** Cada jogador em jogo manda `500`; o canal responde `501`. A sala volta à espera quando todos saem, quando o último em jogo sai da sala ou quando o servidor cai depois de pronto (D48). Todos recebem 402 sem pronto, o dono também (D77). Quem entra de novo na sala (`311`) recebe `312`, `314` e `317` só para si (D49).

Escopo da difusão:

| Opcode | Vai a | Motivo |
|--------|-------|--------|
| 302 | lobby | toda a lista de salas recebe a nova sala |
| 312 (sucesso) | lobby, menos quem já está na sala | o canal soma o jogador na sala; quem já está nela soma com o 549 |
| 322 | lobby | saída ou expulsão |
| 332 | lobby | troca de dono |
| 342 | lobby | sala removida |
| 412 | lobby | estado da sala (jogando) |
| 402, 403, 421 | membros da sala | pronto, início, slot |
| 314, 317 | só quem criou ou entrou | detalhe da sala e lista de jogadores |
| 549 | quem já está na sala | entrada de quem chegou (nó e slot) |
| 462, 463 | dono e convidado | resultado do convite e o próprio convite |
| 312 (erro), 54 com 404 ou 462 | só quem pediu | recusa |

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
| 0x00 | `u16` | opcode real (302, 404 ou 462) |
| 0x02 | `byte[2]` | padding |
| 0x04 | `i32` | código de erro (chave de `msg_error` no `landmass.wdb`) |

Evidência: `re/channel_server.md` §3 (`u16 @0` e `i32 @4`, L96–108). O cliente mostra o código e segue o dispatch com o opcode real sobre o mesmo buffer (inferido).

**301 CREATE_ROOM (C→S), 74 bytes**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `u16` | `map_num` |
| 0x02 | `char[51]` | `name` (NUL-terminado; 3 a 50 bytes) |
| 0x35 | `char[13]` | `password` (NUL-terminado; até 12 bytes, shortcut) |
| 0x42 | `u8` | `scale` |
| 0x43 | `u8` | `game_mode` |
| 0x44 | `u8` | `team_count` |
| 0x45 | `u8` | `max_player` |
| 0x46 | `u8` | `limit_time` |
| 0x48 | `u16` | `limit_score` |

Layout de `re/layouts_f0.md` §7.1, conferido com o hexdump do primeiro 301 (`test_criar_sala_entrada_de_301_offsets`). O byte @0x47 é padding.

**302 CREATE_ROOM_OUT (S→C), registro de sala, 612 bytes**

Offsets relativos ao valor do nó (`re/rooms.md` §1, §2, §5 e 412). Bytes não listados ficam zero.

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `i32` | `room_id`; chave de busca de 302, 312, 322, 332, 342 e 412 |
| 0x04 | `char[51]` | `name`, NUL-terminado (até 50 bytes; `execGetRoomInfo`) |
| 0x37 | `u8` | `has_password` (bool; `execGetRoomInfo`) |
| 0x38 | `u8` | `state`: 0 espera (RS_WAITING), 1 jogando (RS_PLAYING); D65 |
| 0x39 | `u8` | `game_mode` |
| 0x3A | `u8` | `team_count` |
| 0x3B | `u8` | `curr_player` (conta o dono) |
| 0x3C | `u8` | `curr_spectator` (0) |
| 0x3D | `u8` | `max_player` |
| 0x3E | `u8` | `open` (1) |
| 0x40 | `i16` | `map_num` |
| 0x44 | `i16` | `limit_score` |
| 0x46 | `u8` | `limit_time` |
| 0x47 | `u8` | `scale` (game_scale; a lista 141 não o traz) |
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
| 0x03 | `u8` | `scale` (game_scale, node+0x57) |
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

**411 CHANGE_ROOM_PROPERTY (C→S), 10 bytes**: `u8 flags` @0 (os bits da máscara de 412), `u16 map_num` @2 (MAP), `u8 game_mode` @4 e `u8 team_count` @5 (MODE), `u8 max_player` @6, `u8 limit_time` @7 e `u16 limit_score` @8. @1 e @9 não são usados. Shortcut: o RE diz que max, tempo e pontos são sempre escritos; o emulador só os aplica com o bit ligado.

**412 CHANGE_ROOM_PROPERTY_OUT (S→C), 16 bytes**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `i32` | `room_id` (chave de busca) |
| 0x04 | `u8` | máscara: 0x01 MAP, 0x02 MODE, 0x04 LIMIT_PLAYER, 0x08 LIMIT_SCORE, 0x10 LIMIT_TIME, 0x20 STATE, 0x40 OPEN |
| 0x06 | `i16` | `map_num` (MAP) |
| 0x08, 0x09 | `u8` | `game_mode`, `team_count` (MODE) |
| 0x0A | `u8` | `max_player` (LIMIT_PLAYER) |
| 0x0B | `u8` | `limit_time` (LIMIT_TIME) |
| 0x0C | `i16` | `limit_score` (LIMIT_SCORE) |
| 0x0E | `u8` | `open` (OPEN) |
| 0x0F | `u8` | `state` (STATE; 1 jogando, D65) |

Campo sem bit fica de fora e não muda no cliente. MODE exige `game_mode` e `team_count` juntos.

**420 CHANGE_ROOM_SLOT (C→S), 1 byte**: `u8 grupo` @0. O cliente manda o grupo novo: `ChangeTeam` usa `grupo = (i % team_count + 1) % team_count`, em que `i` é o slot atual (D66). Resposta 421 com o slot escolhido.

**542 PLAYER_DETAIL_IN (C→S), 17 bytes**: `char nick[17]` @0, NUL-terminado. Resposta 543.

**421 CHANGE_ROOM_SLOT_OUT (S→C), 8 bytes**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `i32` | `client_guid` |
| 0x04 | `u8` | `slot` |

**451 ROOM_EXPEL (C→S), 18 bytes**: `@0` não é preenchido pelo cliente (ignorado); `char nick[17]` @1. Pedido do dono. Sem resposta: o 452 não tem caso no dispatcher.

**461 ROOM_INVITE (C→S), 17 bytes**: `char nick[17]` @0, NUL-terminado. Shortcut: os 17 bytes são inferidos dos demais nicks.

**462 ROOM_INVITE_OUT (S→C), 4 bytes**: `i32 result` @0. 0 = convite enviado; CERR negativo = recusado (`re/layouts_f0.md` §7.3): -2460 nick fora do canal, -2408 quem convida não está em sala, -2406 sala cheia, -2411 convidado já em sala, -2412 partida iniciada. Quem não é dono recebe envelope `54` com -4061, que o cliente não mostra.

**463 ROOM_INVITE_NOTIFY (S→C), 21 bytes**: `i32 room_id` @0 e `char nick[17]` @4 com o nick de quem convida. Shortcut: os 17 bytes de @4 são inferidos.

**471 ROOM_INVITE_ANSWER (C→S), mínimo 5 bytes**: `i32 room_id` @0, `u8 accept` @4 (1 aceita); @5 em diante não é lido. O aceite só entra com convite pendente para a sala.

**543 PLAYER_DETAIL_OUT (S→C), 77 bytes**: resposta a 542 com os valores do banco (D107): posição (1 + contas com exp maior), jogos, vitórias e derrotas (só partidas com resultado, D105), abates, mortes, headshots, exp, nest e clã. `char nick[20]` @0; oito `i32` a partir de @0x14 (rank, jogos, vitórias, derrotas, abates, mortes, headshots, exp); `u8 nest` @0x34; `i32 clan_mark` @0x38; `char clan[17]` @0x3C. Rótulos da ficha (`LM_PlayerInfoPage`, XInterface 32801–32805): "Partida" = jogos @0x18 (`%t`), vitórias @0x1C (`%w`), derrotas @0x20 (`%l`) (`re/rooms.md` §13); `u8 nest` @0x34; `i32 clan_mark` @0x38; `char clan[17]` @0x3C.

**549 ROOM_ENTRY_OUT (S→C), 48 bytes**: a entrada de jogador de 317 (tabela acima) de quem entrou. Vai só a quem já está na sala.

**700 EXPEL_PLAYER (C→S), 18 bytes**: `u8 kind` @0 (0x10 WEB, 0x21 CHANNEL, 0x22 LOBBY) e `char nick[17]` @1. É o `/EXPEL` do console, não a expulsão do dono (essa é o 451). Não é executado (item 20).

**701 EXPEL_PLAYER_OUT (S→C), 4 bytes**: `i32` 0. Só codec: nenhum handler envia.

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
| 0x04 | `u8` | `state` (0 espera, 1 jogando; D65) |
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
| 0x04 | `i32` | `total_exp` (do lobby: fixado na entrada no canal) |
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

1. **Nick e progressão.** O nick vem em `R+0x08` de 151, 121 e 317 (`re/layouts_f0.md` §1.2), copiado de `account.nickname`. `total_exp` do 121 de quem entra e do 101 vem do banco (F3); 151, 317, 548 e 549 levam o mesmo valor, fixado na entrada no lobby (item 25). Clã e marca vão zerados até o marco 5. O nest do próprio jogador sai só no 101 (F5).
2. **111 com `count` 1.** `FUN_1001c170` não lê o corpo da entrada (`re/LM_Engine.dll/channel_dispatch_FUN_1001da60.c` L978–992). Nenhum dado do canal é enviado. Se o cliente exigir nome de canal, o layout precisa ser decodificado.
3. **`num` do `120`.** O servidor original tem `channel_count 1`; o emulador ignora o `num`. Se o cliente escolher canais por índice, a lista de 111 precisa de mais de uma entrada.
4. **`result` recusado.** -160 é o código de senha inválida do Message. O canal original pode usar outro código.
5. **`location` (101 @0xAC), `message` (123 @4) e `msg_type` (240 @0, 241 @4).** Lidos pelo cliente ou inferidos da assinatura do evento; semântica não confirmada.
6. **Mesma conta em duas conexões.** A segunda substitui a primeira no lobby sem notificá-la.
7. **Heartbeat do servidor.** O cliente responde a `2` com `2`; o emulador envia `2` a cada 10 s e nunca responde. Não há evidência de que o cliente exija esse heartbeat; se a conexão cair em 20 s sem tráfego, reduzir o intervalo.
8. **Limite de lobby.** Uma lista de 151 cabe em um quadro de 65000 bytes: no máximo 1600 entradas (`MAX_LOBBY_ENTRIES`). A lista de salas (141) cabe em 955 registros (`MAX_ROOM_ENTRIES`).
9. **Pedidos de lista (64, 66, 67).** Não tratados. 464 responde 151 com o lobby a quem está fora de sala (D67); 545 e 546 têm resposta (547 e 548). Se o lobby passar do limite do item 8, a paginação ainda não está decodificada.
10. **Chave de sessão não zerada.** O teste com o cliente real mostrou o `100` com 33 bytes zerados, depois de um `111` zerado. Não confirmado: o cliente aceitar a chave não zerada que o `111` entrega e reenviá-la em nova conexão ao canal. Se o cliente recusar, conferir `MsRegisterOut.session_key` e a regra de expiração em [authentication.md](authentication.md).
11. **544 sem resposta e ordem não confirmada.** O RE não tem opcode de retorno para `SaveOption`; o emulador não responde. A ordem dos 37 bytes segue `LM_REGISTER_INFO` (inferido: o RE mostra cópia de 37 bytes de `_OPTION_INFO`, e a struct `LM_OPTION_INFO` do UnrealScript não foi decodificada campo a campo). Se o cliente real mostrar uma opção trocada, decodificar `LM_OPTION_INFO` em `LM_Engine.u`. Conta sem registro devolve 0 em tudo (sem fonte no RE).
12. **Nome e senha da sala (301).** Layout de `re/layouts_f0.md` §7.1 (`char[51]` @2 e `char[13]` @0x35), conferido com um hexdump do cliente real. Limites de 3 a 50 bytes para o nome e 12 para a senha em `domain/rooms.py` (shortcut; o RE dá 13 bytes à senha). Confirmar com outra sala.
13. **`room_id` no 311.** A chave da sala é o guid que o cliente passa no 311 (`NetInRoom(num, pw)`). Tamanho da senha inferido pelos 5 dwords.
14. **Códigos do 312.** O `short` vai para `FUN_10021c80`, cujo mapa para `msg_error` está em gap no RE. Os códigos 1001, 1202 e 1701 são os sufixos de 211000000 + código em `msg_error` do `landmass.wdb`. "Partida já iniciada" é 212000200: o prefixo 212 não cabe no `short`, então o emulador manda 200. Confirmar o texto no cliente.
15. **Envelope 54 e dispatch.** O código fica em @4 (`re/channel_server.md` §3). O corpo real fica sobreposto ao envelope, conforme o RE (inferido). Por isso o 312 não usa envelope.
16. **Campos do registro de sala sem decodificação (D45).** `name` (0x04, `char[51]`), `has_password` (0x37) e `scale` (0x47) vêm de `execGetRoomInfo` (`re/rooms.md`), não de captura. A lista 141 tem 68 bytes e não traz `scale`, então a sala aparece com escala 0 até o 302 ou o 314 da sala. `curr_spectator` (0x3C) e `open` (0x3E) são valores fixos.
17. **Escopo da difusão.** Confirmado na análise de `re/rooms.md`, mas não no cliente real (ver tabela em [Salas](#salas)).
18. **Início e endereço da partida (403).** O 403 vai só aos membros, com `address` de 16 bytes (hipótese, `re/rooms.md` §8) e `port`. Sem servidor de partida no ar, o cliente tenta conectar e falha; isso é esperado. Com `LANDMASS_MATCH_SERVER_DIR`, o emulador sobe um servidor por sala (marco 4). O critério do marco é o recebimento do 403.
19. **Escopo do chat na sala (240).** O RE não decodifica o escopo (`re/rooms.md` §6). Assumido: remetente em sala fala só com a sala.
20. **Console e expulsão (700, 451; D41).** O 700 é o `/EXPEL` do console (`u8 kind` + nick); não é executado, porque o emulador não tem papel de administrador. O dono expulsa pelo 451, sem resposta. A UI não chama o 451 (`XInterface` L29174, comentado): o caminho só é exercido por código e pelos testes.
21. **Pronto e seletor (402, 317).** O bit de pronto é `u8 @4` do 402 e `u8 @0x29` do 317. O seletor `@0x2A` do 317 vai zero (inferido).
22. **Limite de entrada.** Valores fora da faixa na criação são limitados e logados, não recusados. Sem paginação de salas: o limite de 955 por 141 vale até o marco 4.
23. **Troca de dono (332).** Passa para o primeiro membro na ordem de entrada. Regra escolhida, não observada no cliente.
24. **Progressão no login (F2 e F3).** O 101 leva tutorial, exp, Cash e LD em `@0x28`, `@0x2C`, `@0x48` e `@0x4C` (`PlayerRecord`), e os pushes 900 e 902 saem depois do 111. Inferido dos layouts `LM_PLAYER_INFO` (`re/layouts_f0.md` §1.1 e §7.6); não confirmado no cliente real. O 902 vai no bloco misto do dispatcher (shortcut).
25. **Exp nos demais registros (D44).** O `total_exp` de 151, 317, 548 e 549 vem do lobby, fixado na entrada no canal com o valor do banco (`Lobby.join`; shortcut em `domain/lobby.py`). Não muda durante a sessão: concessão pela CLI só aparece ao reentrar. O 121 do próprio jogador continua sendo a referência. Não verificado no cliente real que 151, 317 e 548 não zerem a exp no nó.
26. **Divisão de 549 e 312 (D40).** Quem já está na sala recebe 549 (nó e slot de quem chegou); quem está no canal fora da sala e o entrante recebem 312. O RE mostra que os dois somam 1 no contador de jogadores (`disp@608-691` e `disp@2908-2912`), mas não quem os envia em cada caso: é decisão deste servidor (`RoomHandlers._joined`). Revisar com captura de dois clientes na sala. Não é a causa de o dono ver os botões desabilitados: na criação, o 312 vai ao próprio criador, que o recebe (D65, revisão de D40).
27. **Convite (461 a 471; D42).** O convite fica pendente até o 471 e não expira. O aceite entra sem senha, só com convite pendente para a sala; recusa ou convite inexistente não entra. Os 17 bytes do nick em 461 e 463 são inferidos. Revisar na primeira captura de convite.
28. **Configuração (411; D43).** Campos sem bit em `flags` não mudam; o RE manda max, tempo e pontos sempre, e o emulador só os aplica com o bit ligado (`CsChangeRoomPropertyIn`). `max_player` não cai abaixo de quem já está sentado. Revisar na primeira troca de configuração capturada.
29. **Detalhe do jogador (542 e 543; D67, D107).** O codec segue `LM_PLAYER_DETAIL_INFO` (`re/protocol_full.md` §3.2). O 542 responde com o 543 montado no banco (D107): posição, exp, nest e clã reais; jogos, vitórias, derrotas, abates, mortes e headshots saem zero até haver resultado e métricas gravadas (dúvida 17). Nick fora do canal manda envelope 54 com -2460, código de `re/layouts_f0.md` §7.3; a mensagem na tela não é conhecida. Revisar com a tela de detalhe.
30. **Inventário e morat regular (F4/F5).** 102 e 103 saem no login depois de 900 e 902; 103 só para morat com gate. Peças em -1 e skins em 0 (inferido, D31). Offsets de 102 e 103 além do que o RE dá (GUID, `apply_flag` em `@0x2D`, skins) são inferidos ([re/layouts_f0.md](../../re/layouts_f0.md) §8). Conta sem morat: a sala trava no cliente, e habilitar gate sem morat não corrige (dúvida 24 em [07-progression](../architecture/07-progression.md)). Nada disso foi confirmado no cliente real.
31. **Loja (F8; D50, D51).** 550 debita `accounts.ld` ou `cash` e cria a unidade na mesma transação. Sucesso manda 551 (ou 552), 102 (ou 103), 900 e 902, e o item aparece sem relogar. Recusa manda o mesmo opcode com o código de `NotifyItemBuy` (-4056 LD, -4055 Cash, -1 sem gate) ou 8000 (sem mensagem). Os códigos de saldo são inferidos iguais aos `CERR_BUY_*`, não vistos em runtime. Morat comprado no meio da sessão pode não ficar habilitado no gate: `bEnable` só é ligado pelo 101, então vale relogar. Catálogo abre na primeira compra (D50). O 102 depois do 551 não duplica: é upsert pela chave no mesmo mapa (`FUN_1001d6b0`, dispatcher L699–700 e L890–891), e `@0x35` = 0 não zera `apply_value`. O 552 e o 103 seguem o mesmo padrão (`FUN_100237d0`, `FUN_1001d7f0`, L727–728 e L916). `FUN_10007830`, chamado de novo pelo 103, é busca e não insere. Revisar no cliente real.
32. **Presente, Depósito, gacha e gates (F10, F11; D95 a D100).** 615 cria pendente em `gifts`; 610 e 611 listam; 612 resgata, mas o XInterface não chama 612; o 610 resgata os pendentes (D100). 591 sai do 560 com `308010006`. Os gates habilitados vêm de `accounts.gate_count` (R-GATE-01). Ver [07-progression §5.6, §5.7 e §5.4](../architecture/07-progression.md).
32. **Estado da sala (D65).** 0 é espera (RS_WAITING) e 1 é jogando (RS_PLAYING), conforme os UConst de `Core.u`. A versão anterior mandava 1 para espera e 2 para jogando; com `ready_game` do dono, `RefreshPlayers` (`XInterface` L34719) desabilitava os botões. `ROOM_WAITING` em `domain/rooms.py` é a única fonte do valor. Confirmar com dois clientes.
33. **Mudar grupo (420; D66).** O `u8` é o grupo (`ChangeTeam` calcula `i % team_count`), não o slot. O servidor põe quem pede no primeiro slot livre desse grupo, sem contar o próprio slot. Grupo inválido ou sala ausente não respondem; a posição real vai no 421. Semântica inferida do RE (`XInterface` L21737–21790), não observada no cliente.
34. **Amizade pelo nick (181 para 183).** A busca do nick é exata (`AccountRepository.find_by_nickname`, `accounts.nickname`). Nick recusado volta como 183 com id 0 e `result` -11, e o cliente não insere registro negativo (`handlers/message/social.py`). A amizade vem do menu de contexto (`AddFriendList`, 181); a ficha (542) vem de outro clique, e 464 não entra. `CurSelPlayerNick` só recebe valor ao selecionar a linha da lista (`XInterface` L26857, L27082, L32210, L32412, L62340), nunca pelo 543. Se a seleção não bate com o nick do menu, o menu passa `""` (L26876, L32227, L62359) e a recusa é silenciosa. Esse caso é do cliente e não tem correção no servidor; conferir o log `recusado` com `''` no reteste.

## Checklist no cliente real

Conferir nesta ordem; cada falha aponta o item de lacunas indicado.

1. **Hexdump do primeiro 301.** O servidor loga `CreateRoom` com hexdump. Os 74 bytes devem bater com `CsCreateRoomIn` (item 12).
2. **Criar sala com nome de 3 caracteres.** A sala aparece na lista de quem já está no lobby (302). Quem entra depois a vê no 141.
3. **Criar com nome de 2 caracteres.** Aparece a mensagem de nome curto (211000202).
4. **Entrar com senha errada.** Aparece a mensagem de senha inválida (1701), e nenhum slot fica ocupado (item 14).
5. **Entrar com a senha certa.** Os dois slots aparecem com o estado certo e o nick de cada um (item 1).
6. **Pronto.** O entrante marca pronto (401); o estado aparece nos dois clientes (402).
7. **Iniciar.** O dono inicia (401). Os dois recebem 412 e 403 com `127.0.0.1` e `7777`. O cliente tenta conectar; sem servidor de partida no ar, a falha é esperada (item 18).
8. **Iniciar sem prontos.** Aparece a mensagem "ninguém está pronto" (404, 241002702).
9. **Sair.** A lista do outro atualiza (322). Se o dono sai, o outro vira dono (332). Sala vazia some da lista (342).
10. **Expulsar.** Sem caminho de UI para o 451 (item 20): testar só se o cliente enviar. Quando enviar, o alvo sai da sala (322) e quem não é dono não recebe nada.
11. **Chat.** Mensagem na sala chega só à sala; no lobby, a todos (item 19). O remetente aparece com o nick, não com `[] texto` (item 1).
12. **Entrar em sala iniciada.** Aparece "partida já iniciada" (código 200 no 312; item 14).
13. **Queda em sala.** Os outros veem a saída (322).
14. **Configurar a sala.** O dono muda o mapa ou o máximo; os dois clientes recebem 412 e a lista atualiza (item 28).
15. **Convidar.** O dono convida o nick do outro (461). O convidado recebe o convite (463), aceita (471) e entra sem senha. Nick fora do canal: o dono recebe 462 com -2460 (item 27).
16. **Contagem com 549.** Com dois clientes já na sala, o contador de jogadores sobe uma vez para o entrante (item 26).
17. **Botões do dono (D65).** O dono vê Iniciar, configuração e Sair habilitados. O entrante não vê Iniciar habilitado (item 32); essa metade é previsão pelo mesmo valor de estado, não rastreada no `XInterface`. Sair do dono manda 321 e a sala passa ao outro (item 9).
18. **Mudar grupo (420).** Com `team_count` 2 e o entrante sem pronto, a troca de grupo manda 421 com o slot novo para os dois clientes (item 33).
19. **Ficha do jogador (542).** Clique no nick de quem está no lobby abre a ficha com os valores do banco (D107), sem "Buscando...". Nick fora do canal fecha a espera com a mensagem da UI (item 29).
20. **Amizade pelo nick (181).** Tester2 adiciona Tester pelo menu e o amigo aparece na lista. Se não aparecer, conferir o log `recusado` com `''` no servidor de mensagens (item 34).

## Responsabilidades do serviço

- Manter o lobby em memória (`domain/lobby.py`) e as salas em memória (`domain/rooms.py`).
- Resolver a chave de sessão do `100` no registro em memória (`ports/session_keys.py`).
- Gravar as opções da conta no 544 pelo `OptionsRepository` (`ports/options.py`). Sem resposta.
- Difundir entrada, saída, chat e eventos de sala conforme a tabela de escopo.
- Enviar o endereço da partida (403) vindo de `LANDMASS_GAME_HOST` e `LANDMASS_GAME_PORT`.
- Enviar heartbeat do servidor a cada 10 s por conexão.
- Partida e itens: marcos 4 e 5.
