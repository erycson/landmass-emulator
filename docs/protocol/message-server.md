# Message Server (TCP 7313, `net_code` 13)

Implementação: `protocol/message.py` (layouts), `handlers/message/` (comportamento), `net/server.py` (transporte). Evidências e layouts completos: [`../../tools/re/message_server.md`](../../tools/re/message_server.md).

## Opcodes

| Opcode | Direção | Nome | Payload | Estado |
|-------:|---------|------|---------|--------|
| 2 | C→S | Heartbeat | — | implementado: sem resposta |
| 100 | C→S | Login | `MS_LOGIN_IN` | implementado (captura) |
| 101 | S→C | Resultado do login | `MS_LOGIN_OUT` (8 bytes) | implementado |
| 110 | C→S | Register | — | implementado: exige login; emite a chave de sessão |
| 111 | S→C | Resultado do register | `MS_REGISTER_OUT` (0x4C bytes) | implementado: opções gravadas da conta (teclas e sensibilidade padrão se não houver, D140, D172) e chave de sessão |
| 120 | C→S | InMessageServer | — (1 byte opcional, ignorado) | implementado: exige login |
| 121 | S→C | Resultado da entrada | `MS_IN_MESSAGE_SERVER_OUT` (0x1C bytes) | implementado: `clan_code` é o id do clã da conta (0 sem clã) |
| 130 | C→S | GetChannelServerInfo | — | implementado: exige login |
| 131 | S→C | Lista de canais | `MS_GET_CHANNEL_SERVER_OUT` (2 + 72·n bytes) | implementado |
| 150 | C→S | CreateNickname | `MS_CREATE_NICKNAME_IN` (0x37 bytes) | não tratado (logado e ignorado) |
| 160 | C→S | SendWhisper | `MS_SEND_WHISPER_IN` (0x14 + texto) | implementado: exige login |
| 161 | S→C | Sussurro recebido | `MS_SEND_WHISPER_OUT` (0x14 + texto) | implementado: só ao destinatário |
| 162 | S→C | Erro de sussurro | `MS_SEND_WHISPER_ERROR_OUT` (0x18 + texto) | implementado: `-11` nick inexistente; `-19` fora do Message ou bloqueado |
| 170 | C→S | GetRankingInfo | — | implementado: exige login; responde 171. Só por comando de console (a UI não envia) |
| 171 | C→S | GetClanInfo | — | implementado: exige login e clã; responde 172 |
| 171 | S→C | Ranking (resposta a 170) | `MS_RANKING_INFO_OUT` (0x20 por linha, sentinela zerada se houver menos de 100) | implementado: top 100 por `total_exp` |
| 172 | S→C | Clã (resposta a 171) | 88 bytes | implementado: layout parcial, ver abaixo |
| 174 | C→S | GetClanMember | — | implementado: exige login e clã; responde 175 por membro |
| 175 | S→C | Membro do clã | `MS_CLAN_MEMBER_OUT` (0x20 bytes) | implementado |
| 177 | C→S | SendClanMessage | `u16 len` + texto (máx. 0x78) | implementado: exige clã; entrega 178 aos membros online |
| 178 | S→C | Chat de clã | `MS_CLAN_MESSAGE_OUT` (0x14 + texto) | implementado |
| 180 | C→S | GetFriendList | — | implementado: exige login; responde 183 e 188 |
| 181 | C→S | AddFriend | `MS_NICK_IN` (17 bytes) | implementado: responde 183. Sem confirmação do alvo: grava na hora (D33 e D79). Recusa: 183 com id 0 e `result` -11, que o cliente não insere |
| 182 | C→S | DelFriend | `MS_ACCOUNT_ID_IN` (4 bytes) | implementado: responde 184 |
| 183 | S→C | Registro de amigo | `MS_CONTACT_RECORD` (0x2C bytes) | implementado |
| 184 | S→C | Amigo removido | `MS_DEL_FRIEND_OUT` (8 bytes) | implementado |
| 186 | C→S | AddBlack | `MS_NICK_IN` (17 bytes) | implementado: responde 188 |
| 187 | C→S | DelBlack | `MS_ACCOUNT_ID_IN` (4 bytes) | implementado: responde 189 |
| 188 | S→C | Registro de bloqueado | `MS_CONTACT_RECORD` (0x2C bytes) | implementado |
| 189 | S→C | Bloqueio removido | `MS_DEL_BLACK_OUT` (8 bytes) | implementado |
| 190 | C→S | RefreshFriend | `MS_RELATION_IDS_IN` (4 + 4·n bytes) | implementado: responde 191 |
| 191 | S→C | Lote de amigos | `MS_REFRESH_FRIEND_OUT` (4 + 0x14·n bytes) | implementado |
| 192 | C→S | RefreshBlack | `MS_RELATION_IDS_IN` (4 + 4·n bytes) | implementado: responde 193 |
| 193 | S→C | Lote de bloqueados | `MS_REFRESH_BLACK_OUT` (4 + 0x14·n bytes) | implementado |
| 194 | C→S | RefreshClan | `MS_RELATION_IDS_IN` (4 + 4·n bytes) | implementado: exige clã; responde 195 |
| 195 | S→C | Lote de membros do clã | `MS_REFRESH_CLAN_OUT` (0x0C + 0x0C·n bytes) | implementado |

