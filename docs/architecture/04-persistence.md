# Persistência

## Banco de contas

- SQLAlchemy 2.x async + Alembic. URL em `LANDMASS_DATABASE_URL` (ver [05-configuration.md](05-configuration.md)).
- `app.game_servers` abre um único engine e o compartilha entre Message e Channel.

| Banco | URL de exemplo | Driver |
|-------|----------------|--------|
| SQLite (padrão) | `sqlite+aiosqlite:///data/landmass.db` | `aiosqlite` |
| PostgreSQL | `postgresql+asyncpg://user:pw@host/landmass` | `asyncpg` |
| MySQL/MariaDB | `mysql+asyncmy://user:pw@host/landmass` | `asyncmy` |

- Use só tipos portáveis: `Integer`, `BigInteger`, `String(n)`, `Boolean`, `DateTime(timezone=True)`, `LargeBinary`.
- Proibido SQL específico de fornecedor, procedures, triggers e extensões.
- Toda mudança de schema passa por migração Alembic; nunca altere o banco à mão.
- As migrações rodam no start de `serve` e de `account` (`db/engine.py: migrate`), até `head`.
- Nova migração: `uv run alembic revision -m "descrição"` (usa `alembic.ini` na raiz) e edite o arquivo em `src/landmass_emu/db/migrations/versions/`.

## Convenção de nomes

Vale para todas as tabelas e colunas, presentes e futuras (convenção Laravel, [D11](../decisions/README.md)):

- Tabelas: `snake_case`, plural, em inglês (`accounts`, `characters`, `items`, `clans`, `clan_members`, `friends`). Sem prefixo `tbl_`, que o legado usa em todas as tabelas e não agrega nada.
- Prefixo de grupo: se a fonte agrupar tabelas por domínio (ex.: `map_spawns`), mantenha o prefixo e aplique o resto da convenção ao nome.
- Tabela pivô: nomes singulares em ordem alfabética, unidos por `_` (`account_item`).
- Chave primária: `id`, inteiro autoincremento.
- Chave estrangeira: `<singular>_id` (`account_id`).
- Colunas: `snake_case` em inglês.
- Timestamps: `created_at` e `updated_at` (`DateTime(timezone=True)`); `updated_at` é gravado em todo update.
- Booleanos: prefixo `is_` ou `has_` quando fizer sentido.
- Índices e constraints: `<tabela>_<coluna>_unique`, `<tabela>_<coluna>_index`, `<tabela>_<coluna>_foreign` (ex.: `accounts_username_unique`, `accounts_account_id_foreign`).

## Tabela `accounts` (marco 1)

Fonte: `D:\landmass\servidor\db\LM_account.sql`. Modelo: `db/models.py`. Migração: `db/migrations/versions/d511fd6ac388_create_accounts_table.py`.

| Coluna | Tipo | Original (`tbl_account`) | Uso |
|--------|------|--------------------------|-----|
| `id` | `Integer` PK, autoincremento | `account_code int` | Id da conta. |
| `username` | `String(12)`, único | `userid char(12)` | Login (`account create --user`). |
| `nickname` | `String(16)`, único | `nick nvarchar(10)` | Nickname exibido (121). Tamanho 16 segue o protocolo, não o original. |
| `token_hash` | `String(64)`, único | — (novo) | `sha256` hex do token (ver [../protocol/authentication.md](../protocol/authentication.md)). |
| `created_at` | `DateTime(timezone=True)` | `create_date smalldatetime` | Criação. |
| `updated_at` | `DateTime(timezone=True)` | — (novo) | Última alteração; muda na rotação do token. |

- `username` não é FK para `users`: é o próprio login da conta.
- Único em `nickname`: regra de nickname do jogo (`CheckNickname`, 140, responde "nome disponível").
- Único em `token_hash`: é a chave de busca do login.
- Colunas de progressão (F2 e F3): `tutorial_clear`, `total_exp`, `ld` e `cash`, todas `Integer NOT NULL` com padrão `0`. Migrações `01ad613f288a` e `31c91374dcba`. Regras em [07-progression §4.3](07-progression.md). Colunas de morat regular (F5): `regular_nest_id` e `regular_morat_class`, migração `ff38814bc227`. Tabelas `account_items` (migração `0d72e556d5d3`) e `account_morats` (migração `2100454de3ec`), com regras em [07-progression §4.4 e §4.5](07-progression.md).
- As demais colunas do original (estatísticas, opções, quickslot, morats) entram nos marcos que as usam.

## Tabela `account_options` (F1)

Fonte: [07-progression.md §4.6](07-progression.md). Modelo: `db/models.py` (`OptionsRow`). Migração: `db/migrations/versions/c654f8b37cd7_create_account_options_table.py`.

| Coluna | Tipo | Nulo | Padrão | Uso |
|--------|------|------|--------|-----|
| `id` | `Integer` PK, autoincremento | não | — | Id da linha. |
| `account_id` | `Integer`, único | não | — | FK `accounts.id`. Uma linha por conta. |
| 37 colunas de opção | `Integer` | não | `0` | Uma por campo de `LmRegisterInfo`, com os nomes de 07 §4.6. A ordem é o layout do 111 e do 544 (`re/message_server.md` §4.1). |
| `created_at`, `updated_at` | `DateTime(timezone=True)` | não | — | Criação e última gravação. |

