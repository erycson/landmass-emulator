# Produção em Windows

Instalação, subida, desligamento gracioso, saúde, logs, administração e backup do servidor em produção. Tudo roda num host Windows: o emulador (Message e Channel) e um `LandMass.exe` por partida (D206). Decisões: D200 a D206 em [decisions/README.md](../decisions/README.md). Variáveis completas: [05-configuration.md](../architecture/05-configuration.md).

## Pré-requisitos

- Windows 10 ou 11, ou Windows Server, de 64 bits.
- Python e `uv`, como no desenvolvimento ([README](../../README.md)).
- Servidor de partida montado com o **Server Patch** ([`tools/server-patch/LEIA-ME.md`](../../tools/server-patch/LEIA-ME.md)): uma cópia do cliente com os patches de `Core.dll` e `LandMass.exe` e o `LMEmu.u`.
- Firewall:
  - TCP 7313 e 7314, para o emulador.
  - UDP 7800 a 7899, para as partidas (`LandMass.exe`).

## Configuração

Copie `config.example.toml` para `config.toml` e preencha os campos:

- `public_host`: o IP que os clientes alcançam.
- `match_server_dir`: a pasta `system` do servidor de partida. Com ela, o emulador sobe um `LandMass.exe` por sala.
- `client_dir`: a pasta `system` de um cliente, para o catálogo `landmass.wdb` e a loja.
- `match_login_num` e `database_url`: segredo e banco.

Segredo em arquivo: use `LANDMASS_<CAMPO>_FILE` (D200). Variável de ambiente vence o TOML.

## Subir

```
uv run landmass-emu serve --config config.toml
```

Na subida, o banco é criado e migrado (Alembic, `Migrator`). Para subir junto com o Windows, crie uma tarefa no Agendador de Tarefas:

- Gatilho "Ao iniciar o sistema".
- Ação: o comando acima, com "Iniciar em" na pasta do emulador.
- Opção "Executar estando o usuário conectado ou não".

Use réplica única. As salas e o lobby ficam na memória do processo, e o SQLite tem um único escritor.

## Desligamento

Desligar com aviso e prazo:

```
uv run landmass-emu shutdown --in 300 --message "Manutenção às 22h."
```

- O comando grava `data/control/shutdown.json`, e o servidor lê o pedido em até 1 s. A mensagem tem no máximo 80 bytes em cp1252.
- Ctrl+C e Ctrl+Break no console pedem o mesmo desligamento.
- Fechar a janela do console não chega como sinal e não é tratado.

### O que acontece (D202)

1. O pedido começa a contar o prazo `LANDMASS_SHUTDOWN_GRACE_SECONDS`, que é de 300 s por padrão.
2. Na janela de recusa:
   - A conexão nova é fechada logo no accept.
   - Criar sala e iniciar partida são recusados com os erros 211000201 e 241000201.
   - Quem já está conectado continua.
   - A janela começa no maior aviso antes do prazo, 300 s por padrão.
3. O lobby do Channel recebe avisos 300, 60 e 10 s antes do prazo, pelo opcode 251 (D201). O aviso aparece no HUD e no chat.
4. No prazo, as partidas em andamento são encerradas e gravadas com `end_reason` igual a `server_shutdown`.
5. O processo sai com código 0. Se o lobby esvaziar, sai antes do prazo.
6. Um segundo sinal encerra na hora. Um pedido seguinte só encurta o prazo, nunca o estende.

Quem está só no Message, sem canal, não recebe o aviso.

## Saúde e logs

- `uv run landmass-emu health` conecta nas portas 7313 e 7314, com 3 s por porta. Sai com 0 se as duas aceitam. Durante o desligamento a sonda segue verde (D204).
- Os logs do `serve` saem no stdout, e os da CLI no stderr (D205).
- `LANDMASS_LOG_LEVEL` define o nível. Com `LANDMASS_LOG_JSON=true`, sai uma linha JSON por registro.
- Para guardar os logs em arquivo, redirecione na tarefa: `... serve 1>> logs\serve.log 2>&1`.
- Cada partida grava `partida-<porta>-<id>.log` na pasta do servidor de partida.

## Administração

Os comandos rodam no host, com a mesma configuração:

```
uv run landmass-emu account ban --user ana --days 3
```

- Os comandos de conta, clã e loja gravam direto no banco. O servidor em execução não é avisado (veja o `--help` de cada comando).
- `account grant`, `account create`, `account item add`, `account morat add`, `account kit apply` e `shop sync` leem o `landmass.wdb` de `client_dir`.

## Dados e backup

Em `data\`:

- `landmass.db`: o banco (SQLite).
- `audit\economy.jsonl`: o log de economia (D120).
- `control\shutdown.json`: pedido de desligamento pendente, se houver.

Faça o backup com o servidor parado. Uma cópia do banco feita com o servidor no ar pode sair inconsistente.

## Limitações conhecidas

- Uma réplica. O estado de salas e lobby fica na memória.
- Sem TLS: os frames seguem o protocolo do cliente, sem criptografia (`re/channel_server.md`).
- `FixedMatchHost` (sem `match_server_dir`) manda toda partida a um endereço fixo. Serve para teste com um `servidor.bat` aberto à mão.
