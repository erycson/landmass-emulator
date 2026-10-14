# LandMass Emulator

Servidor do LandMass reescrito em Python, para jogar o cliente original de 2009 depois do fim dos servidores oficiais.

O cliente é a fonte da verdade: cada mensagem e cada regra vêm da engenharia reversa do cliente e do servidor de sala (`LM_Engine.dll`). A prova fica em [`tools/re/`](tools/re/NOTES.md).

> Este repositório não contém o jogo. Você precisa de uma instalação própria do cliente do LandMass.

## O que o servidor tem

| Área | Recursos |
|---|---|
| Entrada | Login por token, lista de canais, troca de canal |
| Lobby | Chat do canal e da sala, sussurro, lista de jogadores, busca por apelido |
| Social | Amigos, bloqueio, clãs (criar, entrar, marca), guerra de clã no canal de clã |
| Salas | Criar, entrar com senha, slots e times, pronto, convite, expulsão, espectadores, troca de configuração |
| Partida | Um `LandMass.exe -server` por sala, com morat e equipamento da conta. Modos DM, TDM, Operação e Bombing Run. Fim de partida com exp e LD, e deserção |
| Bots | Bots nas partidas, com morat e equipamento sorteados. Comandos `/bot` do dono da sala. Rotas geradas pela geometria do mapa (por enquanto só o Airport) |
| Progresso | Exp e patente, LD e Cash, inventário com prazo, morats por gate, equipamento, peças e pintura, atalhos e opções de tecla |
| Loja | Compra em LD ou Cash por nível de preço, extensão de prazo, Item Surpresa, presente e depósito |
| Ranking | Ranking de jogadores |
| GM | Aviso geral, aviso no canal e expulsão, por nível de acesso |
| Operação | Configuração por TOML ou ambiente, desligamento com aviso aos jogadores, verificação de saúde, log de economia |

O que falta e o que não foi verificado no jogo está em [`docs/roadmap.md`](docs/roadmap.md) e nas decisões ([`docs/decisions/README.md`](docs/decisions/README.md)).

## Como jogar

### 1. Prepare o cliente

