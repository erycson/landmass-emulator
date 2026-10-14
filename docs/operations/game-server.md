# Servidor de partida (cópia `servidor-partida`)

Status: cópia montada, patches aplicados, partidas testadas com clientes reais. A evidência de engenharia reversa e as pendências estão em [`../../re/game_server_host.md`](../../re/game_server_host.md).

## Montagem da cópia

Use o `D:\landmass\Server Patch`. O `aplicar.ps1` copia o cliente sem o que o servidor não usa, aplica os dois patches abaixo conferindo os bytes originais e instala o `LMEmu.u`:

```
powershell -ExecutionPolicy Bypass -File "D:\landmass\Server Patch\aplicar.ps1" -Cliente D:\landmass\cliente -Destino D:\landmass\servidor-partida
```

O `build_lmemu.py` atualiza o `LMEmu.u` do Server Patch junto com o servidor e os clientes.

`cliente` e `cliente2` não são alterados. O instalador `LandMass_Setup_20090701.exe` não é tocado.

### Patches (somente na cópia)

| Arquivo | Offset (arquivo) | Antes | Depois | Motivo | Original |
|---------|------------------|-------|--------|--------|----------|
| `system\Core.dll` | `0x3F9C6` (260550) | `74 0E` (`je +0x0E`) | `90 90` (`nop nop`) | Em `appInit`, o `je` pula a cópia da linha de comando para `appCmdLine()`. Com o patch, `-server` chega ao `main`, que faz `GIsClient = 0` (sem janela nem renderização). | `Core.dll.orig` |
| `system\LandMass.exe` | `0x209E4` (133604) | `57` (`W`) | `58` (`X`) | Literal UTF-16 `WLog` (janela da instância já aberta) vira `XLog`. O repasse de linha de comando não acha a janela e a segunda instância segue o próprio caminho e grava o próprio log. | `LandMass.exe.orig` |

Conferência após aplicar (deve mostrar só esses bytes):

```
cmp -l system\Core.dll system\Core.dll.orig        # 2 bytes: 260551 e 260552
cmp -l system\LandMass.exe system\LandMass.exe.orig # 1 byte: 133605
```

Não foi aplicado patch em `LM_Engine.dll`. O patch mínimo em `LoginPlayer` (aceitar qualquer jogador) não teria efeito com os mapas atuais: `LoginPlayer` só é chamado por `UServerLevel::NotifyReceivedText`, e o nível da partida não é `UServerLevel` (ver `re/game_server_host.md`, seção 9).

### Não tocado

- `HShield` (`system\HShield`): nenhum arquivo alterado, removido ou desabilitado nesta cópia.

## Como iniciar

Execute `system\servidor.bat` (a janela fica aberta enquanto o servidor roda). A linha é:

```
LandMass.exe ONS-Treino?listen -server -log login_server=127.0.0.1:7313?version=<V>?login_num=<L>
```

- Argumentos do motor vêm ANTES de `login_server=`. Nas execuções de 2026-10-13, a linha montada com aspas duplas no PowerShell perdeu `login_num=` e o executável saiu com código 0, sem log (`re/game_server_host.md` §11.1). Qualquer token depois de `login_num=...` também pode fazer o executável sair com código 0, sem log (regra de §2 de `re/game_server_host.md`; não reverificada em 2026-10-13). Montada por concatenação, a linha sobe (validado em 2026-10-13: UDP 7777 aberta, `Game class is 'LM_DeathMatch'`, `Bringing Level ONS-Treino.myLevel up for play`).
- `version=` e `login_num=` são copiados de `cliente\system\jogar_teste.bat`. Sem eles o executável também sai com 0 (ver [`../../re/cmdline.md`](../../re/cmdline.md)).
- A partida DM não abre TCP para o Message Server (7313) nem para o Channel (7314) em 15 s, mesmo com `login_server=` apontando para um listener local (`re/game_server_host.md` §11.2).
- `-log` sem valor: o nome do arquivo de log segue o padrão do motor (`system\LandMass.log`). `-log=Server.log` não foi testado.
- Não rode o servidor dentro de `cliente` ou `cliente2`. Cada pasta tem seu próprio `LandMass.log` e `User.ini`.

## Porta

- Protocolo UDP, porta **7777** (`[URL] Port=7777` em `LandMass.ini`). O driver é `IpDrv.TcpNetDriver`, mas o socket é `SOCK_DGRAM` (ver `re/cmdline.md`, seção 2).
- Conferir com o servidor no ar:

```
netstat -ano -p UDP | findstr :7777
```

- Se o cliente estiver em outra máquina, liberar UDP 7777 no firewall do Windows para `LandMass.exe`.
- Com `LANDMASS_MATCH_SERVER_DIR` definido, cada partida lançada pelo emulador usa a porta da faixa `LANDMASS_MATCH_PORT_MIN..MAX` (`PORT=`), não 7777. O `servidor.bat` continua abrindo 7777.

