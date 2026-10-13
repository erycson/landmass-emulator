# Channel Server (TCP 7314, `net_code` 14)

Implementação: `protocol/channel.py` (codec), `domain/lobby.py` (presença), `handlers/channel/` (comportamento), `net/server.py` (transporte). Evidências e layouts completos: [`../../re/channel_server.md`](../../re/channel_server.md).

Este documento cobre o que o emulador implementa (marco 2: entrada, lobby, chat). Os demais opcodes da tabela completa de `re/channel_server.md` seguem como não tratados: logados com hexdump e ignorados, sem derrubar a conexão.

## Grupos de opcodes

| Faixa | Assunto | Estado |
|-------|---------|--------|
| 1xx | Entrada no canal, lobby, lista de jogadores | marco 2 (100, 120, 122 e respostas) |
| 2 | Heartbeat | marco 2 |
| 2xx | Chat | marco 2 (240/241) |
| 3xx | Lista e detalhes de salas | marco 3 |
| 4xx | Sala: slots, propriedades, pronto, início | marco 3 |
| 5xx | Itens, loja, hangar, presentes | marco 5 |
| `GS_*` | Game Server Host ↔ Channel (autenticado por `ch_pw`) | marco 4 |

Sequência de entrada pelo cliente, conforme `re/NOTES.md`: `101 → 111 → 151 → 141 → 121`. O emulador mantém a ordem.

## Fluxo implementado

| Pedido (C→S) | Resposta (S→C) | Efeito |
|--------------|----------------|--------|
| `2` heartbeat | nenhuma | Conta como tráfego. O servidor não responde. |
| `100` InChannelServer, `char session_key[33]` | `101` (176 bytes, `result` @0xa8) e `111` (`count` 1) | Resolve a chave de sessão emitida no `111` do Message. Chave recusada (zerada, desconhecida, expirada ou de conta reemitida): `101` com `result` -160 e sem entrada no lobby. |
| `120` InChannel, corpo ignorado | `151` (lista do lobby, sem o próprio jogador), `141` (salas vazias), `121` (próprio registro) | Entra no lobby. Os demais jogadores recebem `121` com o registro do recém-chegado. |
| `122` OutChannel | `123` (próprio id) | Sai do lobby. Os demais jogadores recebem `123`. |
| `240` SendMsg, `u8 msg_type`, `u8 len`, texto | `241` a todos do lobby, remetente incluído | Chat do lobby. Sem login ou fora do lobby: ignorado. |
| (queda da conexão) | `123` aos demais | Saída implícita. |
| servidor, a cada 10 s | `2` heartbeat | O cliente responde com `2`; o servidor ignora essa resposta. |

Opcodes sem handler (inclusive 67, 64, 66, 464, 545, 546): logados com hexdump e ignorados. Pedido com payload inválido: logado sem hexdump e ignorado.

## Identificação do cliente

O cliente não envia nickname nem token ao entrar no canal. Envia no `100` a chave de sessão que recebeu no `111` do Message (`char[33]` @0x25; [message-server.md](message-server.md)). O canal resolve a chave com `SessionKeyRegistry` (`ports/session_keys.py`, implementado em `domain/session_keys.py`) e usa `account.id` como `client_guid` de toda a sessão. O canal não acessa o banco. Regras da chave em [authentication.md](authentication.md).

Evidências: o corpo do `100` tem 33 bytes (teste com o cliente real; `u8 @32` é o NUL do `char[33]`). O `ChannelServer.exe` original loga `in->guid=%s` logo após `InChannelServer(`. Inferido: o `num` de `InChannelServer(int num)` do UnrealScript não viaja no pacote.

## Opcodes

| Opcode | Direção | Nome (`CsOp`) | Corpo | Estado |
|-------:|---------|---------------|-------|--------|
| 2 | C↔S | `HEARTBEAT` | vazio | implementado |
| 100 | C→S | `IN_CHANNEL_SERVER` | `char session_key[33]` | implementado |
| 101 | S→C | `IN_CHANNEL_SERVER_OUT` | 176 bytes | implementado |
| 111 | S→C | `CHANNEL_INFO_OUT` | `u8 count` = 1 | implementado (shortcut) |
| 120 | C→S | `IN_CHANNEL` | `u32 num` ou vazio | implementado (`num` ignorado) |
| 121 | S→C | `IN_CHANNEL_OUT` | entrada de jogador, 40 bytes | implementado |
| 122 | C→S | `OUT_CHANNEL` | vazio | implementado |
| 123 | S→C | `OUT_CHANNEL_OUT` | 8 bytes | implementado |
| 141 | S→C | `CHANNEL_ROOM_INFO_OUT` | `u16 count` = 0 | implementado (lista vazia) |
| 151 | S→C | `CHANNEL_PLAYER_INFO_OUT` | `u16 count` + entradas de 40 bytes | implementado |
| 240 | C→S | `SEND_MESSAGE` | `u8 msg_type`, `u8 len`, texto | implementado |
| 241 | S→C | `SEND_MESSAGE_OUT` | 8 bytes + texto | implementado |
| 67, 64, 66, 464, 545, 546 | C→S | pedidos de lista | — | não tratados |

## Layouts

Offsets no corpo, depois do cabeçalho `u16`. Campo sem nome no RE recebe o nome do offset.

