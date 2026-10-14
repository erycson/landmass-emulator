# Bots nas partidas

Bots de DeathMatch e TeamDeathMatch no servidor de partida (`LandMass.exe`), com equipamento e morat
sorteados pelo emulador. Não há bot no emulador nem no cliente: o bot só existe no processo do servidor
de partida, e a sala do emulador conta só humanos. Decisões: D220 (configuração e linhas), D221 (sorteio),
D222 (mecanismo no motor), D223 (comandos do dono e vaga) e D225 a D227 (rotas, seção própria).

## Como entram

Há três caminhos, todos com `LANDMASS_MATCH_SERVER_DIR`:

| Caminho | Como | Quando |
|---------|------|--------|
| Automático | `LANDMASS_MATCH_BOTS=N` (padrão 0). A URL leva `?MinPlayers=` com o mínimo entre N e o máximo da sala. O motor completa a partida até N jogadores, humanos incluídos. | Início da partida. |
| Comando do dono | `/bot add [0-9]` no chat. 0 a 7 vira o skill do motor; 8 e 9 viram 7; vazio vira 3. | Durante a partida, se a sala não está cheia. |
| Vaga | Quando um humano entra com `NumPlayers + NumBots` no máximo, sai o bot mais recente (`/bot remove` faz o mesmo). | Entrada de humano. |

Com `LANDMASS_MATCH_BOTS` maior que 0, o dono inicia a partida sozinho, sem outro jogador pronto (D224).

`/bot remove` tira o bot mais recente. Só o dono (apelido cujo hex é `Owner=`) usa os comandos; a
mensagem não aparece para os outros jogadores.

## Formato no `LMEmu.ini`

Na seção da partida (`[m<8 hex> LMEmuLoadout]`, D190), junto com as linhas `Players=`:

```
Owner=<apelido do dono em hex>
Bots=?Name=Bot1?Skill=3?Species=XGame.SPECIES_AssaultB?Morat=101000002?MainWeapon=XGame.LM_AssaultRifle_AB?MainWeaponId=201030002?SubWeapon=XGame.LM_BigGun_AC?SubWeaponId=201070003?MeleeWeapon=XGame.LM_SpecialMelee_SsA?MeleeWeaponId=201130001?EtcWeapon1=XGame.LM_SmokeLauncher_AA?EtcWeapon1Id=201010007?EtcWeapon2=XGame.LM_GLauncher_AB?EtcWeapon2Id=201010002?EtcWeapon3=none?EtcWeapon3Id=0?Booster=XGame.LM_PartsDataBoosterA?BoosterId=203000001?Generator=XGame.LM_PartsDataGeneratorB?GeneratorId=202000002?Record=M_Assault02_0
```

- `Bots=` tem uma linha por bot possível, sorteada no Python (D221): morat entre os do wdb cuja espécie
  tem registro de jogador no `MORATS.upl`; peças válidas para o morat, com `DefaultSet` de reserva.
- `Record=` é o registro de jogador da espécie, que dá a aparência. O motor cria o bot por esse nome.
- Classes de peça: a linha de `Item_Equip` cujo `item_id` é o id (munição do mesmo id fica de fora).
- O booster e o gerador são dados (PartsData) e vão para o PRI, não para o inventário.

## Mecanismo no motor (`tools/unreal/LMEmu/Classes`)

- `LMEmuBots` (só servidor): lê as linhas, dá o nome `Bot<k>` (contador de bots do lote), reclama o bot
  criado pelo `AddBot` do jogo (`ClaimNewest`), grava `PRI.bBot` verdadeiro e ping 0, o booster e o gerador
  no PRI, e a `FavoriteWeapon`.
- `AddBot` (em `LMEmuDeathMatch` e `LMEmuTeamDeathMatch`) chama o `AddBot` do jogo com o nome do registro,
  não com o roster do UT2004. Os nomes do roster (`Jakob`...) não existem no LandMass.
- O equipamento do bot entra pelo `AddDefaultInventory` do jogo, por `NewCreateInventory` de cada classe.
  O do pawn não serve ao bot, porque lê o `PlayerController` do humano.
- Depois do `RestartPlayer`: `SpawnBooster`, `SpawnGenerator` e `SwitchToBestWeapon`.
- `LMEmuBroadcast` fica na frente da cadeia de `BroadcastHandler` e trata `/bot` (D223).

## O que foi verificado (servidor headless, sem cliente)

Porta 7890, `TimeLimit=1`, `MinPlayers=3`. Logs em `servidor-partida\system`:

- Base (`bots-base.log`, código anterior, sem linha de bot): `Accessed None 'Controller'` em
  `LM_xPawn.AddDefaultInventory`, `Accessed null class context 'Species'` em `xPawn.Setup`,
  `PlayAnim: Sequence 'None' not found`, e `WhatToDoNext` sem arma (`bots-t1.log`, antes da correção).
- Com as linhas (`bots-t3.log`, `bots-dm.log`, `bots-dm2.log`, `bots-t4.log` com as linhas do Python):
  `LMEmu: bot Bot1 morat ... skill 3`, `LMEmu: bot Bot1 arma ...LM_AssaultRifle_AA`, e os três bots
  armados. Sem `Accessed None 'Controller'`, `Species` nem `PlayAnim`, e sem `WhatToDoNext` sem arma.
