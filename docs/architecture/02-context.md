# Contexto e topologia

## Componentes

```mermaid
flowchart LR
  subgraph Jogador
    C[LandMass.exe<br/>cliente UE2]
  end
  subgraph Anfitrião
    E[Emulador landmass_emu<br/>Message + Channel]
    G[Game Server Host<br/>LM_Engine.dll modo servidor]
    DB[(Banco<br/>SQLite / MySQL / Postgres)]
    W[(landmass.wdb<br/>dados estáticos do cliente)]
  end
  C -- TCP 7313 --> E
  C -- TCP 7314 --> E
  C -- UE2 netcode UDP --> G
  G -- TCP 7314 GS_* --> E
  E --> DB
  E -. leitura .-> W
```

| Componente | Origem | Papel |
|------------|--------|-------|
| Cliente (`LandMass.exe`, `LM_Engine.dll`, `+server_interface.dll`) | binário original | UI, lobby, partida como cliente UE2 |
| Emulador (`landmass_emu`) | este projeto | Message Server, Channel Server, persistência |
| Game Server Host | **a construir** — ver [06-game-server-host.md](06-game-server-host.md) | Hospeda a partida e valida jogadores contra a sala do Channel |
| Banco de contas | este projeto | Contas e progresso — ver [04-persistence.md](04-persistence.md) |
| `landmass.wdb` | cliente | Itens, mapas, níveis (SQLite somente leitura) |

## Portas

| Porta | Protocolo | Serviço | `net_code` | Implementar |
|-------|-----------|---------|-----------:|:-----------:|
| 7313 | TCP | Message Server: login, canais, amigos, clã, ranking | 13 | sim |
| 7314 | TCP | Channel Server: lobby, salas, loja, hangar, game servers | 14 | sim |
| 7312 | TCP | Update Server | 12 | não — o Launcher de 2009 usa FTP e é ignorado |
| 7310 | TCP | ServerManager (interno entre servidores) | 10 | não |
| configurável | UDP | Partida UE2 (Game Server Host) | — | via host |

Execute Message e Channel no mesmo processo e no mesmo event loop.

## Fluxo ponta a ponta

```mermaid
sequenceDiagram
  participant C as Cliente
  participant M as Message (7313)
  participant Ch as Channel (7314)
  participant G as Game Server Host
  C->>M: Login (100) com login_num
  M-->>C: 101 resultado do login
  C->>M: Register / InMessageServer (110/120)
  M-->>C: 111 / 121
  C->>M: GetChannelServerInfo (130)
  M-->>C: 131 lista de canais
  C->>Ch: entrar no channel server
  Ch-->>C: 101 / 111 / 103 ... lobby
  C->>Ch: criar/entrar sala, pronto
  Ch->>G: GS_IN_PLAYER (sala, time, key)
  Ch-->>C: endereço do game server
  C->>G: UE2 LOGIN URL ?name ?team ?key
  G->>G: LoginPlayer valida contra a sala
  G->>Ch: GS_OUT_PLAYER / resultado
```

Opcodes detalhados em [../protocol/](../protocol/wire-format.md).
