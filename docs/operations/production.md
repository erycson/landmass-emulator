# Produção no Docker Swarm

Imagem, stack, desligamento gracioso, saúde, logs, administração e limitações do servidor em produção. Decisões: D200 a D205 em [decisions/README.md](../decisions/README.md). Variáveis completas: [05-configuration.md](../architecture/05-configuration.md).

## Limitação: o servidor de partida é Windows

O `LandMass.exe` (servidor de partida, `-server`) é executável Windows. A imagem é Linux. Consequências:

- Não defina `LANDMASS_MATCH_SERVER_DIR` no stack. Sem ela, toda partida vai para o endereço fixo `LANDMASS_GAME_HOST` e `LANDMASS_GAME_PORT`. O `LandMass.exe` roda fora do cluster, num host Windows que os clientes alcançam nesse endereço.
- Não há validação de plataforma ainda. Com a variável definida num container Linux, o processo da partida não sobe; não a defina no stack.
- Rodar o `LandMass.exe` sob Wine num nó Linux não foi testado. Não trate como solução pronta.

### Divisão proposta (não implementada)

Separar o canal, que fica no Swarm, do host de partida, que fica no Windows. O ponto de costura já existe: o protocolo `MatchHost` (`src/landmass_emu/ports/match_host.py`), com `start`, `finish`, `end` e `close`. Hoje há duas implementações: `FixedMatchHost` (endereço fixo) e `ProcessMatchHost` (um processo por sala, só Windows).

A proposta é um `RemoteMatchHost` no canal que pede a um agente no host Windows para subir e parar o `LandMass.exe`, e recebe de volta o `GameEndpoint`. O agente roda o `ProcessMatchHost` atual. O canal não muda: o 403, o encerramento e a gravação com `end_reason` seguem como estão.

Pendências: autenticação do agente, faixa de portas, reinício do agente e a entrega do `LMEmu.ini` (D190) ao host Windows, porque hoje ele é escrito na pasta do servidor de partida.

## Pré-requisitos

- Docker Swarm com ao menos um nó.
- Imagem construída no nó ou num registro. Fixe a tag: o stack usa `landmass-emu:latest` por padrão.

```bash
docker build -t landmass-emu:latest .
```

- Secret com a URL do banco. A configuração remove só o fim de linha final do arquivo; o resto do valor fica como está.

```bash
printf '%s' 'sqlite+aiosqlite:////app/data/landmass.db' | docker secret create landmass_database_url -
```

- `LANDMASS_PUBLIC_HOST` com o IP que os clientes alcançam. É obrigatório: o stack recusa a subida sem ele.

## Subir

```bash
export LANDMASS_PUBLIC_HOST=203.0.113.10
docker stack deploy -c deploy/stack.yml landmass
docker service ps landmass_landmass
docker service logs -f landmass_landmass
```

Na subida, o banco é criado e migrado (Alembic, `Migrator`). Sem `LANDMASS_CLIENT_DIR` apontando para um cliente, o servidor sobe com aviso de loja vazia: nada à venda até `shop sync` rodar com o cliente.

Para usar um TOML em vez de só variáveis, monte o arquivo no volume ou num config do Swarm e defina `LANDMASS_CONFIG`. A variável de ambiente vence o TOML (D200).

Réplica única. As salas e o lobby ficam na memória do processo, e o SQLite tem um escritor. Não escale o serviço.

## Desligamento

Pedidos de desligamento, todos com o mesmo efeito:

- `docker service update`, `docker stack rm` ou `docker stop`: o Swarm manda SIGTERM e espera `stop_grace_period` antes do SIGKILL.
- `docker exec` com o comando `shutdown`, para desligar com aviso e prazo:

```bash
docker exec "$(docker ps -q -f name=landmass_landmass)" \
  /app/.venv/bin/landmass-emu shutdown --in 300 --message "Manutenção às 22h."
```

O comando grava `data/control/shutdown.json` no volume, e o servidor lê o pedido em até 1 s. A mensagem tem no máximo 80 bytes em cp1252.

Ctrl+C e Ctrl+Break pedem o mesmo desligamento num processo local. No Windows, fechar a janela do console não chega como sinal e não é tratado.

### O que acontece (D202)

