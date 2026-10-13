# LandMass Emulator — Software Architecture Document

Status: vivo. Atualize este documento junto com qualquer mudança de arquitetura, protocolo ou decisão.
Detalhes de engenharia reversa (evidências, pseudocódigo) ficam em `re/`; este documento referencia, não duplica.

## 1. Escopo

O sistema substitui os servidores originais do LandMass (Message, Channel, Update, ServerManager) por um único
serviço Python, compatível com o cliente de 2009 em `D:\landmass\cliente`. O alvo é um grupo pequeno de jogadores
(amigos), não um serviço público.

Objetivos:

- Levar o cliente do login até a partida usando apenas o emulador.
- Persistir contas, personagem, inventário, clã e ranking em banco SQL padrão.
- Manter o código testável e modular o suficiente para trocar banco e evoluir o protocolo por opcode.

Fora de escopo:

- Escalabilidade horizontal, balanceamento, múltiplos datacenters.
- Anti-cheat (HShield) e qualquer bypass dele.
- Patch/atualização remota do cliente (FTP do Launcher).

## 2. Restrições

| ID | Restrição |
|----|-----------|
| R1 | O cliente é a fonte da verdade. Quando servidor original e cliente divergirem, implemente o que o cliente espera. |
| R2 | Não use SQL Server, procedures T-SQL nem XP Crypt. Use SQL padrão via ORM; SQLite por padrão; MySQL/PostgreSQL por configuração. |
| R3 | Mantenha tudo dentro de `D:\landmass`: código, ferramentas (`tools/`), cache do uv (`.uv-cache/`), bancos e logs. |
| R4 | Não altere `D:\landmass\LandMass_Setup_20090701.exe`. Alterações no cliente: apenas arquivos novos (ex.: `.bat`) ou com backup. |
| R5 | Python 3.14, gerenciado por `uv`. Sem dependências nativas que exijam compilador. |
| R6 | Versione com git. Nunca rode `git clean`; para descartar mudanças use `git checkout`. |

## 3. Visão de contexto

```
            +-------------------- PC do anfitrião --------------------+
            |                                                          |
 Jogador ---+--> LandMass.exe (cliente) --TCP 7313--> [emulador]       |
            |         |                    --TCP 7314--> [emulador]    |
            |         |                                     |          |
            |         +--UE2 netcode (UDP)--> Game Server Host          |
            |                                (LM_Engine.dll, modo       |
            |                                 servidor) --TCP 7314--+   |
            |                                                       |   |
            |                    [emulador] <-----------------------+   |
            |                        |                                  |
            |                        +--> banco (SQLite/MySQL/Postgres) |
            +----------------------------------------------------------+
```

Componentes:

| Componente | Origem | Papel |
|------------|--------|-------|
| Cliente (`LandMass.exe` + `LM_Engine.dll` + `+server_interface.dll`) | binário original | UI, lobby, partida como cliente UE2 |
| Emulador (`landmass_emu`) | este projeto | Message Server + Channel Server + persistência |
| Game Server Host | **a construir** | processo que carrega `LM_Engine.dll` em modo servidor, chama `InitServer`, registra-se no Channel e hospeda a partida |
| Banco | este projeto | contas e progresso |

O executável host original do game server não existe nos arquivos disponíveis (ver `re/NOTES.md`, seção "Game server").
O cliente sozinho não hospeda partidas autenticadas: o `LOGIN` da partida é validado contra a sala informada pelo Channel.

## 4. Topologia e portas

| Porta | Protocolo | Serviço | `net_code` |
|-------|-----------|---------|-----------:|
| 7313 | TCP | Message Server (login, lista de canais, amigos, clã, ranking) | 13 |
| 7314 | TCP | Channel Server (lobby, salas, loja, hangar, registro de game servers) | 14 |
| 7312 | TCP | Update Server | 12 — **não implementar** (o cliente de 2009 usa FTP no Launcher, que é ignorado) |
| 7310 | TCP | ServerManager (interno entre servidores) | — **não implementar** |
| configurável | UDP | Partida UE2 (Game Server Host) | — |

