# Bots nas partidas

Bots de DeathMatch e TeamDeathMatch no servidor de partida (`LandMass.exe`), com morat, apelido e peças
sorteados pelo emulador. Não há bot no emulador nem no cliente: o bot só existe no processo do servidor
de partida, e a sala do emulador conta só humanos. Decisões: D220 (configuração e linhas), D221 (sorteio),
D222 (mecanismo no motor), D223 (comandos do dono e vaga), D225 a D227 (rotas), D228 (sorteio por classe),
D229 (mínimo da partida e `/bot add`), D230 (velocidade do bot) e D231 (apelidos `[BOT]`).

## Como entram

Há três caminhos, todos com `LANDMASS_MATCH_SERVER_DIR`:

| Caminho | Como | Quando |
|---------|------|--------|
| Automático | `LANDMASS_MATCH_BOTS=N` (padrão 0). A URL leva `?MinPlayers=` com o mínimo entre N e o máximo da sala. O motor completa a partida até N jogadores, humanos incluídos. | Início da partida. |
| Comando do dono | `/bot add [0-9]` no chat. 0 a 7 vira o skill do motor; 8 e 9 viram 7; vazio vira 3. O mínimo sobe para `jogadores + bots + 1` (até o máximo da sala). | Durante a partida, se a sala não está cheia. |
| Vaga | Quando um humano entra com `NumPlayers + NumBots` no máximo, sai o bot mais recente. O mínimo passa a contar com o humano. `/bot remove` tira o bot mais recente e baixa o mínimo para `jogadores + bots`. | Entrada de humano e `/bot remove`. |

Com `LANDMASS_MATCH_BOTS` maior que 0, o dono inicia a partida sozinho, sem outro jogador pronto (D224).
Só o dono (apelido cujo hex é `Owner=`) usa os comandos; a mensagem não aparece para os outros jogadores.

## Formato no `LMEmu.ini`

Na seção da partida (`[m<8 hex> LMEmuLoadout]`, D190), junto com as linhas `Players=`:

```
Owner=<apelido do dono em hex>
Bots=?Name=[BOT] Maverick?Skill=3?Species=XGame.SPECIES_DefenderB?Morat=103000002?MainWeapon=XGame.LM_HeavyMachineGun_DB?MainWeaponId=201110002?SubWeapon=XGame.LM_GuidedMissileLauncher_DA?SubWeaponId=201080001?MeleeWeapon=XGame.LM_Hammer_AB?MeleeWeaponId=201090002?EtcWeapon1=XGame.LM_SmokeLauncher_AA?EtcWeapon1Id=201010007?EtcWeapon2=XGame.LM_GLauncher_AB?EtcWeapon2Id=201010002?EtcWeapon3=none?EtcWeapon3Id=0?Booster=XGame.LM_PartsDataBoosterC?BoosterId=203000003?Generator=XGame.LM_PartsDataGeneratorA?GeneratorId=202000001?Record=M_Defender02_0
```

- Uma linha `Bots=` por vaga da sala (`max_players`), para o `/bot add` ter apelido e morat sem repetir.
  O valor é sorteado no Python (`domain/bots.py`, D221): morat entre os do wdb cuja espécie tem registro
  de jogador no `MORATS.upl`.
- Apelido (D231): `[BOT] <apelido>`, com apelido de `BOT_NAMES` (128 palavras ASCII de até 10 caracteres,
  sem nome de pessoa). O sorteio não repete apelido na partida. O nome completo cabe em 16 bytes cp1252.
  O espaço chega ao motor sem conversão (`bot5-dm.log`: `LMEmu: bot [BOT] Maverick ...`), então não há
  troca para `_`. O ping do bot fica 0.
- Peças (D228): cada peça sai só de um candidato com a classe do morat (`class_allows`) e o slot da peça
  (`slot_of`). Sem candidato, `none` e id `0`. O `DefaultSet` do morat não entra no sorteio: no wdb real ele
  traz peças fora da classe ou do slot em 7 casos (Sniper `102000001` e `102000002`: lançadores de granada
  e de fumaça em slot que não é o da peça; SpecialA `105000001`: melee, booster e gerador cuja máscara não
  inclui a classe Special, 10000). Por isso o SpecialA sorteia `none` nessas três peças: nenhuma serve à classe.
