# Message Server (TCP 7313, `net_code` 13)

Implementação: `protocol/message.py`, `handlers/message/`. Evidências e layouts completos: [`../../re/message_server.md`](../../re/message_server.md).

## Opcodes

| Opcode | Direção | Nome | Payload | Estado |
|-------:|---------|------|---------|--------|
| 2 | C→S | Heartbeat | — | confirmado |
| 100 | C→S | Login | `MS_LOGIN_IN` | confirmado (captura) |
| 101 | S→C | Resultado do login | `MS_LOGIN_OUT` | a especificar |
| 110 | C→S | Register | — | confirmado (código) |
| 111 | S→C | Resultado do register | — | a especificar |
| 120 | C→S | InMessageServer | `MS_IN_MESSAGE_SERVER_IN` (opcional, 1 byte) | confirmado (código) |
| 121 | S→C | Resultado da entrada | — | a especificar |
| 130 | C→S | GetChannelServerInfo | — | confirmado (código) |
| 131 | S→C | Lista de canais | — | a especificar |
| 150 | C→S | CreateNickname | `MS_CREATE_NICKNAME_IN` (0x37 bytes) | confirmado (código) |

"A especificar": preencher a partir de `re/message_server.md` e atualizar esta tabela.

## `MS_LOGIN_IN`

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0 | `i32` | `id_len` |
| 4 | `i32` | `pw_len` |
| 8 | `char[33]` | `login_num` |
| 41 | `byte[3]` | padding (lixo) |
| 44 | `char[id_len]` | `id` |
| 44+id_len | `char[pw_len]` | `pw` |

## Sequência esperada pelo cliente

`connect → 100/101 → 110/111 → 120/121 → 130/131 → (Channel)`, conforme `LandMass.log` de sessão real.
