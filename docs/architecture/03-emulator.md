# Arquitetura do emulador

## Camadas

```mermaid
flowchart TB
  T[net — transport<br/>asyncio streams, framing, sessão]
  CO[protocol — codec<br/>bytes ⇄ dataclasses]
  H[handlers — casos de uso por opcode]
  DO[domain — entidades e regras]
  PO[ports — Protocols de repositório]
  AD[db / settings — SQLAlchemy, pydantic-settings]
  APP[app.py — composição]
  T --> CO
  T --> H
  H --> CO
  H --> DO
  H --> PO
  AD -. implementa .-> PO
  APP --> T
  APP --> AD
```

Regras de dependência:

- `protocol` e `domain` não importam `net` nem `db`.
- `handlers` dependem de `ports` (Protocols) e de `protocol`; nunca de SQLAlchemy. Recebem `net.session.Session` (estado da conexão, sem socket).
- `db` implementa `ports`. Componha tudo em um único ponto: `app.py`.

## Estrutura de pacotes

| Caminho | Responsabilidade |
|---------|------------------|
| `src/landmass_emu/__main__.py` | CLI: `serve`, `sniff`, `account create`, `account token`. |
| `src/landmass_emu/app.py` | Composição: repositório, roteador, servidor (`message_server`, `open_accounts`). |
| `src/landmass_emu/admin.py` | Operações de conta da CLI: criar, regenerar token, gravar `.bat`. |
| `src/landmass_emu/settings.py` | Configuração (`pydantic-settings`), ver [05-configuration.md](05-configuration.md). |
| `src/landmass_emu/net/framing.py` | Leitura/escrita de frames `u16 + body`. |
| `src/landmass_emu/net/session.py` | Estado por conexão: peer e conta autenticada. |
| `src/landmass_emu/net/server.py` | `start_service` por serviço: loop de leitura, timeout, roteamento, envio de respostas. |
| `src/landmass_emu/protocol/header.py` | Cabeçalho `(opcode << 5) \| net_code`. |
| `src/landmass_emu/protocol/message.py` | Structs `MS_*` e `LM_*` do Message Server (requisições e respostas). |
| `src/landmass_emu/protocol/channel.py` | Structs `CS_*` (marco 2). |
| `src/landmass_emu/protocol/game.py` | Structs `GS_*` (marco 4). |
| `src/landmass_emu/handlers/message/` | `__init__.py` (roteador `build_router`), `account.py` (100, 110, 120), `channel_list.py` (130). |
| `src/landmass_emu/handlers/channel/` | Lobby, salas, loja, hangar, game server (marcos 2 a 4). |
| `src/landmass_emu/domain/` | `account.py` (conta, token), `channel.py` (canal). Demais entidades nos marcos seguintes. |
| `src/landmass_emu/ports/accounts.py` | Protocol `AccountRepository` e exceção `AccountConflict`. |
| `src/landmass_emu/db/` | `models.py` (`accounts`), `accounts.py` (repositório SQLAlchemy), `engine.py` (migrações no start), `migrations/` (Alembic). |
| `src/landmass_emu/sniffer.py` | Captura de tráfego do cliente (ferramenta de RE). |
| `tests/fixtures/` | Capturas reais usadas como golden files. |

## Concorrência

- Um event loop `asyncio`; uma task por conexão.
- Nenhum IO bloqueante no loop. Banco via drivers async (`aiosqlite`, `asyncpg`, `asyncmy`).
- Estado em memória (canais, salas, online) em serviços de domínio de instância única, acessados só pelo loop.
- A escrita de cada conexão é feita só pela task dela; não há envio concorrente no mesmo socket.
- Leitura de frame com `asyncio.timeout(LANDMASS_RECV_TIMEOUT)`. Heartbeat conta como tráfego.

## Codec

- Cada struct: `@dataclass(frozen=True, slots=True)` com `pack()`/`unpack()` sobre `struct.Struct`. Respostas têm `opcode: ClassVar[int]` e só `pack()`.
- Tabela explícita `opcode → tipo` por serviço. Opcode desconhecido: log com hexdump, conexão mantida.
- Struct novo exige teste de ida e volta; com captura disponível, teste contra o `.bin` real. Respostas sem captura são testadas por offsets explícitos sobre os bytes.

## Handlers

- Assinatura: `async def handler(session: Session, payload: bytes) -> Sequence[Reply]`. O handler não escreve no socket: devolve as respostas e `net/server.py` as envia, com cabeçalho `(reply.opcode << 5) | net_code`.
- Dependências (repositórios, lista de canais) entram por `functools.partial` na montagem do roteador (`handlers/message/__init__.py`).
- Lista vazia = sem resposta: opcode sem handler, pedido antes do login, heartbeat. Nada disso derruba a conexão.
- Um módulo por grupo de opcodes; roteador em tabela explícita (`build_router`), sem descoberta automática.

## Ciclo de uma requisição

```mermaid
sequenceDiagram
  participant N as net/server (task da conexão)
  participant F as framing
  participant P as protocol
  participant R as router
  participant H as handler
  participant Repo as repositório (port)
  N->>F: read_frame()
  F-->>N: body
  N->>P: unpack_header(body)
  P-->>N: (header, payload)
  N->>R: router[opcode]
  R->>H: handler(session, payload)
  H->>P: Tipo.unpack(payload)
  H->>Repo: consulta/grava
  H-->>N: [Reply, ...]
  N->>F: encode_frame(pack_header(reply.opcode) + reply.pack())
```
