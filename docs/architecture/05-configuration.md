# Configuração

Carregue com `pydantic-settings`, prefixo `LANDMASS_`, de variáveis de ambiente e de `.env` opcional na raiz do projeto.

| Variável | Padrão | Uso |
|----------|--------|-----|
| `LANDMASS_DATABASE_URL` | `sqlite+aiosqlite:///../data/landmass.db` | Banco de contas. |
| `LANDMASS_BIND_HOST` | `0.0.0.0` | Interface de escuta. |
| `LANDMASS_PUBLIC_HOST` | `127.0.0.1` | IP anunciado aos clientes (lista de canais, game server). |
| `LANDMASS_MESSAGE_PORT` | `7313` | Porta do Message Server. |
| `LANDMASS_CHANNEL_PORT` | `7314` | Porta do Channel Server. |
| `LANDMASS_SERVER_NAME` | `Norian` | Nome do servidor exibido no cliente. |
| `LANDMASS_CLIENT_VERSION` | `1245776779` | Versão esperada em `version=`. |
| `LANDMASS_RECV_TIMEOUT` | `300` | Segundos sem tráfego antes de desconectar. |
| `LANDMASS_GAME_SERVER_PASSWORD` | `4567` | Senha que o Game Server Host apresenta ao Channel (`ch_pw`). |
| `LANDMASS_CLIENT_WDB` | `../cliente/system/landmass.wdb` | Dados estáticos do cliente. |

Regras:

- Não versione `.env` nem segredos.
- Mantenha caminhos relativos a `D:\landmass` (R3).
