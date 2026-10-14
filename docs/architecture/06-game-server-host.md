# Game Server Host

## Problema

A partida roda em um processo UE2 em modo servidor (`LandMass.exe ... -server`). O cliente só precisa do endereço e da porta no 403 (`NotifyStartGame`); o servidor abre a porta UDP sozinho. O caminho com `GS_*` (`UServerEngine` e `InitServer` de `LM_Engine.dll`) não é usado para o deathmatch. Evidência: [`../../re/game_server_host.md`](../../re/game_server_host.md), seções 9, 10 e 11.

## Como funciona (marco 4)

Uma partida por sala. O canal lança um servidor próprio para cada sala que inicia (`hosting/process.py`) e o encerra no fim.

| Passo | Quem | O que acontece |
|-------|------|----------------|
| 1 | Cliente do dono | Manda 401 com todos os outros prontos. |
| 2 | `Rooms.start` (`domain/rooms.py`) | Sala passa a jogando; cada membro entra em `in_game`. |
| 3 | `RoomHandlers` | 412 PLAYING vai ao lobby. O 403 ainda não sai. |
| 4 | `MatchHost.start(room_id, plan, on_exit)` | Ver a seção "Hospedagem" abaixo. Espera o servidor aceitar conexões. |
| 5 | `RoomHandlers` | Pronto: 403 (endereço e porta da partida) só a quem está na sala. |
| 6 | `RoomHandlers` | Falha: sala volta à espera (412 WAITING, 402 sem pronto) e o dono recebe o erro 241000201. |
| 7 | Fim da partida | Ver "Fim da partida" abaixo. Histórico gravado uma vez. |

### Hospedagem