**100 IN_CHANNEL_SERVER (C→S), 33 bytes**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `char[33]` | `session_key`, NUL-terminado: 32 hexadecimais minúsculos. Mínimo 33 bytes; o emulador ignora bytes extras. |

**101 IN_CHANNEL_SERVER_OUT (S→C), 176 bytes**

| Offset | Tipo | Campo | Valor |
|-------:|------|-------|-------|
| 0x00..0x8F | `byte[144]` | registro do próprio jogador (não decodificado) | zeros |
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

| Offset na entrada | Tipo | Campo do cliente (nó, offset) |
|------------------:|------|-------------------------------|
| 0x00 | `i32` | `client_guid` (+0xA0, chave) |
| 0x04 | `i32` | +0x3C |
| 0x08 | `i32` | +0x10 |
| 0x0C | `i32` | +0x14 |
| 0x10 | `i32` | +0x18 |
| 0x14 | `i32` | +0x1C |
| 0x18 | `u8` | +0x20 |
| 0x19 | `u8` | +0x23 |
| 0x1A | `u8` | +0x21 |
| 0x1B | `byte` | não lido (padding do stride) |
| 0x1C | `i32` | +0x28 |
| 0x20 | `i32` | +0x2C |
| 0x24 | `u8` | +0x30 |
| 0x25..0x27 | `byte[3]` | padding |

Os campos de estatística são enviados zerados até o marco 5 (persistência).

**151 CHANNEL_PLAYER_INFO_OUT (S→C)**

| Offset | Tipo | Campo |
|-------:|------|-------|
| 0x00 | `u16` | `count` |
| 0x02 | entrada[count] | 40 bytes cada, ver tabela acima |

**141 CHANNEL_ROOM_INFO_OUT (S→C), 2 bytes**

| Offset | Tipo | Campo | Valor |
|-------:|------|-------|-------|
| 0x00 | `u16` | `count` | 0 |

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

## Lobby

- Membros do lobby: `domain/lobby.py` (`Lobby`), chave `client_guid`, valor a conexão. Estado só em memória (D12).
- Cada conexão tem uma `outbox`. Quem quer enviar a outra conexão enfileira o corpo nela. Só a task de escrita da própria conexão grava no socket ([03-emulator](../architecture/03-emulator.md#concorrência)).
- A lista de 151 é tirada antes do join, e o broadcast de 121 não vai ao próprio jogador: ele recebe `[151, 141, 121]` como resposta ao `120`, na ordem observada.
- Queda da conexão com jogador no lobby gera `123` aos demais. Conexão sem jogador no lobby não gera nada.

## Lacunas e inferências

Cada item com código afetado tem um `shortcut:` no código; o item 9 é ausência de handler e não tem linha própria. Ao confirmar no cliente real, remova a inferência ou corrija o layout.

1. **Nickname de outros jogadores.** Os layouts de 121 e 151 não têm campo de nome. Os nomes de `LM_PLAYER_INFO.strNick` vêm de outro caminho não decodificado (candidatos: 543, 548). Sem nome, a lista mostra entradas sem nickname.
2. **111 com `count` 1.** `FUN_1001c170` não lê o corpo da entrada (`re/LM_Engine.dll/channel_dispatch_FUN_1001da60.c` L978–992). Nenhum dado do canal é enviado. Se o cliente exigir nome de canal, o layout precisa ser decodificado.
3. **`num` do `120`.** O servidor original tem `channel_count 1`; o emulador ignora o `num`. Se o cliente escolher canais por índice, a lista de 111 precisa de mais de uma entrada.
4. **`result` recusado.** -160 é o código de senha inválida do Message. O canal original pode usar outro código.
5. **`location` (101 @0xAC), `message` (123 @4) e `msg_type` (240 @0, 241 @4).** Lidos pelo cliente ou inferidos da assinatura do evento; semântica não confirmada.
6. **Mesma conta em duas conexões.** A segunda substitui a primeira no lobby sem notificá-la.
7. **Heartbeat do servidor.** O cliente responde a `2` com `2`; o emulador envia `2` a cada 10 s e nunca responde. Não há evidência de que o cliente exija esse heartbeat; se a conexão cair em 20 s sem tráfego, reduzir o intervalo.
8. **Limite de lobby.** Uma lista de 151 cabe em um quadro de 65000 bytes: no máximo 1600 entradas (`MAX_LOBBY_ENTRIES`).
9. **Pedidos de lista (64, 66, 67, 464, 545, 546).** Não tratados. Se o lobby ficar vazio no cliente real, o próximo passo é tratar 545/546 (listas de salas e de jogadores), cujo layout de entrada ainda não foi decodificado.
10. **Chave de sessão não zerada.** O teste com o cliente real mostrou o `100` com 33 bytes zerados, depois de um `111` zerado. Não confirmado: o cliente aceitar a chave não zerada que o `111` entrega e reenviá-la em nova conexão ao canal. Se o cliente recusar, conferir `MsRegisterOut.session_key` e a regra de expiração em [authentication.md](authentication.md).

## Responsabilidades do serviço

- Manter o lobby em memória (`domain/lobby.py`).
- Resolver a chave de sessão do `100` no registro em memória (`ports/session_keys.py`).
- Difundir entrada, saída e chat aos jogadores do lobby.
- Enviar heartbeat do servidor a cada 10 s por conexão.
- Salas, slots, pronto, partida e itens: marcos 3 a 5.