Opcodes sem handler (140, 150, 152, ...): logados com hexdump e ignorados; a conexão continua. 173 (clã removido) e 176 (membro removido) não são emitidos: nenhum pedido do cliente os dispara e a saída de clã é feita pela CLI (D55).

## Comportamento

- Login é o único pedido aceito antes da autenticação. Após `101` com `result == 0`, a conexão fica autenticada; pedidos 110/120/130 sem login são logados e ignorados (sem resposta).
- Um novo login zera a autenticação anterior. Login com token inválido responde `result = -160` e deixa a conexão sem conta.
- Heartbeat não recebe resposta e conta como tráfego para o timeout.
- Payload malformado de opcode conhecido: logado com o motivo (sem hexdump) e ignorado.
- `login_num` nunca é logado.
- Cada 110 com login emite uma chave de sessão nova, que invalida a anterior da conta. A chave vai no 111 e é validada pelo Channel (ver [authentication.md](authentication.md)).

## Amigos, bloqueios, sussurro e presença (F12)

Implementação: `handlers/message/social.py` e `whisper.py`; presença em `domain/presence.py` (D32). Tabelas `friends` e `blocks` em [04-persistence](../architecture/04-persistence.md).

- Relação dirigida: A ter B como amigo não faz B ter A. Amizade e bloqueio são listas separadas. O id do amigo é o `account_id` do alvo, o mesmo que o cliente devolve em 182 e 187.
- 180 responde 183 por amigo e, depois, 188 por bloqueado, um registro por mensagem. Lista vazia não responde.
- 181 e 186 criam a relação pelo nick e respondem com o registro do alvo (183 ou 188). Criar de novo é idempotente. Recusa (nick inválido, nick inexistente ou a própria conta) responde com registro de id 0 e `result` `-11` no gate, sem gravar.
- 182 e 187 removem pelo id e respondem com o mesmo id em `@0` e o resultado em `@4`: `0` removido; `-11` não existia.
- 190 e 192 respondem em lote (191, 193) só com os ids da própria lista. Ids de outras contas são ignorados, sem vazar exp. Sem nenhum id da lista, a resposta tem contagem 0.
- Sussurro (160): o destinatário conectado no Message recebe 161; o remetente não recebe confirmação. Destinatário fora do Message, ou que bloqueou o remetente, recebe 162 com `-19`. Nick inexistente: 162 com `-11`. Texto acima de 0x78 bytes é payload malformado e é ignorado.
- Presença: online é ter conexão autenticada no Message. Entra no login aceito e sai ao fechar a conexão ou no início de outro login. Não há aviso de entrada e saída: o cliente consulta o estado em 180, 190 e 192 (D39).
- Pedidos de amigo, bloqueio e sussurro sem login são ignorados, sem resposta.

## Clã e ranking (F13, F14)

Implementação: `handlers/message/clan.py` e `ranking.py`; layouts em `protocol/message.py`; tabelas `clans` e `clan_members` em [04-persistence](../architecture/04-persistence.md). Criar, entrar, sair, renomear e marcar são feitos pela CLI (`landmass-emu clan`, D55): o cliente não tem pedido para isso.

