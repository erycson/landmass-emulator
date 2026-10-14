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
| `banned_until` | `DateTime(timezone=True)`, nulo | — (novo) | Fim do bloqueio administrativo (D106; migração `9e4c2b7a1d05`). Nulo ou no passado: login liberado. |
| `access_level` | `Integer` NOT NULL, padrão 0 | — (novo) | Nível de acesso GM (`ucAccess` do cliente; D193; migração `7a2d9c4e1b35`). 9 ou mais: comandos de GM no canal; 10 ou mais: some da lista de jogadores de quem tem menos de 10. Gravado pela CLI (`account access`). |

- `username` não é FK para `users`: é o próprio login da conta.
- Único em `nickname`: regra de nickname do jogo (`CheckNickname`, 140, responde "nome disponível").
- Único em `token_hash`: é a chave de busca do login.
- Colunas de progressão (F2 e F3): `tutorial_clear`, `total_exp`, `ld` e `cash`, todas `Integer NOT NULL` com padrão `0`. Migrações `01ad613f288a` e `31c91374dcba`. Regras em [07-progression §4.3](07-progression.md). Colunas de morat regular (F5): `regular_nest_id` e `regular_morat_class`, migração `ff38814bc227`. Tabelas `account_items` (migração `0d72e556d5d3`, com as colunas de montagem `account_morat_id`, `slot_name` e `system_slot`) e `account_morats` (migração `2100454de3ec`), com regras em [07-progression §4.4 e §4.5](07-progression.md).
- As estatísticas do original não são colunas de `accounts`: a ficha as calcula de `match_players` (D107). O quickslot é a tabela `account_quick_slots` (D73, seção abaixo).
- Gates (F10): `gate_count`, `Integer` NOT NULL com padrão 4, na migração `a3d9e6f1c402` (junto com `gifts`). Regra em [07-progression R-GATE-01](07-progression.md).


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

## Tabela `account_quick_slots` (F6 e F7, D73)

Fonte: [07-progression](07-progression.md) (tabela de legado `tbl_quickslot`, D73). Modelo: `db/models.py` (`AccountQuickSlotRow`). Migração: `db/migrations/versions/4b7e1d2a9c60_create_account_quick_slots_table.py`.

| Coluna | Tipo | Nulo | Padrão | Uso |
|--------|------|------|--------|-----|
| `id` | `Integer` PK, autoincremento | não | — | Id da linha. |
| `account_id` | `Integer` | não | — | FK `accounts.id`. |
| `slot_index` | `Integer` | não | — | Slot de 0 a 4. |
| `enabled` | `Integer` | não | `0` | 1 = atalho ligado. |
| `memo` | `String(8)` | não | `""` | Texto do atalho. |
| `gate_index` | `Integer` | não | — | Gate do atalho; -1 = sem gate. |
| `created_at`, `updated_at` | `DateTime(timezone=True)` | não | — | Criação e última gravação. |

- Constraints: `account_quick_slots_account_id_foreign` (FK) e `account_quick_slots_account_id_slot_index_unique`.
- Semeadura: `DEFAULT_QUICK_SLOTS` (`domain/quick_slots.py`) grava as cinco linhas padrão: slots 0 e 1 ligados (gates 0 e 1), 2 e 3 desligados (gates 2 e 3), 4 desligado sem gate. Acontece na criação da conta e em `account kit apply`. Repetir não duplica (índice único).
- O cliente não tem opcode para ler ou gravar atalhos (`re/features.md` §4): nenhum pacote do protocolo lê a tabela.

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

## Tabelas `clans` e `clan_members` (F13)

Fonte: [07-progression.md §4.8](07-progression.md). Modelos: `db/models.py` (`ClanRow`, `ClanMemberRow`). Migração: `db/migrations/versions/3f8a1c0d9e27_create_clans_and_clan_members_tables.py`, sobre `ce9926b0fcad`.

- `clans`: `id`, `name` (`String(16)`, único `clans_name_unique`), `master_account_id` (FK `clans_master_account_id_foreign`), `mark` (`Integer`, padrão 0), `created_at`, `updated_at`.
- `clan_members`: `id`, `clan_id` (FK `clan_members_clan_id_foreign`, índice `clan_members_clan_id_index`), `account_id` (FK `clan_members_account_id_foreign`, único `clan_members_account_id_unique`), `grade` (`Integer`, padrão 0), `created_at`, `updated_at`.
- Uma conta, um clã (D60). O mestre entra como membro de grau 0 (D61).
- Apagar o clã remove os membros e depois o clã, numa transação (D59). Sair apaga a linha do membro.

