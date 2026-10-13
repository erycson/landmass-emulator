# Configuração

Carregue com `pydantic-settings` (`settings.py`), prefixo `LANDMASS_`, de variáveis de ambiente e de `.env` opcional no diretório de execução.

| Variável | Padrão | Uso | Marco |
|----------|--------|-----|:-----:|
| `LANDMASS_DATABASE_URL` | `sqlite+aiosqlite:///data/landmass.db` | Banco de contas. Caminho relativo ao diretório de execução (raiz de `emulador\`). | 1 |
| `LANDMASS_BIND_HOST` | `0.0.0.0` | Interface de escuta. | 1 |
| `LANDMASS_PUBLIC_HOST` | `127.0.0.1` | IP anunciado aos clientes na lista de canais. Máximo 15 caracteres (campo `service_address`). | 1 |
| `LANDMASS_MESSAGE_PORT` | `7313` | Porta do Message Server. Também usada no `.bat` gerado. | 1 |
| `LANDMASS_CHANNEL_PORT` | `7314` | Porta anunciada para os canais (`service_port`). | 1 |
| `LANDMASS_CLIENT_VERSION` | `1245776779` | Versão em `version=` do `.bat` gerado. | 1 |
| `LANDMASS_CLIENT_DIR` | `../cliente/system` | Pasta onde `account create/token` grava `jogar_<user>.bat`. | 1 |
| `LANDMASS_RECV_TIMEOUT` | `300` | Segundos sem tráfego antes de desconectar. Mínimo `60`. | 1 |
| `LANDMASS_CHANNELS` | `[{"name": "Canal 1", "max_clients": 100}]` | Lista JSON de canais. `address` (máx. 15) e `port` são opcionais; ausentes usam `LANDMASS_PUBLIC_HOST` e `LANDMASS_CHANNEL_PORT`. `name` tem no máximo 35 caracteres. Entre 1 e 255 canais. | 1 |
| `LANDMASS_SERVER_NAME` | `Norian` | Nome do servidor exibido no cliente. | 2 |
| `LANDMASS_CLIENT_WDB` | `../cliente/system/landmass.wdb` | Dados estáticos do cliente. | 2 |
| `LANDMASS_GAME_SERVER_PASSWORD` | `4567` | Senha que o Game Server Host apresenta ao Channel (`ch_pw`). | 4 |

Regras:

- Não versione `.env` nem segredos.
- Caminhos padrão são relativos ao diretório de execução (raiz de `emulador\`); tudo fica dentro de `D:\landmass` (R3).
- Valores que o protocolo não comporta (nome de host longo, nickname longo) são rejeitados na configuração ou truncados no codec; nunca passam em silêncio.