- 121 leva `clan_code` = id do clã da conta (0 sem clã). Com clã, o cliente pede 171 e 174 (features §0.1).
- 171 (GetClanInfo) responde 172 com o clã da conta; sem clã, não responde. Layout de 88 bytes: `i32` @0 = 0 (índice da lista do cliente, inferido); nome `char[17]` @4 (inferido: `execGetClanInfo` lê corpo+4); `i32` id do clã @0x18 (decodificado: `node+0x28`); mestre `char[17]` @0x1D (inferido: `execGetClanInfo` lê corpo+0x1D); `i32` marca @0x4C (decodificado: `node+0x2C`); `u8` @0x50 = 0 (`node+0x30`, sem leitor identificado).
- 174 responde 175 por membro, um por pacote, como 183. 175: chave `i16` @0 (id da conta; contas acima de 32767 são omitidas, ver shortcut em `handlers/message/clan.py`), nick `char[17]` @2, estado `u8` @0x14 (0x22 conectado), `i32` exp @0x18. `u8` @0x1C = 0: `+0x23` no cliente não tem leitor identificado, e o grau do membro não sai no protocolo.
- 177 (SendClanMessage): `u16 len` @0, texto a partir de @2. `len` acima de 0x78 ou payload menor que `2 + len` é malformado e é ignorado sem entregar (o cliente copia sem limite). Só quem tem clã envia; sem clã, ignora. 178 vai aos membros online do clã, inclusive a quem enviou, como o chat geral (D58). Layout igual ao de 161.
- 194 (RefreshClanList) usa `MS_RELATION_IDS_IN`, como 190, e responde 195 só com os ids do próprio clã (sem vazar exp de outro clã). 195: cabeçalho de 12 bytes com `i32` clã @0, `i32` marca @4, `u8` @8 = 0 e `u8` contagem @9; registros de 0x0C a partir de @0x0C: `i32` conta @0, `i32` exp @4, `u8` estado @8.
- 170 (GetRankingInfo) responde 171 com o top 100 por `total_exp` decrescente, com empate pelo id da conta. Entrada de 0x20: `i32` índice @0 (slot 0 a 99, sequencial), `u16` posição @4 (empate na menor posição: 1, 1, 3), nick `char[17]` @6, `i32` exp @0x18, `u16` clã @0x1C. Com menos de 100 linhas, a última entrada é zerada: o laço do cliente não confere o tamanho e para em posição 0 (D56).
- Ranking por nest (oddeye, shadow, leon) não cabe no protocolo: 170 não tem corpo e 171 não tem campo de nest. Fica fora (D108, dúvida 22).
- 173 e 176 não são emitidos (D55).
- Limites conhecidos: 171 usa `u16` para o clã, então um clã acima de 65535 sai como 0; 175 usa `i16` para a conta.

## `MS_LOGIN_IN`

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0 | `i32` | `id_len` |
| 4 | `i32` | `pw_len` |
| 8 | `char[33]` | `login_num` |
| 41 | `byte[3]` | padding (lixo) |
| 44 | `char[id_len]` | `id` |
| 44+id_len | `char[pw_len]` | `pw` |

No fluxo por token, `id` e `pw` vêm vazios e são ignorados (senha fica para o argon2id, D8).

## Respostas (offsets no corpo, depois do cabeçalho `u16`)

**`MS_LOGIN_OUT` (101), 8 bytes**

| Offset | Tipo | Campo | Valor |
|-------:|------|-------|-------|
| 0x00 | `u8` | `forced_login` | `0` |
| 0x01..0x03 | `byte[3]` | padding | `0` |
| 0x04 | `i32` | `result` | `0` sucesso; `-160` senha inválida ou conta bloqueada (D106) |

**`MS_REGISTER_OUT` (111), 0x4C bytes**

| Offset | Tamanho | Campo |
|-------:|--------:|-------|
| 0x00 | 37 | `LM_REGISTER_INFO`: 37 `u8` na ordem de `tools/re/message_server.md` §4.1 (`background` … `screenshot`). Opções gravadas pelo 544 do Channel (`account_options`); teclas e sensibilidade padrão se a conta não tem registro (D140, D172). |
| 0x25 | `char[33]` | `session_key`, NUL-terminado: 32 caracteres hexadecimais minúsculos (`secrets.token_hex(16)`). Emitida para a conta logada. O cliente copia os 33 bytes para `DAT_1005AE20` (`tools/re/message_server.md` §4) e os envia no `100` do Channel. |
| 0x46 | 2 | padding |
| 0x48 | `i32` | `result` = `0` |

**`MS_IN_MESSAGE_SERVER_OUT` (121), 0x1C bytes**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `i32` | `result` = `0` |
| 0x04 | `char[17]` | `nickname`, NUL-terminado; máximo 16 bytes cp1252 (excedente truncado) |
| 0x15..0x17 | `byte[3]` | zeros |
| 0x18 | `i32` | `clan_code` = `0` |

**`MS_GET_CHANNEL_SERVER_OUT` (131), 2 + 72·n bytes**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `u8` | `count` (n, máximo 255) |
| 0x01 | `u8` | `bRandom` = `0` |
| 0x02 | `LM_SERVER_INFO[n]` | 72 bytes cada (tabela abaixo) |

**`LM_SERVER_INFO` (72 bytes), entrada de 131**