1. O pedido começa o prazo, `LANDMASS_SHUTDOWN_GRACE_SECONDS` (300 s por padrão).
2. Desde o pedido, conexão nova é fechada no accept. Criar sala e iniciar partida são recusados com os erros 211000201 e 241000201. Quem já está conectado continua.
3. O lobby do Channel recebe avisos em 300, 60 e 10 s antes do prazo (`LANDMASS_SHUTDOWN_NOTICE_SECONDS`). O aviso aparece no HUD e no chat, pelo opcode 251 (D201), com a mensagem do comando e o tempo que falta.
4. No prazo, as partidas em andamento são encerradas com a parada graciosa do servidor de partida. Cada uma é gravada com `end_reason` igual a `server_shutdown`.
5. O processo sai com código 0. Sai antes do prazo se o lobby esvaziar.
6. Um segundo sinal encerra já. Um pedido seguinte só encurta o prazo, nunca o estende.

### Limites

- Quem está só no Message, sem canal, não recebe o aviso. O aviso sai pelo lobby do Channel.
- O prazo do Swarm precisa cobrir o desligamento inteiro. O `stop_grace_period` do stack é `6m`: 300 s de prazo, até 8 s de parada de partida (`EXIT_GRACE_SECONDS`) e margem para gravar o banco. Se aumentar `LANDMASS_SHUTDOWN_GRACE_SECONDS`, aumente o `stop_grace_period` no mesmo tanto.
- Com `restart_policy` em `on-failure`, uma saída 0 não reinicia o serviço. Para voltar depois de um desligamento planejado:

```bash
docker service update --force landmass_landmass
```

- Se o processo não sai antes do `stop_grace_period`, o Swarm mata o processo e as partidas abertas não são gravadas.

## Saúde e logs

- O HEALTHCHECK roda `landmass-emu health` a cada 30 s. A sonda conecta nas portas 7313 e 7314 (3 s por porta). Se qualquer uma recusar, a saída é 1 e o Swarm troca a tarefa.
- Durante o desligamento a sonda segue verde, porque os listeners continuam abertos (D204). Sem isso, o Swarm reiniciaria a tarefa no meio do prazo.
- Os logs saem no stdout. Com `LANDMASS_LOG_JSON=true` (padrão do stack), cada linha é um objeto JSON com `ts`, `level`, `logger` e `msg`.
- Cada conexão da sonda gera `conectou` e `desconectou` em INFO, por porta, a cada 30 s. Para cortar esse ruído, use `LANDMASS_LOG_LEVEL=WARNING`, mas os registros de conexão dos jogadores também somem.

```bash
docker service logs -f landmass_landmass
```

## Administração

Os comandos rodam no container:

```bash
docker exec "$(docker ps -q -f name=landmass_landmass)" \
  /app/.venv/bin/landmass-emu account ban --user ana --days 3
```

- Os comandos de conta, clã e loja gravam direto no banco. O servidor em execução não é avisado (ver `--help` de cada comando).
- `account grant`, `account create`, `account item add`, `account morat add`, `account kit apply` e `shop sync` leem o catálogo `landmass.wdb` de `LANDMASS_CLIENT_DIR`. A imagem não tem o cliente. `account create` e `account token` gravam o `.bat` lá. Rode esses comandos no host com a mesma `LANDMASS_DATABASE_URL`, ou monte a pasta `system` do cliente em somente leitura e aponte `LANDMASS_CLIENT_DIR` para ela.
- `ban`, `unban` e os comandos de clã não precisam do cliente.

## Dados e backup

O volume `landmass-data` fica em `/app/data`:

- `landmass.db`: o banco (SQLite).
- `audit/economy.jsonl`: o log de economia (D120).
- `control/shutdown.json`: pedido de desligamento pendente, se houver.

Faça o backup com o serviço parado: `docker service scale landmass_landmass=0`, copie o volume e suba de novo. Copiar o banco com o servidor no ar pode deixar uma cópia inconsistente.

## Limitações conhecidas

- Servidor de partida só Windows (seção acima).
- Uma réplica. Estado de salas e lobby na memória.
- Sem TLS: os frames seguem o protocolo do cliente, sem criptografia (`re/channel_server.md`, linha de cabeçalho).
- Imagem sem o cliente: catálogo e loja precisam do wdb fora do container (seção Administração).
- A faixa UDP 7800 a 7899 é publicada, mas só é usada com `LANDMASS_MATCH_SERVER_DIR`, que não roda no container Linux.
- O deploy em Swarm real não foi testado: a stack foi validada com `docker stack config`, e a imagem foi construída e exercitada num container local.