## Tabela `gifts` (F10)

Migração `a3d9e6f1c402` (sobre `a3c7e915d2b4`). Modelo `GiftRow` em `db/models.py`. Colunas, chaves e regras em [07-progression §4.9](07-progression.md). Sem tabela de log: envio, resgate e gacha vão ao log de economia (D99, D120).

## Tabela `shop_items` (venda da loja, D191)

Migração `e8b4d1f6a237` (sobre `5c1e8a3f7b92`). Modelo `ShopItemRow` em `db/models.py`. Uma linha por id do catálogo à venda, com `enabled` e preço por nível (0 a 3) em LD e Cash. Colunas e regras em [07-progression §4.11](07-progression.md). Preenchida por `landmass-emu shop sync` a partir do wdb; sem tabela de log (o log de economia tem o `catalog_id` e o `tier` de cada compra).

## Repositório

- Contrato: `ports/accounts.py` (`AccountRepository`, Protocol). Handlers e CLI dependem só dele.
- Implementação: `db/accounts.py` (`SqlAccountRepository`). Violação de unicidade vira `AccountConflict`.
- Opções: `ports/options.py` (`OptionsRepository`) e `db/options.py` (`SqlOptionsRepository`). O Message lê no 111; o Channel grava no 544.
- Progressão: `ports/progression.py` (`ProgressionRepository`) e `db/progression.py` (`SqlProgressionRepository`). O tutorial é um `UPDATE` com OR no banco (`bitwise_or`), sem leitura antes da escrita. O grant soma no próprio `UPDATE`.
- Clãs: `ports/clans.py` (`ClanRepository`) e `db/clans.py` (`SqlClanRepository`). Violação de unicidade vira `ClanConflict`.
- Ranking: `ports/ranking.py` (`RankingRepository`) e `db/ranking.py` (`SqlRankingRepository`), uma consulta sobre `accounts` sem tabela (D18).
- Presentes: `ports/gifts.py` (`GiftRepository`) e `db/gifts.py` (`SqlGiftRepository`). O envio debita pelo `debit` de `db/shop.py` na mesma transação que cria a linha; o resgate (612, e o 610 pelo D100) grava a unidade e marca `claimed_at` juntos.
- Loja: `ports/shop.py` (`ShopItemRepository`, com `ShopItem`) e `db/shop.py` (`SqlShopItemRepository`). A compra lê a venda por id; a CLI `shop` grava. O `ShopItem` não tem tipo de `domain/`, então não há ciclo de importação.
- Uso de item especial (560): `ports/use.py` (`UseRepository`) e `db/use.py` (`SqlUseRepository`). Consumo, crédito de LD, prêmios e contagem de gates numa transação.
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

## Histórico de partidas

- Porta: `ports/matches.py` (`MatchRepository.save`). Implementação: `db/matches.py` (`SqlMatchRepository`), que grava a partida e os jogadores numa transação e devolve o id de `matches`.
- Dados em memória: `domain/match_stats.py` (`MatchRecord`, `PlayerMatchStats`), sem IO.
- Modelos: `db/models.py` (`MatchRow`, `MatchPlayerRow`). Migração: `db/migrations/versions/887ad86230f6_create_matches_and_match_players_tables.py`. Colunas `uuid` e `played_seconds`: `db/migrations/versions/5c1e8a3f7b92_add_uuid_and_played_seconds_to_matches.py`.
- Constraints: `match_players_match_id_foreign` (FK) e `match_players_match_id_account_id_unique` (um jogador por partida).
- Gravação: uma vez, no fim da partida, com `end_reason` (D48, D52). Não há tabela de eventos nem registro durante a partida.
- Gravado: identidade, sala, `uuid` (D152), tempo jogado do canal e, quando o log traz o bloco `GameEnded`, kills, colocação, exp e LD (D153, D154). Sem o bloco, essas métricas ficam `NULL`. A ficha (D107) lê essas colunas.
- Contrato de resultado (D105): jogos, vitórias e derrotas contam só partidas com `won` não nulo em alguma linha. Quem não tem `won` nessa partida conta como jogo sem vitória nem derrota. No DM, o log não traz `Winner` (ver a disponibilidade abaixo).

Tabela `matches` (uma linha por partida):

