# Configuração

Carregue com `pydantic-settings` (`settings.py`), prefixo `LANDMASS_`. Precedência, da maior para a menor (D200):

1. Argumentos da linha de comando (`--config`).
2. Variáveis de ambiente, e `.env` no diretório de execução (conta como ambiente).
3. `LANDMASS_<CAMPO>_FILE`: o valor vem do arquivo. Com a variável e o `_FILE` juntos, é erro.
4. Arquivo TOML: `landmass-emu serve --config <arquivo>` ou `LANDMASS_CONFIG`. Chaves são os nomes dos campos sem o prefixo (`message_port = 7313`). Chave desconhecida e arquivo inexistente são erro. Modelo com todas as chaves: [`config.example.toml`](../../config.example.toml).
5. Padrão do código (tabela abaixo).

Segredos com `_FILE` (o valor vem de um arquivo): `LANDMASS_DATABASE_URL_FILE` e `LANDMASS_MATCH_LOGIN_NUM_FILE`. O fim de linha do arquivo sai; o resto fica como está. Um arquivo ilegível é erro que nomeia a variável. Produção: [`operations/production.md`](../operations/production.md).

| Variável | Padrão | Uso | Marco |
|----------|--------|-----|:-----:|
| `LANDMASS_DATABASE_URL` | `sqlite+aiosqlite:///data/landmass.db` | Banco de contas. Caminho relativo ao diretório de execução (raiz de `emulador\`). | 1 |
| `LANDMASS_BIND_HOST` | `0.0.0.0` | Interface de escuta dos dois serviços (Message e Channel). | 1 |
| `LANDMASS_PUBLIC_HOST` | `127.0.0.1` | IP anunciado aos clientes na lista de canais. Máximo 15 caracteres (campo `service_address`). | 1 |
| `LANDMASS_MESSAGE_PORT` | `7313` | Porta do Message Server. Também usada no `.bat` gerado. | 1 |
| `LANDMASS_CHANNEL_PORT` | `7314` | Porta de escuta do Channel Server e porta anunciada aos canais (`service_port`). | 1, 2 |
| `LANDMASS_CLIENT_VERSION` | `1245776779` | Versão em `version=` do `.bat` gerado. | 1 |
| `LANDMASS_CLIENT_DIR` | `../cliente/system` | Pasta onde `account create/token` grava `jogar_<user>.bat`. `account grant`, `account create`, `account item add`, `account morat add` e `account kit apply` e `shop sync` leem dela o `landmass.wdb` (catálogo, somente leitura). | 1 |
| `LANDMASS_RECV_TIMEOUT` | `300` | Segundos sem tráfego antes de desconectar, em Message e Channel. Mínimo `60`. | 1, 2 |
| `LANDMASS_CHANNELS` | `[{"name": "Canal 1", "max_clients": 100}]` | Lista JSON de canais. `address` (máx. 15) e `port` são opcionais; ausentes usam `LANDMASS_PUBLIC_HOST` e `LANDMASS_CHANNEL_PORT`. `name` tem no máximo 35 caracteres. `mode` é o `channel_mode` do canal (0 normal; 6 clã, D199). Entre 1 e 255 canais. | 1 |
| `LANDMASS_SERVER_NAME` | `Norian` | Nome do servidor exibido no cliente. | 2 |
| `LANDMASS_GAME_HOST` | `127.0.0.1` | Endereço do servidor de partida anunciado no 403 (`NotifyStartGame`). Máximo 15 caracteres (campo `char[16]` NUL-terminado). Mínimo 1. Com `LANDMASS_MATCH_SERVER_DIR`, é o endereço do 403 de toda partida. | 3, 4 |
| `LANDMASS_GAME_PORT` | `7777` | Porta do servidor de partida anunciada no 403 quando a partida é fixa (sem `LANDMASS_MATCH_SERVER_DIR`). Entre 1 e 65535. | 3, 4 |
| `LANDMASS_GAME_SERVER_PASSWORD` | `4567` | Senha que o Game Server Host apresenta ao Channel (`ch_pw`). Não usada no caminho por processo (D46). | 4 |
| `LANDMASS_MATCH_SERVER_DIR` | não definida | Pasta `system\` do servidor-partida, com o `LandMass.exe`. Sem ela a partida é o endereço fixo de `LANDMASS_GAME_HOST/PORT`. Com ela, cada sala em partida tem um processo próprio (D46), e o equipamento vai para `LMEmu.ini` nessa pasta (D190). | 4 |
| `LANDMASS_MATCH_PORT_MIN` | `7800` | Primeira porta UDP da faixa das partidas. Entre 1024 e 65535. Não pode ser maior que `LANDMASS_MATCH_PORT_MAX`. | 4 |
| `LANDMASS_MATCH_PORT_MAX` | `7899` | Última porta UDP da faixa das partidas. Entre 1024 e 65535. | 4 |
| `LANDMASS_MATCH_READY_TIMEOUT` | `30` | Segundos até a porta da partida aparecer em `netstat`. Entre 0 e 300 (exclusivo em 0). Vencido o prazo, a sala volta à espera e o dono recebe o erro 241000201 (D47). | 4 |
| `LANDMASS_MATCH_LOGIN_NUM` | não definida | `login_num` que o servidor de partida recebe na linha de comando. Obrigatório junto com `LANDMASS_MATCH_SERVER_DIR`. Use o valor do `jogar_teste.bat`; não o versione (D54). | 4 |
| `LANDMASS_MATCH_BOTS` | `0` | Total mínimo de jogadores da partida, humanos e bots (`?MinPlayers=`), de 0 a 31; a URL leva o mínimo limitado ao máximo da sala. Só com `LANDMASS_MATCH_SERVER_DIR`: cada bot ganha uma linha `Bots=` no `LMEmu.ini` e a sala leva `Owner=` (D220, D221). | 4 |
| `LANDMASS_AUDIT_LOG` | `data/audit/economy.jsonl` | Arquivo do log de economia: uma linha JSON por compra (550), destruição (555) e extensão (580), aprovada ou recusada. Relativo à pasta de onde o servidor roda; use caminho absoluto quando rodar de outro checkout (D120). | F8 |
| `LANDMASS_SHUTDOWN_GRACE_SECONDS` | `300` | Prazo do desligamento (SIGINT, SIGTERM ou `landmass-emu shutdown`): segundos até as partidas serem encerradas e o processo sair. Entre 0 e 3600. (D202) | prod |
| `LANDMASS_SHUTDOWN_NOTICE_SECONDS` | `[300, 60, 10]` | Instantes de aviso antes do prazo, em segundos. Lista; no ambiente, em JSON (`[300, 60, 10]`). Cada valor entre 1 e 3600, sem repetir; a lista sai em ordem decrescente. Os avisos vão a quem está no lobby (D201, D202). | prod |
| `LANDMASS_CONTROL_FILE` | `data/control/shutdown.json` | Arquivo do pedido de `landmass-emu shutdown`. O processo em execução lê a cada segundo; pedido pendente de execução anterior é apagado na subida (D203). | prod |
| `LANDMASS_LOG_LEVEL` | `INFO` | Nível do log (o `serve` loga no stdout; a CLI, no stderr): `DEBUG`, `INFO`, `WARNING` ou `ERROR`. Cada conexão da sonda do HEALTHCHECK gera `conectou` e `desconectou` em INFO; com `WARNING` esses registros somem (D205). | prod |
| `LANDMASS_LOG_JSON` | `false` | Uma linha JSON por registro do `serve` (`ts`, `level`, `logger`, `msg`, e `exc` quando há erro), para o parser do operador (D205). | prod |

Regras:

- Não versione `.env` nem segredos.
- O heartbeat do Channel (10 s) é constante de `app.py` (`CHANNEL_HEARTBEAT_SECONDS`), não variável de ambiente.
- Caminhos padrão são relativos ao diretório de execução (raiz de `emulador\`); tudo fica dentro de `D:\landmass` (R3).
- Valores que o protocolo não comporta (nome de host longo, nickname longo) são rejeitados na configuração ou truncados no codec; nunca passam em silêncio.
- Bots (D220, D221): `LANDMASS_MATCH_BOTS` é o total mínimo de jogadores da partida, e o motor completa com bots até esse número, limitado ao máximo da sala (`MatchPlan.bots`). Cada bot possível (k de 1 até esse mínimo) vira uma linha da seção do `LMEmu.ini`, com a chave `Bots=` (a chave bate com a variável `config array<string> Bots` do pacote LMEmu, e `Bot` colidiria com a classe `Bot` do motor):

  ```
  Bots=?Name=Bot1?Skill=3?Species=XGame.SPECIES_AssaultB?Morat=101000002?MainWeapon=XGame.LM_AssaultRifle_AB?MainWeaponId=201030002?SubWeapon=XGame.LM_BigGun_AC?SubWeaponId=201070003?MeleeWeapon=XGame.LM_SpecialMelee_SsA?MeleeWeaponId=201130001?EtcWeapon1=XGame.LM_SmokeLauncher_AA?EtcWeapon1Id=201010007?EtcWeapon2=XGame.LM_GLauncher_AB?EtcWeapon2Id=201010002?EtcWeapon3=none?EtcWeapon3Id=0?Booster=XGame.LM_PartsDataBoosterA?BoosterId=203000001?Generator=XGame.LM_PartsDataGeneratorB?GeneratorId=202000002?Record=M_Assault02_0

  (Exemplo real: sorteio com semente 2026 sobre o `landmass.wdb` do cliente e o `MORATS.upl` da pasta do servidor de partida.)
  ```

  Morat e peças são sorteados por bot (`domain/bots.py`, `random.Random` injetado). O morat sai entre os do wdb cuja espécie tem registro de jogador no `MORATS.upl` da pasta do servidor de partida (lido na primeira partida com bots; sem o arquivo, a partida sobe sem bots e loga aviso). `Record` é o registro de time 0 da espécie. A classe de cada peça é a seção de `Item_Equip` cuja linha `item_id` traz o próprio id; munição do mesmo id fica de fora, e três ids com `item_slot` e sem `item_id` ficam de fora do sorteio. Peça sem candidato de classe e slot vem do `DefaultSet` do morat, se o id existe no catálogo; senão `none` com id `0`. Cabeça, corpo, braço, perna e pintura não são sorteados nesta fase.
- `Owner=<apelido em hex>` vai na mesma seção, com o apelido do dono da sala (mesmo formato de `Players=`). Sala sem dono com apelido não leva a linha.
- A sala conta só jogadores humanos: bots existem só no processo do servidor de partida, e `Rooms` (`domain/rooms.py`) não cria membro para eles. A capacidade da sala é a do cliente.