## Como um cliente conecta

1. Subir o emulador conforme [`running-client.md`](running-client.md).
2. Subir o servidor de partida (`servidor.bat`) antes do cliente.
3. O 403 `NotifyStartGame` leva o endereço da partida, configurado no emulador:
   - Sem `LANDMASS_MATCH_SERVER_DIR`: `LANDMASS_GAME_HOST` e `LANDMASS_GAME_PORT` (padrão `127.0.0.1:7777`). A porta do 403 precisa ser a mesma do `servidor.bat`.
   - Com `LANDMASS_MATCH_SERVER_DIR`: `LANDMASS_GAME_HOST` e a porta da partida, lançada pelo emulador.
   Ver [`../architecture/05-configuration.md`](../architecture/05-configuration.md).
4. Iniciar o cliente de teste em `cliente2` com o `jogar_<usuário>.bat`. Criar sala, o dono inicia (401), o cliente recebe o 403 e tenta `127.0.0.1:7777`.

(Inferido: o cliente monta o `open` com o endereço e a porta do 403. A conexão real não foi observada.)

## O que conferir no log

Arquivo: `D:\landmass\servidor-partida\system\LandMass.log`, gravado no encerramento normal (ver [`running-client.md`](running-client.md)).

| Sinal | Significado |
|-------|-------------|
| Processo vivo e UDP 7777 em `netstat` | O servidor subiu. |
| `Game class is '...'` e `Bringing Level ... up for play` | Mapa carregado (padrão observado no cliente; a linha exata do servidor não foi observada). |
| `binding to port ... failed` (IpDrv) ou `Failed to listen` / `NetListen` (Engine) | A porta não abriu. |
| Saída em poucos segundos, sem `LandMass.log` | Aspas duplas no PowerShell perdem `login_num=` (monte por concatenação); token depois de `login_num=` (não reverificado); ou falta `login_server=`/`version=`/`login_num=`. Ponha os argumentos do motor no início. |
| Log de LOGIN recusado | A validação está na lógica UnrealScript (`XGame`), não em `LM_Engine.dll` (ver `re/game_server_host.md`). |

## Partida lançada pelo emulador (marco 4)

Com `LANDMASS_MATCH_SERVER_DIR`, o canal sobe um `LandMass.exe` por sala que inicia a partida e o encerra no fim (D46). Sem a variável, vale o `servidor.bat` com endereço fixo, como acima.