- `bots-t4.log` usa as linhas geradas pelo Python: morat de espécie B, gerador B, `EtcWeapon3=none`.
- A partida termina por tempo (`GameEnded` com as constantes) e fecha com `Closing by request`.

## Avisos que sobram (motor, não bot)

| Aviso | Situação |
|-------|----------|
| `LM_xPawn.Setup:027B` e `:0283` `Accessed None 'PlayerReplicationInfo'`, dois por bot | O pawn chama `Setup` antes do possess, quando o PRI ainda não existe. Efeito: `eSpeciesType` do PRI não é gravado. Não há gancho sem trocar a classe do pawn. |
| `Class XGame.LM_AssaultRifle` not found | `FavoriteWeapon` do registro do `MORATS.upl`, lido em `InitBot` antes da reclamação. A `FavoriteWeapon` é trocada depois pela arma da linha. |
| `LM_TeamDeathMatch.InitGameReplicationInfo` `Teams` None | Já existe na partida sem bots (`bots-base.log`). Não é de bot. |
| `CheckEndGame` e `ControlEndReason` `Winner` None | Já existe na partida sem bots. |
| `Class XGame.SPECIES_*C/D/E` not found | Registros do roster do UT2004, que o bot não usa. Já existiam antes. |

Uma execução de DeathMatch com bots (`bots-dm.log`) não processou o `exit` e precisou de kill. A repetição
(`bots-dm2.log`) fechou normalmente. O motivo não foi achado: é intermitente, e o emulador já derruba o
processo depois de 8 s (`EXIT_GRACE_SECONDS`), com o log possivelmente sem o trecho final.

## Rotas (D225 a D227)

Os bots andam pela rota do mapa quando não têm inimigo. A rota vem da geometria, não de gravação de humanos.

**Geração (`LMEmuBake`, D225).** Com `?lmemubake=1` na URL, o servidor de teste (sem bots) faz um flood-fill
a partir dos `PlayerStart` numa grade de 160 uu. Cada célula candidata é varrida de cima para baixo: o
piso vale se a normal Z é de pelo menos 0,7 e o ponto não tem água, volume de dano ou KillZ, e há folga de
teto e passagem pelo raio. Arestas: `w` andar (degrau até 40 uu), `f` queda (até 600 uu), `j` pulo (até a
altura do JumpZ, com alcance horizontal do GroundSpeed), `b` booster (até 500 uu). Sai ao terminar, com
`LMEmuBake fim`. O bake é fatiado por Timer (40 expansões por tick) e tem teto de 20000 nós.

Inicie o bake com a mesma linha de comando da partida (`hosting/command.py`), com
`<mapa>?listen?game=LMEmu.LMEmuDeathMatch?lmemubake=1`, por `subprocess` do Python. Iniciado pelo
`Start-Process` do PowerShell, o `LandMass.exe` sai na hora, sem log. Rotas geradas: só `ONS-Airport`.

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

**Validação em ONS-Airport (headless, sem cliente):**

- Bake: 2953 nós e 18420 arestas (`w` 16091, `f` 1151, `j` 511, `b` 667). Termina em 29,7 s de jogo (59 s de
  processo, contando carga e saída). Teto não atingido. Nenhuma célula barrada por água (o teste é
  conservador: volume que toca a esfera do pawn conta).
- Conectividade: as bases time 0 e time 1 estão no mesmo componente. Time 0 para time 1 em 79 passos; de
  time 1 para time 0 em 58.
- Descartes do último bake: 814 pisos sob teto, 13630 na passagem, 24 no meio do caminho de `w`.
- Teste de bot (TDM e DM, um bot, `?QuickStart=1`): o bot sai do nó 22 com plano até o nó 830 (base time 0),
  mas não se move. O `Assign` roda uma vez e o estado fica em `Roaming`. No DM nem chega a planejar. O log
  de posições (`LMEmuRec` com `bRecordBots`) fica parado em todas as amostras.

**Não verificado nesta fase:**

- O bot andando pela rota no servidor headless. O motor não tem fonte no repositório, e não foi possível
  confirmar por que o `Roaming` não move o pawn (a IA sem humano pode estar parada). Ver a próxima etapa.
- Pulo e booster em jogo. Os limites de pulo e de subida são os do motor (`JumpZ`, `GroundSpeed`, `Gravity`),
  não medidos com pawn.
- Tolerâncias do bake (folga, degrau, raio) sem conferência contra o cliente: o traço é pontual, então uma
  parede muito fina pode passar.

## Não verificado (exige cliente ou humano)

- Placar: o código do XInterface trata `bBot` (`LM_DMScoreBoardPage` e a linha de squad, com o ping
  em `4 * Ping`, que é 0 para bot). O que aparece na tela não foi visto.
- Chat `/bot`: o hook `AcceptBroadcastText` compila, mas nenhum jogador manda mensagem sem cliente.
- Vaga: a remoção de bot quando entra humano (`Login`) não roda sem humano.
- Recompensa: o bloco `GameEnded` por jogador só saiu com bots (nenhum humano); não há prova de que
  bot fica fora do bloco quando há humano. O emulador casa por apelido, então um humano chamado `Bot1`
  colidiria com o bot. Isto é um risco conhecido, sem tratamento nesta fase.
- Equipamento aplicado no combate: a arma foi selecionada, mas não se viu tiro nem dano.

## Fora desta fase

Booster no seguimento de rota (aresta `b`), combate com a rota e Onslaught/OP/BR com bots (só DM e TDM).