- `Record=` é o registro de jogador da espécie, que dá a aparência. O motor cria o bot por esse nome.
- O booster e o gerador são dados (PartsData) e vão para o bot pelo `Parts`, antes da arma.

## Mecanismo no motor (`tools/unreal/LMEmu/Classes`)

- `LMEmuBots` (só servidor): lê as linhas e escolhe o apelido não usado na partida (`NextLine`). O motor
  pode entregar o controlador depois do `AddBot` (o time cria pelo roster): a linha pedida vai para a fila
  `Pending`, e quem chega primeiro leva a linha mais antiga (`ClaimNewest` ou `ClaimIfNew` no `RestartPlayer`).
  A reclamação grava nome, `bBot`, ping 0, skill e `FavoriteWeapon`.
- `LMEmuBots.Add` (D229) é o `/bot add` do chat e o disparo de teste. Chama o `AddBot` do jogo e, se der
  certo, põe `MinPlayers = min(jogadores + bots + 1, máximo)`. `Sync` (`MinPlayers = jogadores + bots`) roda no
  `/bot remove`, na vaga do `Login` e no `PostLogin` do humano.
- `LMEmuTeamDeathMatch.GetMinPlayers` devolve `MinPlayers`. O `LM_TeamGame` arredonda o mínimo para par
  (código lido no XGame; o efeito não foi medido), o que criaria um bot a mais com total ímpar.
  Com 5 bots em TDM, a contagem ficou em 5 (`bot5-tdm.log`).
- Velocidade (D230): o `LM_WeaponBase.CalcPawnSpeedValues` do jogo volta cedo para pawn que não é de jogador
  humano, então o bot ficava com `GroundSpeed` 0. `LMEmuBots.Speed` faz a mesma conta com a arma, o booster
  e o gerador da linha (peso, força e agilidade), e roda depois do `RestartPlayer`.
- `AddBot` (em `LMEmuDeathMatch` e `LMEmuTeamDeathMatch`) chama o `AddBot` do jogo com o registro de jogador,
  não com o roster do UT2004 (`Jakob` etc. não existem no LandMass).
- O equipamento do bot entra pelo `AddDefaultInventory` do jogo (`Equip`), por `NewCreateInventory` de cada
  classe da linha. O do pawn não serve ao bot, porque lê o `PlayerController` do humano.
- `LMEmuBroadcast` fica na frente da cadeia de `BroadcastHandler` e trata `/bot` (D223).
- `LMEmuRecorder` (`bRecord=True`): grava posições e, a cada 10 s, uma linha `LMEmu: contagem` com jogadores,
  bots, mínimo e máximo. `TesteAdd=N` (só para teste, padrão 0) faz N `/bot add` aos 15 s pelo mesmo `Botset.Add`.

## Verificado (servidor headless, sem cliente)

Portas 7880 a 7890, `ONS-AirPort`, `?QuickStart=1`. Logs em `scratchpad\landmass-teste\servidor-partida\system`.

Velocidade (D230):

| Log | Estado | Bots | `gs` (GroundSpeed) | `vxy` | `bd` / `gd` (booster e gerador) | Posição |
|-----|--------|------|--------------------|-------|-----------------------------|---------|
| `base-b.log` | antes | 4 | 0,00 | 0,00 | False / False | parados |
| `bot-d.log` | depois | 4 | 248 a 275 | até 458 | True / True | andam 583 a 1991 uu em 30 s; rota `1084` e `2391` |

Mínimo da partida e `/bot add` (D229), sem humano:

| Log | Estado | Início | Adds | Contagem |
|-----|--------|--------|------|----------|
| `bot5-dm.log` | DM, `MinPlayers=5` | 5 | 0 | 5 de 0,5 s a 31,5 s; a partida acaba antes de 42 s |
| `bot5-tdm.log` | TDM, `MinPlayers=5` | 5 | 0 | 5 de 0,5 s a 42 s |
| `before-tdm5.log` | TDM, `LMEmu.u` do `HEAD` | 5 | 0 | 5 bots (Bot1 a Bot5) sem saída antes do fim |
| `bot3-c.log` | TDM, mínimo não sobe no add | 3 | 2 | 3 de 21 s a 42 s: os dois adds não ficam |
| `bot3-dm2.log` | DM, mínimo sobe `+1` | 3 | 2 | 3 para 5 em 21 s; 5 até 41 s |
| `bot3-tdm3.log` | TDM, mínimo sobe `+1` | 3 | 2 | 3 para 5 em 21 s; 5 até 42 s; fecha com `Closing by request` |