Rode Message e Channel no mesmo processo e no mesmo event loop.

## 5. Protocolo de fio

Referência completa: `re/NOTES.md`, `re/message_server.md`, `re/channel_server.md`.

- Framing: `u16 LE length` + `body[length]`. `length` não inclui os 2 bytes. Máximo 65000. Sem criptografia.
- Cabeçalho do body: `u16 LE = (opcode << 5) | net_code`. Rejeite `net_code` diferente do esperado pela porta.
- Resposta do servidor: `opcode = opcode_do_pedido + 1`. Mensagens não solicitadas usam opcodes próprios.
- Structs são C/MSVC 7.1, little-endian, alinhamento natural (4 bytes). Ignore bytes de padding: o cliente envia lixo de pilha neles.
- Strings: `char[N]` terminadas em `\0`, codificação cp1252 (cliente brasileiro). Dados variáveis seguem o struct fixo com tamanhos declarados no próprio struct.
- Heartbeat: opcode 2, sem payload, a cada 10 s. Desconecte após `recv_timeout` sem tráfego (padrão: 300 s).

## 6. Autenticação

O cliente converte a linha de comando para minúsculas e, com `login_num` presente, faz login automático por token
(`NetGuidLogin`), sem formulário. O formulário só aparece com `login_num=DEVELOPERGUID`, valor inalcançável após a conversão.

Regras:

- Trate `login_num` (até 32 caracteres, minúsculo) como credencial do jogador.
- Gere tokens aleatórios (`secrets.token_hex(16)`, 32 caracteres) por conta via CLI administrativa.
- Armazene apenas o hash do token (`hashlib.sha256`, comparação com `hmac.compare_digest`). Token é segredo de alta entropia; não use hash lento.
- Gere um `.bat` por jogador com `login_server=<ip>:7313?version=<v>?login_num=<token>`.
- Senha de usuário (fluxo `id`/`pw` do `MS_LOGIN_IN`) fica suportada no codec, mas o fluxo principal é o token.

## 7. Arquitetura do emulador

### 7.1 Camadas

```
transport  -> asyncio streams, framing, sessão por conexão
codec      -> bytes <-> dataclasses por opcode (puro, sem IO)
handlers   -> casos de uso por opcode; recebem mensagem + contexto, devolvem respostas
domain     -> entidades e regras (conta, personagem, sala, canal)
ports      -> Protocols de repositório e serviços (clock, gerador de token)
adapters   -> SQLAlchemy (repositórios), configuração
```

Regras de dependência:

- `codec` e `domain` não importam nada de `transport` nem `adapters`.
- `handlers` dependem de `ports` (Protocols), nunca de SQLAlchemy.
- `adapters` implementam `ports`. A composição acontece em um único ponto (`app.py`).

### 7.2 Estrutura de pacotes

```
src/landmass_emu/
  __main__.py          CLI: serve, sniff, account (create/token/list)
  app.py               composição: settings, engine, repositórios, servidores
  settings.py          pydantic-settings
  net/
    framing.py         leitura/escrita de frames
    session.py         estado por conexão, heartbeat, timeout
    server.py          start_server por serviço, roteamento opcode -> handler
  protocol/
    header.py          pack/unpack (opcode, net_code)
    message.py         structs MS_*_IN / MS_*_OUT
    channel.py         structs CS_*_IN / CS_*_OUT
    game.py            structs GS_*
  handlers/
    message/           login, register, channel_info, ...
    channel/           lobby, room, shop, hangar, game_server
  domain/
  ports/
  db/
    models.py          SQLAlchemy 2 (Mapped/mapped_column)
    repositories.py
    migrations/        Alembic
  sniffer.py           ferramenta de captura (marco 0)
tests/
  fixtures/            capturas reais do cliente (.bin) usadas como golden files
```

