# Channel Server (TCP 7314, `net_code` 14)

Implementação: `protocol/channel.py`, `protocol/game.py`, `handlers/channel/`. Evidências e layouts completos: [`../../re/channel_server.md`](../../re/channel_server.md).

## Grupos de opcodes

| Faixa | Assunto |
|-------|---------|
| 1xx | Entrada no channel server, canais, lobby, lista de jogadores |
| 3xx | Lista e detalhes de salas |
| 4xx | Sala: slots, propriedades, pronto, início |
| 5xx | Itens, loja, hangar, presentes |
| `GS_*` | Game Server Host ↔ Channel (porta 7314, autenticado por `ch_pw`) |

Sequência observada em sessão real: `101 → 111 → 103×n → 151 → 141 → 121 → 312/541/547/548/123 ...`.

## Opcodes

Tabela completa a preencher a partir de `re/channel_server.md` (opcode, direção, struct, semântica, estado).

## Responsabilidades do serviço

- Manter canais, lobby e salas em memória (serviço de domínio único).
- Registrar Game Server Hosts e alocar um por sala ao iniciar a partida.
- Enviar `GS_IN_PLAYER` ao host antes de liberar os clientes para conectar.
- Persistir resultado da partida e alterações de inventário.