| Coluna | Tipo | Nulo | Uso |
|--------|------|------|-----|
| `id` | `Integer` PK, autoincremento | não | Id da partida. |
| `room_id` | `Integer` | não | Sala onde a partida rodou. |
| `map_record_id` | `Integer` | não | Id do registro do mapa. |
| `map_file` | `String(64)` | não | Arquivo do mapa. |
| `game_mode` | `Integer` | não | Modo de jogo. |
| `game_class` | `String(64)` | não | Classe do jogo (ex.: `LM_DeathMatch`). |
| `team_count` | `Integer` | não | Número de times. |
| `max_players` | `Integer` | não | Máximo de jogadores (`MaxPlayers` do log). |
| `time_limit` | `Integer` | não | Tempo limite da partida. |
| `goal_score` | `Integer` | não | Pontuação para vencer (`GoalScore` da URL). |
| `started_at`, `ended_at` | `DateTime(timezone=True)` | não | Início e fim da partida. |
| `end_reason` | `String(32)` | não | Motivo do fim: `exit_play` (todos saíram ou o último em jogo saiu), `return_to_room` (o último em jogo voltou à sala, D150) ou `server_exit` (processo caiu depois de pronto), D48. |
| `uuid` | `String(36)` | sim | Identificador da partida, único (`matches_uuid_unique`). Partidas anteriores à migração `5c1e8a3f7b92` ficam sem uuid (D152). |
| `created_at`, `updated_at` | `DateTime(timezone=True)` | não | Criação e última gravação. |

Tabela `match_players` (uma linha por jogador por partida):

| Coluna | Tipo | Nulo | Uso |
|--------|------|------|-----|
| `id` | `Integer` PK, autoincremento | não | Id da linha. |
| `match_id` | `Integer`, FK `matches.id` | não | Partida. |
| `account_id` | `Integer` | não | Conta do jogador. Único por partida. |
| `nickname` | `String(16)` | não | Nickname na partida. |
| `slot` | `Integer` | não | Posição do jogador na sala. |
| `team` | `Integer` | sim | Time; nulo quando o modo não define time. |
| `is_master` | `Boolean` | não | Se era o mestre da sala. |
| `kills`, `deaths`, `assists`, `ranking`, `headshots`, `bullets`, `hits`, `damage`, `exp`, `money` | `Integer` | sim | Métricas da partida; disponibilidade na tabela abaixo. |
| `played_percent` | `Float` | sim | Percentual do tempo jogado, de 0 a 100, derivado do canal (D152). |
| `played_seconds` | `Integer` | sim | Tempo jogado em segundos: do início até a saída da partida ou o fim. Vem do canal (D152). |
| `won` | `Boolean` | sim | Vitória; disponibilidade na tabela abaixo. |
| `created_at`, `updated_at` | `DateTime(timezone=True)` | não | Criação e última gravação. |

Recompensa (R-REW-10, D155): na mesma transação da gravação, `accounts.total_exp` e `accounts.ld` somam o exp e o LD de cada jogador que os tem.

Disponibilidade das métricas: o que o jogo produz, segundo o RE do `XGame` e o bloco `GameEnded`. O emulador lê o bloco ao fim da partida (D153, D154); sem o bloco, as métricas ficam `NULL`.

| Métrica | O que o jogo produz | Situação |
|---------|---------------------|----------|
| `kills` | `Kills`, por jogador, nos blocos de DM e de OP/time. | Lido do bloco `GameEnded` quando ele sai (D154). |
| `ranking` | `Ranking`, no bloco de DM. | Lido do bloco `GameEnded` quando ele sai (D154). |
| `played_percent` | Não vem do bloco: o `Played` do log não é usado. | Derivado do canal (`with_played`, D152). |
| `exp`, `money` | Exp e LD ganhos, por jogador, no bloco de DM. | Lido do bloco `GameEnded` quando ele sai (D154). |
| `won` | `Winner`, no bloco de OP/time. Não há no DM, e a semântica (time ou jogador) não foi confirmada. | Parcial; não coletado. |
| `deaths` | `PRI.Deaths` é incrementado em `Killed()`, mas não entra no bloco. | Não produzido: fica `NULL`. |
| `assists` | Só `m_iAssistScore` (critical frag de time). Não é assistência de CS. | Não existe: fica `NULL`. |
| `headshots` | O tipo de dano `DamageTypeHeadShot` existe; nenhum contador por partida é logado. | Não produzido: fica `NULL`. |
| `bullets`, `hits`, `damage` | Sem fonte no código extraído. | Sem fonte: fica `NULL`. |

Métrica sem fonte fica `NULL`; nenhum valor é estimado.