Instale o LandMass, baixe o [dgVoodoo2](https://github.com/dege-diosg/dgVoodoo2/releases) (zip da versão 2.87.5 ou mais nova, extraído numa pasta) e aplique o **Client Patch**. Ele deixa o jogo em janela sem borda, com widescreen, FOV ajustado e texturas na qualidade máxima:

```
powershell -ExecutionPolicy Bypass -File tools\client-patch\aplicar.ps1 -Cliente "C:\LandMass" -DgVoodoo "C:\Downloads\dgVoodoo2_87_5"
```

| Opção | Efeito |
|---|---|
| `-Largura 2560 -Altura 1080` | Resolução da partida. Sem ela, usa a do monitor principal. |
| `-IniciarSozinho` | Ativa o botão de iniciar sem outro jogador pronto, para jogar contra bots. |

Detalhes e como desfazer: [`tools/client-patch/README.md`](tools/client-patch/README.md).

### 2. Peça uma conta

O administrador do servidor cria a conta e entrega um `jogar_<usuário>.bat`. Copie esse arquivo para a pasta `system` do cliente e execute.

Não use o `Launcher.exe`, porque ele procura um servidor de atualização que não existe mais.

O `.bat` contém o seu token de login. Trate-o como senha.

### 3. Dentro do jogo

| Comando no chat | Quem | Efeito |
|---|---|---|
| `/bot add [0-9]` | Dono da sala, na partida | Adiciona um bot. O número é a dificuldade: 0 a 9, e sem número vale 3. |
| `/bot remove` | Dono da sala, na partida | Remove o bot mais recente. |
| `/NOTIFY <texto>` | GM (nível 9 ou mais) | Aviso no canal. |
| `/ALLNOTIFY <texto>` | GM | Aviso a todos os canais. |
| `/EXPEL <apelido>` | GM | Expulsa o jogador. |

- Os bots aparecem como `[BOT] Apelido`, com ping 0. Um humano que entra numa partida cheia toma a vaga do bot mais recente.
- O jogo expulsa quem fica 3 minutos sem jogar (AFK), e isso conta como deserção.

## Como montar um servidor

Requisitos: Windows 10 ou 11 (ou Windows Server), Python 3.14 e [`uv`](https://docs.astral.sh/uv/). O servidor de partida é o próprio `LandMass.exe`, que só roda em Windows.

### 1. Servidor de partida

Monte uma cópia do cliente com o **Server Patch**. Ele aplica dois patches de bytes e instala o pacote `LMEmu.u` e as rotas dos bots:

```
powershell -ExecutionPolicy Bypass -File tools\server-patch\aplicar.ps1 -Cliente "C:\LandMass" -Destino "D:\servidor-partida"
```

Detalhes: [`tools/server-patch/README.md`](tools/server-patch/README.md).

### 2. Configuração

Copie `config.example.toml` para `config.toml` e ajuste:

| Chave | Valor |
|---|---|
| `public_host` | O IP que os jogadores alcançam. |
| `client_dir` | A pasta `system` de um cliente: catálogo, mapas e loja vêm do `landmass.wdb`. |
| `match_server_dir` | A pasta `system` do servidor de partida. Com ela, cada sala abre um `LandMass.exe`. |
| `match_bots` | Total mínimo de jogadores numa partida, completado com bots. 0 desliga os bots. |

O `match_login_num` é um segredo: passe por `LANDMASS_MATCH_LOGIN_NUM_FILE`. Toda chave também pode vir de uma variável `LANDMASS_<CHAVE>` ([referência](docs/architecture/05-configuration.md)).

Libere no firewall:
- TCP 7313 e 7314 (emulador);
- UDP 7800 a 7899 (partidas).

### 3. Subir

```
uv sync
uv run landmass-emu serve --config config.toml
```

O banco SQLite (`data/landmass.db`) é criado e migrado na subida. Para produção (tarefa do Windows, logs e backup), veja [`docs/operations/production.md`](docs/operations/production.md).

Depois da primeira subida, importe a loja do cliente com `uv run landmass-emu shop sync`.

## Comandos da CLI

Todos rodam com `uv run landmass-emu <comando>` e aceitam `--config`. Os comandos de conta, clã e loja gravam direto no banco: um servidor em execução não é avisado, e o jogador vê a mudança ao relogar. Use `--help` em cada comando para ver as opções.

### Servidor

| Comando | Efeito |
|---|---|
| `serve` | Sobe o Message (TCP 7313) e o Channel (TCP 7314). |
| `shutdown --in 300 --message "Manutenção"` | Desliga o servidor em execução, com avisos aos jogadores. |
| `health` | Testa as portas e sai com 0 se as duas aceitam conexão. |
| `sniff` | Grava os bytes que o cliente envia, sem responder. Serve para engenharia reversa. |

### Contas (`account`)

| Comando | Efeito |
|---|---|
| `account create --user ana --nickname Ana` | Cria a conta e grava o `jogar_ana.bat` na pasta do cliente. |
| `account token --user ana` | Gera um novo token e invalida o anterior. |
| `account grant --user ana --exp 1000 --ld 5000 --cash 100` | Soma exp, LD e Cash. |
| `account ban --user ana --days 3` | Bloqueia o login por N dias. |
| `account unban --user ana` | Remove o bloqueio. |
| `account access ana 9` | Nível de acesso: 0 jogador, 9 GM, 10 administrador. |
| `account item add` | Dá um item com prazo em dias. |
| `account morat add` | Dá um morat num gate (0 a 7). |
| `account kit apply` | Aplica o kit inicial (morats com peças padrão) a uma conta. |

O usuário (`--user`) tem de 1 a 12 caracteres: minúsculas, dígitos ou `_`. O apelido tem até 16 bytes e não pode começar com `[BOT]`.

### Clãs (`clan`)

`create`, `join`, `leave`, `rename`, `mark` e `show`.

### Loja (`shop`)

| Comando | Efeito |
|---|---|
| `shop sync` | Importa do `landmass.wdb` os itens à venda, com nome e preços. |
| `shop list [--disabled]` | Lista ID, nome, preços e status. |
| `shop enable <id>` / `shop disable <id>` | Liga ou desliga a venda do item. |
| `shop price <id> <nível> [--point N] [--cash N]` | Muda o preço de um nível. `--point` é LD, e 0 não vende naquela moeda. |

## Estrutura

| Pasta | Conteúdo |
|---|---|
| `src/landmass_emu/` | O emulador: protocolo, domínio, banco, serviços. |
| `tests/` | Testes (`uv run pytest`). |
| `docs/` | Arquitetura, protocolo, operação e decisões. Comece por [`docs/README.md`](docs/README.md). |
| `tools/client-patch/` | Patch do cliente: janela, widescreen e o botão de iniciar opcional. |
| `tools/server-patch/` | Montagem do servidor de partida, com `LMEmu.u` e rotas dos bots. |
| `tools/unreal/` | Fontes do pacote `LMEmu` (UnrealScript), build e troca de textura. |
| `tools/routes/` | Geração das rotas dos bots a partir do log do bake. |
| `tools/re/` | Notas de engenharia reversa (só `.md`). |
| `tools/scripts/` | Automação de teste com o cliente. |

## Desenvolvimento

```
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

Os quatro precisam passar antes de cada commit. A documentação é técnica e no imperativo; registre as mudanças no arquivo de `docs/` do assunto e as decisões em [`docs/decisions/README.md`](docs/decisions/README.md).

## Licença

[GNU Affero General Public License v3.0](LICENSE) ou posterior (AGPL-3.0-or-later). Em resumo:

- Você pode usar, estudar, modificar e distribuir o emulador, inclusive com fins comerciais.
- Quem distribuir o código, modificado ou não, tem de manter a mesma licença e entregar o código-fonte.
- **Servidor público conta como distribuição:** se você rodar uma versão modificada para outras pessoas jogarem pela rede, tem de oferecer a elas o código-fonte dessa versão.
- Não há garantia.

O texto válido é o do [LICENSE](LICENSE); este resumo não o substitui.

LandMass e seus recursos pertencem aos respectivos donos. Este projeto não é afiliado a eles e não distribui o jogo. O dgVoodoo2 é de terceiro e tem licença própria.