O `bot3-c.log` é a medição antes do `+1`: o `/bot add` roda, o motor não cria bot que fique e a contagem
fica em 3. O `HEAD` não tinha o teste de add; a comparação de partida inicial usa o `before-tdm5.log`.

Sorteio (D228, D231): `tests/test_bots.py` sorteia 200 sementes com 20 bots e confere, por peça, o slot e a
classe do morat (`class_allows`); o teste com o wdb real faz o mesmo com 30 sementes. Nomes: sem repetição na
partida, 16 bytes com o prefixo, sem caractere fora de ASCII. O prefixo `[BOT]` é recusado no cadastro
(`account create`) e no pedido de contato, sem diferenciar caixa (`tests/test_account.py`).

## Comportamento (D244 a D248)

- Combate: o motor do UT2004 (TacticalMove, RangedAttack, Charging) com personalidade e notas de arma do LMEmu.
- Caça e deslocamento: rota do mapa até onde está o inimigo, com penalidade nas arestas que travam e booster em trecho longo.
- Time: todo bot é freelance; nenhum segue o humano.
- Trava: o `LMEmuMarker` de cada bot chama o `WhatToDoNext` se o bot fica 4 s parado sem inimigo à vista (D248).
- Medição: `LMEmu: ia` no log (flags, personalidade e notas), `LMEmuRec` com `bRecord=True`.

## Avisos que sobram (motor, não bot)

| Aviso | Situação |
|-------|----------|
| `LM_xPawn.Setup:027B` `Accessed None 'PlayerReplicationInfo'`, dois por bot | O pawn chama `Setup` antes do possess, quando o PRI ainda não existe. Efeito: `eSpeciesType` do PRI não é gravado. Não há gancho sem trocar a classe do pawn. |
| `Class XGame.LM_AssaultRifle` not found | `FavoriteWeapon` do registro do `MORATS.upl`, lido em `InitBot` antes da reclamação. A `FavoriteWeapon` é trocada depois pela arma da linha. |
| `LM_TeamDeathMatch.InitGameReplicationInfo` `Teams` None | Já existe na partida sem bots. Não é de bot. |
| `CheckEndGame` e `ControlEndReason` `Winner` None | Já existe na partida sem bots. |
| `Class XGame.SPECIES_*C/D/E` not found | Registros do roster do UT2004, que o bot não usa. Já existiam antes. |

## Não verificado e limites

- A partida sem humano termina em cerca de 40 s pelo LastMan do LM (D243). Com bots, o `CheckLastMan` do LMEmu só encerra
  sem humano. Por isso os testes headless de contagem cobrem 40 s, não a partida inteira.
- Um `bot3-tdm2.log` (TDM com dois adds) parou depois do fim da partida e foi morto pelo harness. A repetição
  (`bot3-tdm3.log`) fechou normalmente. Não foi reproduzido.
- Bots criados pelo roster do motor, sem linha, saem da partida sozinhos (`bot saiu  reclamado False`, em
  DM e TDM, perto de t=11 s). Não foi explicado; eles não entram na contagem de bots com linha.
- `LM_TeamGame.RestartPlayer` destrói bot cujo time tem dois jogadores a mais (lido no XGame). Não apareceu
  nas execuções desta fase, e nada foi mudado para isso. Se aparecer, a correção é desligar `bBalanceTeams`
  só no respawn do bot.
- Chat `/bot add` real: o comando e a resposta não rodaram sem cliente. O disparo de teste usa o mesmo
  `Botset.Add`, mas não o caminho `AcceptBroadcastText`.
- Ordem de `CalcPawnSpeedValues` no jogador humano (D141): não testada sem cliente.
- Ping 0 do bot: gravado no PRI, mas o placar não foi visto.
- Recompensa: o bloco `GameEnded` por jogador só saiu com bots. O emulador casa por apelido, então um humano
  chamado `[BOT] ...` seria confundido. O prefixo reservado impede isso pelo cadastro.
