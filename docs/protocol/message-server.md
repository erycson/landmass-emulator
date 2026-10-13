# Message Server (TCP 7313, `net_code` 13)

Implementação: `protocol/message.py` (layouts), `handlers/message/` (comportamento), `net/server.py` (transporte). Evidências e layouts completos: [`../../re/message_server.md`](../../re/message_server.md).

## Opcodes

| Opcode | Direção | Nome | Payload | Estado |
|-------:|---------|------|---------|--------|
| 2 | C→S | Heartbeat | — | implementado: sem resposta |
| 100 | C→S | Login | `MS_LOGIN_IN` | implementado (captura) |
| 101 | S→C | Resultado do login | `MS_LOGIN_OUT` (8 bytes) | implementado |
| 110 | C→S | Register | — | implementado: exige login; emite a chave de sessão |
| 111 | S→C | Resultado do register | `MS_REGISTER_OUT` (0x4C bytes) | implementado: opções gravadas da conta (zeros se não houver) e chave de sessão |
| 120 | C→S | InMessageServer | — (1 byte opcional, ignorado) | implementado: exige login |
| 121 | S→C | Resultado da entrada | `MS_IN_MESSAGE_SERVER_OUT` (0x1C bytes) | implementado |
| 130 | C→S | GetChannelServerInfo | — | implementado: exige login |
| 131 | S→C | Lista de canais | `MS_GET_CHANNEL_SERVER_OUT` (2 + 72·n bytes) | implementado |
| 150 | C→S | CreateNickname | `MS_CREATE_NICKNAME_IN` (0x37 bytes) | não tratado (logado e ignorado) |

Opcodes sem handler (140, 150, 180 GetFriendList, clã, ...): logados com hexdump e ignorados; a conexão continua.

## Comportamento

- Login é o único pedido aceito antes da autenticação. Após `101` com `result == 0`, a conexão fica autenticada; pedidos 110/120/130 sem login são logados e ignorados (sem resposta).
- Um novo login zera a autenticação anterior. Login com token inválido responde `result = -160` e deixa a conexão sem conta.
- Heartbeat não recebe resposta e conta como tráfego para o timeout.
- Payload malformado de opcode conhecido: logado com o motivo (sem hexdump) e ignorado.
- `login_num` nunca é logado.
- Cada 110 com login emite uma chave de sessão nova, que invalida a anterior da conta. A chave vai no 111 e é validada pelo Channel (ver [authentication.md](authentication.md)).

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
| 0x04 | `i32` | `result` | `0` sucesso; `-160` senha inválida |

**`MS_REGISTER_OUT` (111), 0x4C bytes**

| Offset | Tamanho | Campo |
|-------:|--------:|-------|
| 0x00 | 37 | `LM_REGISTER_INFO`: 37 `u8` na ordem de `re/message_server.md` §4.1 (`background` … `screenshot`). Opções gravadas pelo 544 do Channel (`account_options`); zeros se a conta não tem registro. |
| 0x25 | `char[33]` | `session_key`, NUL-terminado: 32 caracteres hexadecimais minúsculos (`secrets.token_hex(16)`). Emitida para a conta logada. O cliente copia os 33 bytes para `DAT_1005AE20` (`re/message_server.md` §4) e os envia no `100` do Channel. |
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
| 0x04 | `u8` | `channel_mode` | `0` |
| 0x05 | `u8` | `access_level` | `0` |
| 0x06..0x07 | `byte[2]` | padding | `0` |
| 0x08 | `i32` | `access_exp` | `0` |
| 0x0C | `u16` | `max_client_count` | `LANDMASS_CHANNELS[i].max_clients` |
| 0x0E | `u16` | `curr_client_count` | `0` |
| 0x10 | `u16` | `pick_client_count` | `0` |
| 0x12 | `u16` | `service_port` | porta do canal (padrão `LANDMASS_CHANNEL_PORT`) |
| 0x14 | `char[16]` | `service_address`, NUL-terminado; máximo 15 caracteres | endereço do canal (padrão `LANDMASS_PUBLIC_HOST`) |
| 0x24 | `char[36]` | `server_name`, NUL-terminado; máximo 35 caracteres | `LANDMASS_CHANNELS[i].name` |

Strings de largura fixa são truncadas no codec para caber com o NUL; nomes e hosts longos demais são recusados na configuração.

## Sequência esperada pelo cliente

`connect → 100/101 → 110/111 → 120/121 → 130/131 → (Channel)`, conforme `LandMass.log` de sessão real.

Quando o nickname já existe (criado pela CLI `account create`), o cliente vai direto de 111 para 120. O ramo 140/150 (criação de nickname no jogo) não existe no marco 1.
