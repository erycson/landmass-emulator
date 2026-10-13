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

## Tabela `tbl_account` (marco 1)

Fonte: `D:\landmass\servidor\db\LM_account.sql`. Modelo: `db/models.py`. Migração: `db/migrations/versions/7b3f0c2e9a41_tbl_account.py`.

| Coluna | Tipo | Original (`tbl_account`) | Uso |
|--------|------|--------------------------|-----|
| `account_code` | `Integer` PK, autoincrement | `account_code int` | Id da conta. |
| `userid` | `String(12)`, único | `userid char(12)` | Login (`account create --user`). |
| `nick` | `String(16)`, único | `nick nvarchar(10)` | Nickname exibido (121). Tamanho 16 segue o protocolo, não o original. |
| `token_hash` | `String(64)`, único | — (novo) | `sha256` hex do token (ver [../protocol/authentication.md](../protocol/authentication.md)). |
| `create_date` | `DateTime(timezone=True)` | `create_date smalldatetime` | Criação. |

- Único em `nick`: regra de nickname do jogo (`CheckNickname`, 140, responde "nome disponível").
- Único em `token_hash`: é a chave de busca do login.
- As demais colunas do original (estatísticas, opções, quickslot, morats) entram nos marcos que as usam.

## Repositório

- Contrato: `ports/accounts.py` (`AccountRepository`, Protocol). Handlers e CLI dependem só dele.
- Implementação: `db/accounts.py` (`SqlAccountRepository`). Violação de unicidade vira `AccountConflict`.

## Origem do schema

- Fonte: `D:\landmass\servidor\db\LM_account.sql` (última migration, MSSQL, UTF-16).
- Mantenha nomes de tabela e coluna originais (`tbl_account`, `tbl_item`, `tbl_morats`, `tbl_quickslot`, `tbl_clan`, ...) para facilitar a conferência com o código original.
- Modele apenas as tabelas exigidas pelo marco em curso ([../roadmap.md](../roadmap.md)).
- Reimplemente a lógica das procedures (`GameLogin`, `SaveQuickSlot`, `LoadAllQuickSlot`, `SaveOption`, ...) em Python, em repositórios ou serviços de domínio.
- Substitua XP Crypt por hashing na aplicação ([../protocol/authentication.md](../protocol/authentication.md)).

## Dados estáticos do jogo

- Fonte: `D:\landmass\cliente\system\landmass.wdb` (SQLite comum).
- Tabelas relevantes: `item`, `Item_Equip`, `maps`, `LevelList`, `Morats`, `supply`, `gift`, `msg_error`, `message_server`.
- Abra em modo somente leitura (`file:...?mode=ro`). Não copie para o banco de contas; o cliente é a fonte desses dados (R1).
- Os demais `.wdb` (magic `f7 db 00 00 72 f3 31 01`) usam formato proprietário `Cdb_table`; decodifique só se necessário.