| Offset | Tipo | Campo | Valor no emulador |
|-------:|------|-------|-------------------|
| 0x00 | `u16` | `server_id` | 1, 2, ... (ordem na configuração) |
| 0x02 | `u8` | `server_type` | `0` |
| 0x03 | `u8` | `server_group` | `0` |
| 0x04 | `u8` | `channel_mode` | `0`; vem de `LANDMASS_CHANNELS[].mode`. 6 é `CM_CLAN` (D199, `docs/protocol/clan-war.md`) |
| 0x05 | `u8` | `access_level` | `0` (requisito do canal; o cliente não lê, D195) |
| 0x06..0x07 | `byte[2]` | padding | `0` |
| 0x08 | `i32` | `access_exp` | `0` |
| 0x0C | `u16` | `max_client_count` | `LANDMASS_CHANNELS[i].max_clients` |
| 0x0E | `u16` | `curr_client_count` | `0` |
| 0x10 | `u16` | `pick_client_count` | `0` |
| 0x12 | `u16` | `service_port` | porta do canal (padrão `LANDMASS_CHANNEL_PORT`) |
| 0x14 | `char[16]` | `service_address`, NUL-terminado; máximo 15 caracteres | endereço do canal (padrão `LANDMASS_PUBLIC_HOST`) |
| 0x24 | `char[36]` | `server_name`, NUL-terminado; máximo 35 caracteres | `LANDMASS_CHANNELS[i].name` |

Strings de largura fixa são truncadas no codec para caber com o NUL; nomes e hosts longos demais são recusados na configuração.

## Layouts de amigos, bloqueio e sussurro (F12)

Offsets do corpo, sem o cabeçalho `u16`. Pedidos (C→S) e respostas (S→C).

**`MS_SEND_WHISPER_IN` (160), 0x14 + n bytes**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `char[18]` | `target`: nick do destinatário, NUL-terminado |
| 0x12 | `u16` | `len` do texto (máximo 0x78) |
| 0x14 | `char[len]` | `text` |

**`MS_SEND_WHISPER_OUT` (161), 0x14 + n bytes**: mesmo layout, com `sender` (nick de quem enviou) em 0x00.

**`MS_SEND_WHISPER_ERROR_OUT` (162), 0x18 + n bytes**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `i32` | `result`: `-11` nick inexistente; `-19` fora do Message ou bloqueado |
| 0x04 | `char[18]` | `target` |
| 0x16 | `u16` | `len` |
| 0x18 | `char[len]` | `text` |

**`MS_NICK_IN` (181, 186), 17 bytes**: `char[17]` `nick`, NUL-terminado.

**`MS_ACCOUNT_ID_IN` (182, 187), 4 bytes**: `i32` `account_id` do amigo ou do bloqueado.

**`MS_CONTACT_RECORD` (183, 188), 0x2C bytes**: um registro por mensagem.

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `i32` | `account_id` (chave). Em recusa, `0` |
| 0x04 | `char[17]` | `nickname`, NUL-terminado (máximo 16 bytes) |
| 0x18, 0x1C | `i32` | reservados: `0` |
| 0x20 | `i32` | `total_exp` |
| 0x25 | `u8` | `online`: `0x22` conectado; `0` fora |
| 0x28 | `i32` | gate: `0` aceita; negativo recusa (`-11`) |

Os demais bytes são zero.

**`MS_DEL_FRIEND_OUT` (184), `MS_DEL_BLACK_OUT` (189), 8 bytes**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `i32` | `account_id` ecoado (vem de 182 ou 187) |
| 0x04 | `i32` | `result`: `0` removido; `-11` não existia. O cliente tira o nó pela chave em `@0` só com `@4 == 0` |

**`MS_RELATION_IDS_IN` (190, 192), 4 + 4·n bytes**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `u8` | `count`: 1 a 14; fora disso, payload malformado |
| 0x01..0x03 | `byte[3]` | padding |
| 0x04 | `i32[count]` | ids das contas |

**`MS_REFRESH_FRIEND_OUT` (191), `MS_REFRESH_BLACK_OUT` (193), 4 + 0x14·n bytes**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `u8` | `count` |
| 0x01..0x03 | `byte[3]` | zeros |
| 0x04 | registro de 0x14 bytes, `count` vezes | ver abaixo |

Registro (relativo ao início do registro):

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `i32` | `account_id` |
| 0x04 | `i32` | `total_exp` |
| 0x08, 0x0C | `i32` | `0` |
| 0x10 | `u8` | `nest`: `0` |
| 0x11 | `u8` | `online`: `0x22` conectado; `0` fora |
| 0x12..0x13 | `byte[2]` | padding |

## Sequência esperada pelo cliente

`connect → 100/101 → 110/111 → 120/121 → 130/131 → (Channel)`, conforme `LandMass.log` de sessão real.

Quando o nickname já existe (criado pela CLI `account create`), o cliente vai direto de 111 para 120. O ramo 140/150 (criação de nickname no jogo) não existe no marco 1.
