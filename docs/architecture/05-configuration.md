# Configuração

Carregue com `pydantic-settings` (`settings.py`), prefixo `LANDMASS_`, de variáveis de ambiente e de `.env` opcional no diretório de execução.

| Variável | Padrão | Uso | Marco |
|----------|--------|-----|:-----:|
| `LANDMASS_DATABASE_URL` | `sqlite+aiosqlite:///data/landmass.db` | Banco de contas. Caminho relativo ao diretório de execução (raiz de `emulador\`). | 1 |
| `LANDMASS_BIND_HOST` | `0.0.0.0` | Interface de escuta dos dois serviços (Message e Channel). | 1 |
| `LANDMASS_PUBLIC_HOST` | `127.0.0.1` | IP anunciado aos clientes na lista de canais. Máximo 15 caracteres (campo `service_address`). | 1 |
| `LANDMASS_MESSAGE_PORT` | `7313` | Porta do Message Server. Também usada no `.bat` gerado. | 1 |
| `LANDMASS_CHANNEL_PORT` | `7314` | Porta de escuta do Channel Server e porta anunciada aos canais (`service_port`). | 1, 2 |
| `LANDMASS_CLIENT_VERSION` | `1245776779` | Versão em `version=` do `.bat` gerado. | 1 |
| `LANDMASS_CLIENT_DIR` | `../cliente/system` | Pasta onde `account create/token` grava `jogar_<user>.bat`. `account grant`, `account create`, `account item add`, `account morat add` e `account kit apply` leem dela o `landmass.wdb` (catálogo, somente leitura). | 1 |
| `LANDMASS_RECV_TIMEOUT` | `300` | Segundos sem tráfego antes de desconectar, em Message e Channel. Mínimo `60`. | 1, 2 |
| `LANDMASS_CHANNELS` | `[{"name": "Canal 1", "max_clients": 100}]` | Lista JSON de canais. `address` (máx. 15) e `port` são opcionais; ausentes usam `LANDMASS_PUBLIC_HOST` e `LANDMASS_CHANNEL_PORT`. `name` tem no máximo 35 caracteres. Entre 1 e 255 canais. | 1 |
| `LANDMASS_SERVER_NAME` | `Norian` | Nome do servidor exibido no cliente. | 2 |
| `LANDMASS_GAME_HOST` | `127.0.0.1` | Endereço do servidor de partida anunciado no 403 (`NotifyStartGame`). Máximo 15 caracteres (campo `char[16]` NUL-terminado). Mínimo 1. Com `LANDMASS_MATCH_SERVER_DIR`, é o endereço do 403 de toda partida. | 3, 4 |
| `LANDMASS_GAME_PORT` | `7777` | Porta do servidor de partida anunciada no 403 quando a partida é fixa (sem `LANDMASS_MATCH_SERVER_DIR`). Entre 1 e 65535. | 3, 4 |
| `LANDMASS_GAME_SERVER_PASSWORD` | `4567` | Senha que o Game Server Host apresenta ao Channel (`ch_pw`). Não usada no caminho por processo (D46). | 4 |
| `LANDMASS_MATCH_SERVER_DIR` | não definida | Pasta `system\` do servidor-partida, com o `LandMass.exe`. Sem ela a partida é o endereço fixo de `LANDMASS_GAME_HOST/PORT`. Com ela, cada sala em partida tem um processo próprio (D46). | 4 |
| `LANDMASS_MATCH_PORT_MIN` | `7800` | Primeira porta UDP da faixa das partidas. Entre 1024 e 65535. Não pode ser maior que `LANDMASS_MATCH_PORT_MAX`. | 4 |
| `LANDMASS_MATCH_PORT_MAX` | `7899` | Última porta UDP da faixa das partidas. Entre 1024 e 65535. | 4 |
| `LANDMASS_MATCH_READY_TIMEOUT` | `30` | Segundos até a porta da partida aparecer em `netstat`. Entre 0 e 300 (exclusivo em 0). Vencido o prazo, a sala volta à espera e o dono recebe o erro 241000201 (D47). | 4 |
| `LANDMASS_MATCH_LOGIN_NUM` | não definida | `login_num` que o servidor de partida recebe na linha de comando. Obrigatório junto com `LANDMASS_MATCH_SERVER_DIR`. Use o valor do `jogar_teste.bat`; não o versione (D54). | 4 |

Regras:

- Não versione `.env` nem segredos.
- O heartbeat do Channel (10 s) é constante de `app.py` (`CHANNEL_HEARTBEAT_SECONDS`), não variável de ambiente.
- Caminhos padrão são relativos ao diretório de execução (raiz de `emulador\`); tudo fica dentro de `D:\landmass` (R3).
- Valores que o protocolo não comporta (nome de host longo, nickname longo) são rejeitados na configuração ou truncados no codec; nunca passam em silêncio.