### 7.3 Modelo de concorrência

- Use um único event loop `asyncio`. Uma task por conexão.
- Não bloqueie o loop: todo IO de banco passa pelo driver async (`aiosqlite`, `asyncpg`, `asyncmy`).
- Estado compartilhado em memória (canais, salas, jogadores online) vive em serviços de domínio de instância única, acessados só pelo loop.
- Envie respostas pela `Session`, que serializa escritas por conexão.

### 7.4 Codec

- Declare cada struct como `@dataclass(frozen=True, slots=True)` com `pack()`/`unpack()` baseados em `struct.Struct`.
- Uma tabela `OPCODES: dict[int, type[Message]]` por serviço. Opcode desconhecido: registre em log com hexdump e mantenha a conexão.
- Todo struct novo exige teste de ida e volta e, quando houver captura, teste contra o `.bin` real.

### 7.5 Handlers

- Assinatura: `async def handle(msg, ctx: HandlerContext) -> None`, enviando via `ctx.session.send(...)`.
- `HandlerContext` carrega sessão, repositórios (Protocols), serviços de domínio e relógio.
- Um módulo por grupo de opcodes. Registre handlers em tabela explícita, sem descoberta mágica.

## 8. Persistência

- SQLAlchemy 2.x async + Alembic. URL em `LANDMASS_DATABASE_URL`:
  - padrão `sqlite+aiosqlite:///../data/landmass.db`
  - `postgresql+asyncpg://...`
  - `mysql+asyncmy://...`
- Use apenas tipos portáveis (`Integer`, `BigInteger`, `String(n)`, `DateTime(timezone=True)`, `Boolean`, `LargeBinary`). Sem SQL específico de fornecedor.
- Derive o schema de `D:\landmass\servidor\db\LM_account.sql` (última migration, UTF-16, MSSQL), mantendo nomes de tabela e colunas (`tbl_account`, `tbl_item`, `tbl_morats`, `tbl_quickslot`, `tbl_clan`, ...). Modele apenas as tabelas exigidas pelo marco em curso.
- Reimplemente a lógica das procedures (`GameLogin`, `SaveQuickSlot`, `LoadAllQuickSlot`, ...) em Python, nos repositórios ou serviços de domínio.
- Dados estáticos do jogo (itens, mapas, níveis) vêm de `cliente\system\landmass.wdb` (SQLite). Leia-os em modo somente leitura e nunca os copie para o banco de contas.

## 9. Configuração

- `pydantic-settings`, prefixo `LANDMASS_`, arquivo `.env` opcional na raiz do projeto.
- Chaves mínimas: `DATABASE_URL`, `BIND_HOST`, `PUBLIC_HOST` (IP anunciado aos clientes), `MESSAGE_PORT`, `CHANNEL_PORT`, `SERVER_NAME`, `CLIENT_VERSION`, `RECV_TIMEOUT`.
- Não grave segredos no repositório.

## 10. Execução do cliente

- Use `cliente\system\jogar_local.bat` (desenvolvimento) ou o `.bat` gerado por jogador.
- Parâmetros obrigatórios: `version=` e `login_num=` (sem eles o `LandMass.exe` encerra). `login_server=ip:porta` sobrepõe o endereço do Message Server.
- Modo janela/minimizado para testes automatizados: ver `re/windowed.md` (em investigação).

## 11. Game Server Host

Requisito: reproduzir o executável ausente que hospeda partidas.

- Carregar `LM_Engine.dll` (x86) e dependências UE2 em processo 32-bit.
- Chamar `appInit` com a linha de comando e `InitServer("ip=.. port=.. mode=.. ch_ip=.. ch_port=.. ch_code=.. ch_pw=..")`.
- Executar o laço: `UGameEngine::Tick` + `ChannelServerTick`; encerrar com `ExitServer`.
- Alternativa a avaliar: `LandMass.exe SERVER` com `INI=` próprio definindo `GameEngine=LM_Engine.ServerEngine`, e um shim que chame `InitServer`.
- O Channel do emulador deve implementar o lado servidor das mensagens `GS_*` (registro do game server, `GS_IN_PLAYER`, `GS_OUT_PLAYER`).

