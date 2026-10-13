# Persistência

## Banco de contas

- SQLAlchemy 2.x async + Alembic. URL em `LANDMASS_DATABASE_URL` (ver [05-configuration.md](05-configuration.md)).

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
- As demais colunas do original (estatísticas, opções, quickslot, morats) entram nos marcos que as usam.

## Repositório

- Contrato: `ports/accounts.py` (`AccountRepository`, Protocol). Handlers e CLI dependem só dele.
- Implementação: `db/accounts.py` (`SqlAccountRepository`). Violação de unicidade vira `AccountConflict`.

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