O equipamento de cada jogador vai para `LMEmu.ini`, na mesma pasta `system\`, em uma seção `[m<8 hex> LMEmuLoadout]` por partida. A seção é gravada antes do lançamento e tirada no fim, na falha de início e na queda (D190).

Pré-requisito: o pacote `LMEmu` precisa estar em `servidor-partida\system`. Gere-o a partir da raiz de `emulador\` com `uv run python unreal/build_lmemu.py --landmass D:/landmass`. O script compila com o UCC 3369 ajustado e copia `LMEmu.u` para essa pasta. Sem o pacote, a classe `LMEmu.*` não existe no motor (inferido, não testado).

Configuração (PowerShell, na raiz de `emulador\`). O valor de `login_num` vem do `jogar_teste.bat`; não o escreva em arquivo versionado:

```
$env:LANDMASS_MATCH_SERVER_DIR = "D:\landmass\servidor-partida\system"
$env:LANDMASS_MATCH_LOGIN_NUM = "<login_num do jogar_teste.bat>"
$env:LANDMASS_MATCH_PORT_MIN = "7800"
$env:LANDMASS_MATCH_PORT_MAX = "7899"
uv run landmass-emu serve
```

### Roteiro: uma partida com dois clientes

Pré-requisito: `servidor-partida` com os patches conferidos (ver acima) e duas contas. As contas são `ana` e `bia`, com `account create --user ana --nickname Ana` e `account create --user bia --nickname Bia`. Os `.bat` caem em `cliente\` e `cliente2\`.

| # | Ação | Esperado no emulador (`serve`) |
|---|------|-------------------------------|
| 1 | Subir o emulador com a configuração acima. | Sem erro na inicialização. |
| 2 | Abrir `cliente\jogar_ana.bat` e `cliente2\jogar_bia.bat`, entrar no canal 1. | Sem log de erro. Os dois veem um ao outro no lobby. |
| 3 | Ana cria sala DM em ONS-Treino, 2 vagas. | `[...] sala 1 criada: <nome>` |
| 4 | Bia entra na sala 1. | `[...] entrou na sala 1` |
| 5 | Bia marca pronto; Ana inicia. | `partida iniciada na sala 1`, depois `partida da sala 1: LMEmu.LMEmuDeathMatch pronta na porta UDP 7800`. |
| 6 | Conferir a porta: `netstat -ano -p UDP \| findstr :7800`. | Uma linha `UDP 0.0.0.0:7800` com o PID do `LandMass.exe` lançado. |
| 7 | Os clientes mostram a contagem (402 pronto do dono, D77) e entram em `127.0.0.1:7800`. | (Não confirmado: aceitar o 403 atrasado.) |
| 8 | Jogar até o fim. Cada cliente manda 500 ao sair da partida. | `partida da sala 1: servidor encerrado (porta 7800)`. Sala volta à espera e Bia fica sem pronto. |
| 9 | Conferir o histórico (com o emulador parado): `uv run python -c "import sqlite3; c=sqlite3.connect('data/landmass.db'); print(c.execute('select id, room_id, map_file, game_class, end_reason from matches').fetchall()); print(c.execute('select match_id, account_id, nickname, is_master, kills from match_players').fetchall())"` | Uma linha em `matches` (`ONS-Treino`, `LMEmu.LMEmuDeathMatch`, `exit_play`). Duas em `match_players` com `kills` nulo. |
| 10 | Cada cliente volta à sala e envia 311 para a sala 1. | Só quem entrou recebe 312, 314 e 317; o lobby não recebe nada de novo. |

Os logs do servidor de partida (`servidor-partida\system\LandMass.log`) só são gravados no encerramento normal do processo; enquanto ele roda o arquivo fica travado. Procure `Game class is 'LM_DeathMatch'` e `Bringing Level ONS-Treino.myLevel up for play`, que apareceram numa execução anterior. Com o LMEmu, procure as linhas do `LMEmuLoadout` (D190): `LMEmu: login ... recebe ...` por jogador com equipamento, e `LMEmu: login sem equipamento ...` para quem não tem morat no gate. A linha `Game class` com `LMEmu.LMEmuDeathMatch` não foi observada.

### Casos que devem falhar do jeito certo

| Caso | Como provocar | Esperado |
|------|---------------|----------|
| Faixa sem porta livre | `LANDMASS_MATCH_PORT_MIN=7800` e `MAX=7800`, com outro programa usando UDP 7800. | Ana recebe o erro "Não foi possível iniciar a partida. Tente novamente."; emulador: `partida da sala 1 não começou: nenhuma porta UDP livre na faixa configurada`. Sala continua em espera. |
| Servidor não abre a porta | `LANDMASS_MATCH_LOGIN_NUM=0` (o valor de teste que não sobe o servidor, re/game_server_host.md §5). | Erro igual ao anterior; emulador: `servidor de partida encerrou antes de abrir a porta`. |
| Servidor cai depois de pronto | Encerrar o `LandMass.exe` durante a partida. | `servidor de partida da sala 1 caiu sozinho`. Histórico com `end_reason = server_exit`. |

### Limites conhecidos

- A partida não foi jogada por agente. Os passos 5 a 10 dependem do cliente real.
- O equipamento (D190) não foi visto no jogo. Não há prova de que o `LMEmuLoadout` aplique as peças, e o gate do `selected_morats` do 401 é tratado como índice sem prova (`re/rooms.md` §5).
- Não há prazo próprio de partida. Se um cliente nunca manda 500 e o servidor não cai, a sala fica jogando até alguém sair.
- As métricas de jogador ficam nulas quando o log não traz o bloco `GameEnded` (D153, D154; `re/game_server_host.md` §11.4 e §11.7) (ver `04-persistence.md`, "Histórico de partidas").
- Salas e partidas em andamento são só de memória: reiniciar o emulador zera as salas.

## Riscos e pendências

- Não testado com cliente. Com `servidor.bat`, a UDP 7777 foi vista aberta (2026-10-13), mas o chamador de `ULevel::Listen` ainda não foi achado (ver `re/game_server_host.md`, seção 9). Se o servidor não abrir a porta, esse é o primeiro ponto a investigar.
- Com ou sem `LANDMASS_MATCH_SERVER_DIR`, o 401 consulta o mapa em `landmass.wdb` (`LANDMASS_CLIENT_DIR`). Sem o arquivo ou sem o mapa da sala, a partida não inicia (241000201).
- Saídas precoces (~20 ms, sem log) ainda sem causa comprovada; podem afetar o servidor.
- A conexão com o Channel (`GS_*`, `CServerRoom`) não está no caminho desta cópia. Um LOGIN recusado não vem do `LM_Engine.dll`.
- Os patches são binários de 2008 alterados à mão. Restaure com os arquivos `.orig` se algo se comportar de forma estranha.
- Log por partida: `LOG=partida-<porta>-<id>.log` antes de `-log` gera um arquivo por partida (verificado, `re/game_server_host.md` §11.5; D153). Os arquivos ficam em `system\`. O `LandMass.log` deixa de ser o log das partidas do emulador.
