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

Instale o LandMass e dê dois cliques em `tools\client-patch\configurar.bat`. Ele pergunta, uma por vez:

| Pergunta | O que muda no jogo |
|---|---|
| IP do servidor | Cria `system\jogar.bat`, que abre a tela de usuário e senha do jogo. |
| Ativar 4GB? | 1 bit no `LandMass.exe`: o jogo pode usar até 4 GB de memória. |
| Liberar o botão Iniciar sozinho? | 3 bytes no `XInterface.u`, para jogar sozinho contra bots. Só serve se o servidor tiver os bots ligados. |
| Configurar o vídeo? | [dgVoodoo2](https://github.com/dege-diosg/dgVoodoo2/releases) (baixe o zip e extraia), janela sem borda, widescreen, FOV e texturas no máximo. |

Armas, equipamento e bots não pedem nada no cliente: vêm do servidor. Cada item é opcional. Os originais ficam salvos (`*.orig`, `*.antes-patch`). Linha de comando e como desfazer: [`tools/client-patch/README.md`](tools/client-patch/README.md).

### 2. Peça uma conta

O administrador do servidor cria a conta com usuário e senha. Abra `system\jogar.bat` e entre pela tela de login do jogo. O administrador também pode entregar um `jogar_<usuário>.bat`, que entra direto: copie-o para a pasta `system` do cliente e execute.

O `Launcher.exe` só funciona se o administrador ligou o Launcher no servidor e distribuiu o cliente já apontado para ele (D242). Sem isso, use o `.bat`.

O `jogar_<usuário>.bat` contém o seu token de login. Trate-o como senha.

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

### Jeito fácil

Dê dois cliques em `tools\server-patch\configurar.bat`. Ele pergunta, uma por vez:

| Pergunta | Chave do `config.toml` |
|---|---|
| IP público, o que os jogadores alcançam | `public_host` e `game_host` |
| Pasta `system` do cliente instalado | `client_dir` |
| Ligar as partidas? (armas e equipamento da conta) | `match_server_dir`. Monta o servidor de partida (passo 1 abaixo). |
| Ligar os bots? e quantos jogadores por partida | `match_bots` (veja [Bots](#bots)) |
| Ligar o Launcher? | `update_port`. Também aponta o `landmass.wdb` do cliente para este servidor. |

No fim, ele grava o `config.toml` e cria o `iniciar-servidor.bat` na raiz. Para subir o servidor, execute esse `.bat`. Pode rodar o assistente de novo: as respostas atuais aparecem como padrão. Os passos abaixo são o mesmo processo feito à mão.

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
uv run landmass-emu --config config.toml serve
```

O banco SQLite (`data/landmass.db`) é criado e migrado na subida. Para produção (tarefa do Windows, logs e backup), veja [`docs/operations/production.md`](docs/operations/production.md).

Depois da primeira subida, importe a loja do cliente com `uv run landmass-emu shop sync`.

### Bots

Os bots são ligados só no servidor, por `match_bots` (exige `match_server_dir`):

- **`match_bots = 0`: desligados.** A partida só começa com outro jogador pronto, e o `/bot` não faz nada. Mesmo com o cliente alterado (`-IniciarSozinho`), o servidor recusa iniciar a sala com uma pessoa só.
- **`match_bots = N`: ligados.** A partida já começa completa com bots até N jogadores, humanos incluídos. O dono da sala pode iniciar sozinho. Com o padrão 4, você entra com 3 bots. Em time, o motor põe cada bot no time menor: você e 1 bot de um lado, 2 bots do outro. Quem entra depois toma a vaga de um bot. Na partida, o dono ainda usa `/bot add` e `/bot remove`.

Cada bot sai com um morat e um equipamento sorteados dentro da classe dele, e com o nome `[BOT] Apelido`. Os bots seguem as rotas do mapa (`LMEmuRoutes.ini`). Por enquanto, só o ONS-Airport tem rotas geradas ([`tools/routes`](tools/routes/README.md)).

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