- **Fixa** (`FixedMatchHost`): sem `LANDMASS_MATCH_SERVER_DIR`. O 403 leva `LANDMASS_GAME_HOST:LANDMASS_GAME_PORT`; não há processo. Mesmo assim, o 401 consulta o mapa no `landmass.wdb` (ver Riscos).
- **Por processo** (`ProcessMatchHost`): com `LANDMASS_MATCH_SERVER_DIR` (pasta `system\` do servidor-partida):
  1. Escolhe a primeira porta UDP livre em `LANDMASS_MATCH_PORT_MIN..MAX`. O teste é um bind e fechamento, feito antes do lançamento.
  2. Grava a seção `[m<8 hex> LMEmuLoadout]` no `LMEmu.ini` da pasta de sistema, com uma linha `Players=` por jogador (`hosting/loadout.py`, D190). Falha de escrita é falha de início.
  3. Lança `LandMass.exe <mapa>?listen?game=<classe>?MaxPlayers=<n>?TimeLimit=<t>?GoalScore=<g>?lmemu=<chave> -server PORT=<porta> -log login_server=<msg>?version=<v>?login_num=<l>`. `login_server` é `LANDMASS_PUBLIC_HOST:LANDMASS_MESSAGE_PORT`. A classe é `LMEmu.*` (D190).
  4. Espera a porta aparecer em `netstat -ano -p UDP` com o PID do próprio processo, até `LANDMASS_MATCH_READY_TIMEOUT` segundos. Não há bind de teste depois do lançamento: disputaria a porta com o servidor.
  5. Se o processo cai antes de abrir a porta, ou o prazo vence, o processo é encerrado, a seção sai do `LMEmu.ini` e a partida falha.
- `PORT=` abre uma única tentativa, sem fallback (re/game_server_host.md, §10). Porta ocupada é falha, não troca.
- Plano da partida (`domain/match.py`, puro): mapa de `maps` (`RecordIndex` = `map_num`), classe pelo modo e pelo `OPType` do mapa (D53, D170, D192), `MaxPlayers` limitado pelo mapa e no mínimo 2.
- Equipamento (`domain/loadout.py`, puro, com as portas de inventário e conta): para cada jogador, o morat do gate escolhido no 401, com peças e pinturas montadas, senão o `DefaultSet` do wdb. Ver D190.

### Fim da partida

A partida acaba em um de três casos (D48):

1. Todos os jogadores que estavam na partida mandaram 500 (ExitPlay). O canal responde 501 a cada um.
2. O último jogador em jogo sai da sala sem ter mandado 500.
3. O processo do servidor cai depois de pronto (`on_exit`).

Nos três casos o canal faz o mesmo: encerra o servidor pelo console (`MatchHost.end`, digita `exit` e espera o `LOG=`, D153), volta a sala à espera (412 WAITING ao lobby, 402 sem pronto para cada membro, o dono incluído (D77), 317 à sala) e grava o histórico uma vez (D52). Sala que esvazia no meio da partida é encerrada sem gravar.

Quem entra de novo na própria sala depois da partida (311) recebe 312, 314 e 317 só para si (D49). Esse 311 também tira o jogador da partida: quando o último em jogo volta assim, a partida acaba sem 500 e grava com `end_reason` `return_to_room` (D150).

Quem sai antes do fim (500 com outros ainda em jogo, ou o 311 de volta nesse caso) fica na sala sem pronto (D210). O canal zera o pronto e manda o 317 só a quem saiu. Sem isso, o cliente trava Sair, Opções e Iniciar, que dependem de sala jogando sem pronto (`LM_RoomPage.RefreshPlayers`).

O bloco `GameEnded` é lido ao fim da partida. O servidor o escreve no `EndGame`, que pode ocorrer por último jogador, tempo ou pontuação. O emulador pede a saída pelo console (`exit`), espera o motor gravar o `LOG=` da partida e só então derruba o processo (D153). `hosting/game_end.py` lê o último bloco completo e os jogadores casam pelo nick (D154). Quem não aparece no bloco fica com métricas nulas e sem recompensa (`re/game_server_host.md`, seções 11.4 e 11.7).

## Partida em memória

Salas e partida em andamento ficam só em memória (D24, D52). Se o emulador cai, as salas somem e a partida começa de novo. Nada é gravado durante a partida. Ao fim, o histórico vai para `matches` e `match_players` (ver [`04-persistence.md`](04-persistence.md), "Histórico de partidas").

## Contrato do motor (caminho `GS_*`, não usado)

| Export | Função |
|--------|--------|
| `InitServer(wchar* cmdline)` | Lê `ip=`, `port=`, `mode=`, `ch_ip=`, `ch_port=`, `ch_code=`, `ch_pw=`; carrega `ServerMessage.wdb` e `error.wdb`; conecta ao Channel. |
| `ChannelServerTick()` | Processa mensagens `GS_*` do Channel. |
| `LogoutChannelServer()` / `ExitServer()` | Desconexão e encerramento. |
| `ServerRoom()` | Acesso ao `CServerRoom` (jogadores autorizados da sala). |
| `UServerLevel::NotifyReceivedText` | Handshake UE2; no `LOGIN`, chama `LoginPlayer(key, name, team)`. |

Este contrato só seria necessário se a validação de jogador fosse feita pelo servidor de partida. Hoje o `key` e o `team` do cliente não são conferidos no caminho de deathmatch (re/game_server_host.md, §9.2). A subida DM não abre TCP para 7313 nem 7314 (`re/game_server_host.md`, §11.2), e o DM não lê `key` nas opções de URL (§11.3).

## Abordagens

| Opção | Descrição | Situação |
|-------|-----------|----------|
| A | Host nativo 32-bit mínimo que carrega as DLLs UE2, chama `appInit`, `InitServer` e executa o laço. | Não escolhida. |
| B | `LandMass.exe SERVER` com `INI=` próprio + shim que chame `InitServer`. | Não escolhida: `UServerEngine::Init` não chama `InitServer`. |
| C | Canal lança o `LandMass.exe -server` por sala com `PORT=` (D46). | **Escolhida.** Sem shim e sem `GS_*`. |

## Requisitos e configuração

- `LANDMASS_GAME_HOST` e `LANDMASS_GAME_PORT`: endereço do 403 quando a partida é fixa, e endereço (host) do 403 quando é por processo (a porta vem da faixa).
- `LANDMASS_GAME_SERVER_PASSWORD` (`ch_pw`) não é usada no caminho atual. Fica documentada para o caminho `GS_*`.
- Variáveis `LANDMASS_MATCH_*`: ver [`05-configuration.md`](05-configuration.md).

## Riscos e pendências

- Partida real não testada no jogo: a porta por `PORT=` (UDP aberta com o PID, §11.2), o 403 atrasado, o 500 como fim e o 501 com valor 0 dependem do cliente real.
- Volta à sala pelo 311 como fim da partida é inferido (D150); não validado no cliente real.
- Depósito: 588 responde 589 (D151); o botão Terminar não foi testado no cliente real.
- Estatísticas de partida: o bloco `GameEnded` é lido ao fim da partida (D153, D154). Falta a prova com dois clientes; sem o bloco, as métricas ficam nulas (ver `04-persistence.md`).
- Matching de `map_num` com `RecordIndex` e unidades de `TimeLimit` são inferidos (D53).
- Um cliente que nunca manda 500 com o servidor vivo mantém a sala em jogo até o processo cair. Sem prazo próprio de partida (ver `operations/game-server.md`).
- Entrar de novo numa partida em andamento não tem suporte (D210). O 401 de quem saiu com a sala jogando é recusado sem resposta, e o botão de pronto continua habilitado no cliente.
- Quem saiu aparece como pronto para os outros jogadores até o fim da partida (D210). Só o próprio cliente recebe o pronto zerado.
- Modo fixo também precisa do `landmass.wdb` e do mapa da sala: sem eles o 401 devolve 241000201. Antes do marco 4 o 403 saía sem consultar o catálogo, então é uma mudança de comportamento.
- Equipamento na partida (D190): o cliente não manda o equipamento (`EnterGame` não manda `character`, D141). O emulador monta cada jogador no `LMEmu.ini` a partir do inventário. Não validado no jogo: o pacote `LMEmu` precisa estar em `servidor-partida\system` (ver [game-server](../operations/game-server.md)), e o `selected_morats` do 401 é tratado como gate sem prova (`re/rooms.md` §5).
- Bombing Run (D192): a classe e o grupo mínimo de dois times vêm do `CServerRoom::Init` nativo. Não testados com clientes.