Decida a abordagem com base em `re/channel_server.md` antes do marco 4.

## 12. Estratégia de testes

| Nível | O que cobre | Ferramenta |
|-------|-------------|-----------|
| Unidade | codec (ida e volta, golden files), regras de domínio | pytest |
| Handler | handler + repositórios em memória | pytest-asyncio |
| Integração | servidor real em porta efêmera + cliente de teste Python que fala o protocolo | pytest-asyncio |
| Aceitação | cliente real (`LandMass.exe`) contra o emulador, conferindo `LandMass.log` | script de automação (marco a marco) |

- Converta toda captura relevante de `captures/` em fixture em `tests/fixtures/` com nome descritivo.
- Gates obrigatórios antes de commit: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src`, `uv run pytest`.

## 13. Engenharia reversa: ferramentas e artefatos

- REA (MCP `rea`) + Ghidra 12.1.4 + JDK 21 em `D:\landmass\tools`. O REA mantém um binário ativo por vez: não paralelize análises que troquem de alvo.
- Fontes primárias, em ordem de confiança: comportamento do cliente (capturas, `LandMass.log`) > código do cliente (`+server_interface.dll`, `LM_Engine.dll`, UnrealScript embutido nos `.u`) > servidores de 2006-07 (`ChannelServer.map`, `.ilk`).
- Registre cada achado em `re/` com evidência (binário, endereço, função ou linha de script). Marque inferências como tal.

## 14. Marcos

| # | Entrega | Critério de aceite |
|---|---------|--------------------|
| 0 | Esqueleto, sniffer, framing | Captura do handshake real (feito) |
| 1 | Message Server: login por token, lista de canais | Cliente chega à tela de seleção de canal |
| 2 | Channel: entrada, lobby, chat, lista de salas | Dois clientes se veem no lobby |
| 3 | Salas: criar, entrar, slots, pronto | Dois clientes na mesma sala com "pronto" |
| 4 | Game Server Host + `GS_*` | Partida inicia e termina; resultado volta ao Channel |
| 5 | Persistência de progresso: itens, loja, quickslot, morats, clã, ranking | Estado sobrevive a reinício do servidor |

## 15. Decisões

| ID | Decisão | Motivo |
|----|---------|--------|
| D1 | Um processo, `asyncio` puro, sem framework de rede | Poucos jogadores; menos dependências; controle total do framing |
| D2 | SQLAlchemy 2 async + Alembic | Portabilidade SQLite → MySQL/Postgres sem reescrever consultas |
| D3 | Login por token em `login_num` | O cliente força login automático; formulário inalcançável |
| D4 | Não implementar Update (7312) nem ServerManager (7310) | Cliente de 2009 não depende deles; topologia simplificada |
| D5 | Codec separado de handlers | Testar protocolo sem rede e sem banco |

## 16. Riscos e questões em aberto

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Executável do game server ausente | Sem partida | Construir Game Server Host (seção 11); avaliar viabilidade cedo no marco 3 |
| Divergência entre structs do servidor de 2007 e do cliente de 2009 | Pacotes mal interpretados | Usar sempre o cliente como referência (R1) e validar com capturas |
| HShield bloquear execução fora do Launcher ou em modo servidor | Cliente/host não iniciam | Testar cedo; documentar comportamento |
| Render D3D minimizado | Testes automatizados falham | Usar janela pequena fora de foco; ver `re/windowed.md` |
| NAT/firewall dos amigos | Conexão externa falha | Anunciar `PUBLIC_HOST`; documentar portas a abrir |