- Símbolo de clã nos bots: não implementado (fora desta fase).

## Rotas (D225 a D227)

Os bots andam pela rota do mapa quando não têm inimigo. A rota vem da geometria, não de gravação de humanos.
Depois da correção de velocidade (D230), o bot anda pela rota (`bot-d.log`); antes ele ficava parado.

**Geração (`LMEmuBake`, D225).** Com `?lmemubake=1` na URL, o servidor de teste (sem bots) faz um flood-fill
a partir dos `PlayerStart` numa grade de 160 uu. Cada célula candidata é varrida de cima para baixo: o
piso vale se a normal Z é de pelo menos 0,7 e o ponto não tem água, volume de dano ou KillZ, e há folga de
teto e passagem pelo raio. Arestas: `w` andar (degrau até 40 uu), `f` queda (até 600 uu), `j` pulo (até a
altura do JumpZ, com alcance horizontal do GroundSpeed), `b` booster (até 500 uu). Sai ao terminar, com
`LMEmuBake fim`. O bake é fatiado por Timer (40 expansões por tick) e tem teto de 20000 nós.

Inicie o bake com a mesma linha de comando da partida (`hosting/command.py`), com
`<mapa>?listen?game=LMEmu.LMEmuDeathMatch?lmemubake=1`, por `subprocess` do Python. Iniciado pelo
`Start-Process` do PowerShell, o `LandMass.exe` sai na hora, sem log. Rotas geradas: só `ONS-AirPort`.
Use em `--mapa` o nome do mapa como na URL da partida.

**Arquivo (D226).** `tools/routes/rotas.py --log <log do bake> --mapa <mapa> --ini <LMEmuRoutes.ini>` lê
as linhas `LMEmuBake` e grava só a seção `[<mapa> LMEmuRoutes]`; as de outros mapas ficam. Imprime a
contagem por flag e se as bases (time 0 e time 1) se alcançam nos dois sentidos. Sem linhas de bake, o
script usa as `LMEmuRec` de `LMEmuRecorder` (`bRecord=True` no `LMEmu.ini`, complemento).

**Seguimento (D227).** `LMEmuRoutes` carrega `[<mapa> LMEmuRoutes]` no primeiro uso. O alvo do bot é a base
mais longe dele (nó mais próximo do centro dos `PlayerStart` de cada time), então ele vai e volta entre as
duas. O caminho é A* com custo de distância (`j` vale 2x, `b` 3x) e heurística de distância reta; o plano
fica guardado por bot e é refeito se o bot sai dele. Pulo só no chão, a até 150 uu do nó, pela aresta `j`.
Arestas `b` ficam fora do A* (`ROUTE_BOOST=false`) até o booster do bot ser ligado. Com inimigo, o squad
volta ao combate normal.

**Validação do bake em ONS-Airport (headless, sem cliente):**

- Bake (D248): 3239 nós e 19874 arestas (`w` 17738, `f` 1332, `j` 128, `b` 676). Termina em 32,5 s de jogo (99 s de
  processo, contando carga e saída). Teto não atingido. Nenhuma célula barrada por água (o teste é
  conservador: volume que toca a esfera do pawn conta).
- Conectividade: as bases se alcançam sem aresta `b` nos dois sentidos (63 e 59 passos). Sobram 32 nós alcançáveis
  sem volta, em fossos a z -9646. Das arestas `w` planas, 812 de 17164 não têm volta.
- Descartes do último bake: 1371 pisos sob teto, 15510 na passagem, 23 no meio do caminho de `w`.
- Partida só com bots, TDM (320 s): no 10x10, cada bot fica parado no máximo 3% do tempo e passa 4% a 34% do
  tempo na metade inimiga; no 2x2, de 15% a 26%. Os times se encontram no meio. Não houve avanço claro do time
  que mata mais (mortes e frente por janela de 30 s não andam juntas).

Não verificado nas rotas: pulo e booster em jogo (os limites são os do motor, não medidos com pawn), e as
tolerâncias do bake (folga, degrau, raio) sem conferência contra o cliente.

## Fora desta fase

Booster no seguimento de rota (aresta `b`), combate com a rota e Onslaught/OP/BR com bots (só DM e TDM).