- Constraints: `account_options_account_id_foreign` (FK) e `account_options_account_id_unique`.
- Upsert portável: leitura e depois insert ou update, sob `asyncio.Lock` do repositório. Sem `ON CONFLICT`, que é específico de fornecedor.
- Conta sem linha: o repositório devolve zeros. A linha nasce no primeiro 544.

## Tabelas `friends` e `blocks` (F12)

Fonte: [07-progression.md §4.7](07-progression.md). Modelos: `db/models.py` (`FriendRow`, `BlockRow`). Migração: `db/migrations/versions/ce9926b0fcad_create_friends_and_blocks_tables.py`, sobre `31c91374dcba`.

| Coluna | Tipo | Nulo | Padrão | Uso |
|--------|------|------|--------|-----|
| `id` | `Integer` PK, autoincremento | não | — | Id da linha. |
| `account_id` | `Integer` | não | — | FK `accounts.id`: dono da lista. |
| `friend_account_id` (`friends`) ou `blocked_account_id` (`blocks`) | `Integer` | não | — | FK `accounts.id`: o alvo. |
| `created_at`, `updated_at` | `DateTime(timezone=True)` | não | — | Criação e última gravação. |

- Constraints em `friends`: `friends_account_id_foreign`, `friends_friend_account_id_foreign`, único `friends_account_id_friend_account_id_unique` e índice `friends_friend_account_id_index`. `blocks` segue o mesmo padrão com `blocked_account_id`.
- Relação dirigida: A ter B como amigo não faz B ter A. Amizade e bloqueio são tabelas separadas.
- Sem log: só o par e as datas (D12). Remoção apaga a linha.
- Adição repetida: a violação do único vira `False` (idempotente). Remoção: lê a linha e apaga.

## Repositório

- Contrato: `ports/accounts.py` (`AccountRepository`, Protocol). Handlers e CLI dependem só dele.
- Implementação: `db/accounts.py` (`SqlAccountRepository`). Violação de unicidade vira `AccountConflict`.
- Opções: `ports/options.py` (`OptionsRepository`) e `db/options.py` (`SqlOptionsRepository`). O Message lê no 111; o Channel grava no 544.
- Progressão: `ports/progression.py` (`ProgressionRepository`) e `db/progression.py` (`SqlProgressionRepository`). O tutorial é um `UPDATE` com OR no banco (`bitwise_or`), sem leitura antes da escrita. O grant soma no próprio `UPDATE`.
- Leitura do `landmass.wdb`: `db/catalog.py` (`WdbCatalog`), somente leitura, `mode=ro`, textos em cp1252.

## Origem do schema

- Fonte: `D:\landmass\servidor\db\LM_account.sql` (última migration, MSSQL, UTF-16).
- Os nomes seguem a convenção acima. O legado (`tbl_*`) serve de referência: a tabela de cada marco mostra a coluna original quando isso ajuda a conferência.
- Modele apenas as tabelas exigidas pelo marco em curso ([../roadmap.md](../roadmap.md)).
- Reimplemente a lógica das procedures (`GameLogin`, `SaveQuickSlot`, `LoadAllQuickSlot`, `SaveOption`, ...) em Python, em repositórios ou serviços de domínio.
- Substitua XP Crypt por hashing na aplicação ([../protocol/authentication.md](../protocol/authentication.md)).

## Tabelas do legado não migradas

| Tabela original | Substituto |
|-----------------|-----------|
| `tbl_loginlog`, `tbl_clanlog` | Log estruturado da aplicação: `logging` do Python em JSON lines, com rotação, em `data/logs/`. Sem tabela. |
| `tbl_logincount`, `tbl_usercount`, `tbl_group_usercount`, `tbl_concurrent`, `tbl_date_member` | Métricas calculadas sob demanda (consulta ou contadores em memória). Sem tabela. |
| `tbl_account_del`, `tbl_item_del`, `tbl_friends_del`, `tbl_morats_del`, `tbl_nickname_del` | Coluna `deleted_at` (soft delete) na própria tabela, só onde houver necessidade real; caso contrário, `DELETE`. |
| `tbl_index` (gerador de IDs) | Autoincremento `id`. |
| `tbl_login` (presença online) | Estado em memória da sessão. |
| `tbl_temp_user`, `tbl_tool_patch` | Não migradas (sem uso no cliente). |

## Dados estáticos do jogo

- Fonte: `D:\landmass\cliente\system\landmass.wdb` (SQLite comum).
- Tabelas relevantes: `item`, `Item_Equip`, `maps`, `LevelList`, `Morats`, `supply`, `gift`, `msg_error`, `message_server`.
- Abra em modo somente leitura (`file:...?mode=ro`). Não copie para o banco de contas; o cliente é a fonte desses dados (R1).
- Os demais `.wdb` (magic `f7 db 00 00 72 f3 31 01`) usam formato proprietário `Cdb_table`; decodifique só se necessário.
