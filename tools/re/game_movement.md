# Movimento na partida (LandMass, UE2 build 3369): engenharia reversa

Escopo: leitura estática, somente leitura. Fontes: `D:\landmass\cliente\system\` (`Engine.u`, `XGame.u`, `LM_Engine.u`, `Core.u`, `UTV2004.u`, `XEffects.u`, `XInterface.u`, `Engine.dll`, `LM_Engine.dll`, `LandMass.ini`, `User.ini`). Dumps gerados com `strs.py` ficam no scratchpad (`dump_*.txt`, `dll_*.txt`, `body_LM_*.txt`). O jogo não foi aberto, o MCP `rea` não foi usado, nenhum arquivo fora de `re\` e do scratchpad foi alterado.

Limitação do método: `strs.py` imprime todas as strings ASCII antes das UTF-16 (`U:`), e quebra a linha em caracteres não ASCII (comentários em coreano). Trechos reconstituídos a partir de fragmentos estão marcados como (inferido).

## 0. Resposta direta: o movimento autoritativo reaproveita o UE2?

**Parcial.**

- **Física e colisão: reaproveitado (UE2 nativo).** `Engine.dll` exporta `AActor::physWalking`, `AActor::physFalling`, `APawn::physWalking`, `APawn::physFalling`, `AActor::moveSmooth`, `ULevel::MoveActor` e `execAutonomousPhysics@AActor`. `LM_Engine.dll` **importa** `?physWalking@AActor` e `?physFalling@AActor` do `Engine.dll` (tabela de imports) e **não exporta nenhum símbolo de movimento** (460 exports, nenhum `physWalking`, `ServerMove` ou `SetMovement`). O `LM_Engine.dll` não sobrescreve física.
- **Protocolo de predição e correção: reaproveitado (UE2 em UnrealScript).** `PlayerController.ReplicateMove`, `ServerMove`, `MoveAutonomous`, `SendClientAdjustment`, `ClientUpdatePosition` e `LongClientAdjustPosition` estão em `Engine.u` com a lógica padrão. `ServerMove` não é nativo: a linha `//native function ServerMove(...)` está comentada em `Engine.u · PlayerController`, e `Engine.dll` não exporta `execServerMove`.
- **Substituído pela LandMass (lógica própria):**
  1. **Posição e velocidade de pawn humano vêm do cliente.** `XGame.u · LM_xPawn.AutonomousPhysics` chama `SetMovement(NewLocation, NewRotation, NewPhysics)` e `Velocity = NewVelocity` quando `IsHumanControlled()` e `Level.NetMode != NM_Client`. Os valores vêm de `LM_xPawn.ServerUpdateMovement`, que o cliente envia em `LM_xPlayer.CallServerMove`. `SetMovement` é `native` em `Engine.u · LM_Pawn` e implementado em `Engine.dll` como `execSetMovement@ALM_Pawn`.
  2. **Booster próprio.** `Engine.u · LM_BoosterBase.Tick` altera `Pawn.GroundSpeed`, `AirSpeed` e `WaterSpeed`, e consome `fBoosterRemains`.
  3. **Classes LM de pawn e enum estendido.** `Engine.u` contém `class LM_Pawn extends Pawn` e `class LM_BoosterBase extends Actor`, e o enum `EPhysics` inclui `PHYS_Boosting`. O motor deste build foi estendido pela LandMass, e a parte LM de pawn está compilada em `Engine.dll`.
- **Autoridade: parcial.** Para humanos, o servidor aceita a posição e a velocidade do cliente. Ainda valida tempo (`CheckSpeedHack`) e contagem de chaff, mas não reavalia a ativação do booster. Ver seção 4.

## 1. Pipeline de rede do movimento (UE2 deste build)

### 1.1 RPCs de movimento

| Função | Sentido e tipo | Evidência |
|---|---|---|
| `ServerMove(float TimeStamp, vector InAccel, vector ClientLoc, bool NewbRun, bool NewbDuck, bool NewbJumpStatus, bool NewbDoubleJump, eDoubleClickDir DoubleClickMove, byte ClientRoll, int View, optional byte OldTimeDelta, optional int OldAccel)` | cliente para servidor, `unreliable` | `Engine.u · PlayerController`, replication: `unreliable if( Role<ROLE_Authority ) ServerUpdatePing, ShortServerMove, ServerMove, RocketServerMove;` |
| `ShortServerMove`, `DualServerMove`, `RocketServerMove`, `TurretServerMove`, `SpaceFighterServerMove` | cliente para servidor, `unreliable` | mesmo bloco |
| `ClientAdjustPosition(TimeStamp, newState, newPhysics, NewLocX/Y/Z, NewVelX/Y/Z, NewBase)` | servidor para cliente, `unreliable` | `Engine.u · PlayerController`, replication: `unreliable if( Role==ROLE_Authority ) ... ClientAdjustPosition, ShortClientAdjustPosition, VeryShortClientAdjustPosition, LongClientAdjustPosition;` |
| `ShortClientAdjustPosition(TimeStamp, newState, newPhysics, NewLocX/Y/Z, NewBase)` | servidor para cliente, `unreliable` | chamado em `Engine.u · PlayerController.SendClientAdjustment` quando `NewVel == vect(0,0,0)` |
| `VeryShortClientAdjustPosition` | servidor para cliente, `unreliable` | `Engine.u · PlayerController.VeryShortClientAdjustPosition`: chama `LongClientAdjustPosition(TimeStamp,'PlayerWalking',PHYS_Walking,...,0,0,0,...)` |
| `LongClientAdjustPosition(TimeStamp, newState, newPhysics, NewLocX/Y/Z, NewVelX/Y/Z, NewBase, NewFloorX/Y/Z)` | servidor para cliente, `unreliable` | `Engine.u · PlayerController.SendClientAdjustment`: usado quando `Pawn.Physics == PHYS_Spider` |
| `ClientAckGoodMove` | não existe | nenhum hit em dumps, DLLs ou `xinterface_strs.txt` |

Buffer de movimento: `Engine.u · class SavedMove extends Info;` (linha 22796). `PlayerController` declara `var SavedMove SavedMoves, FreeMoves, PendingMove;` (`Engine.u`, linhas 24529-24531).

### 1.2 Cliente: predição local

`Engine.u · PlayerController.ReplicateMove(float DeltaTime, vector NewAccel, eDoubleClickDir DoubleClickMove, rotator DeltaRot)`:
1. `NewMove = GetFreeMove(); NewMove.SetMoveFor(self, DeltaTime, NewAccel, DoubleClickMove);`
2. `ProcessMove(NewMove.Delta, NewMove.Acceleration, NewMove.DoubleClickMove, DeltaRot);` faz a predição local com a lógica do `PlayerWalking`, que o LM sobrescreve (seção 2).
3. `Pawn.AutonomousPhysics(NewMove.Delta);` No cliente cai no `super.AutonomousPhysics` nativo, porque o ramo LM só roda com `NetMode != NM_Client`.
4. Enfileira em `SavedMoves` e tenta fundir com `PendingMove` quando a aceleração muda pouco (`Dot > 0.99`).

`CallServerMove` recebe `ClientLoc` como parâmetro e envia o pacote (`Engine.u · PlayerController.CallServerMove`). (inferido: `ClientLoc` é `Pawn.Location` do cliente no momento do envio.)

### 1.3 Servidor: recálculo e tolerância

`Engine.u · PlayerController.ServerMove`:
- Descarta replay: `if ( CurrentTimeStamp >= TimeStamp ) return;`
- Descarta sem pawn reconhecido: `if ( AcknowledgedPawn != Pawn ) return;`
- Anti-speedhack (nativo, `Engine.dll · ENGINE_CheckSpeedHack`): `else if ( !CheckSpeedHack(DeltaTime) ) { bWasSpeedHack = true; DeltaTime = 0; Pawn.Velocity = vect(0,0,0); }`
- `DeltaTime = FMin(MaxResponseTime, TimeStamp - CurrentTimeStamp);` e depois `MoveAutonomous(DeltaTime, NewbRun, NewbDuck, NewbPressedJump, NewbDoubleJump, DoubleClickMove, Accel, DeltaRot)` (só se `Level.Pauser == None && DeltaTime > 0`).
- `MoveAutonomous` chama `ProcessMove` e depois `Pawn.AutonomousPhysics(DeltaTime)` (`Engine.u · PlayerController.MoveAutonomous`).

**Tolerância de posição** (trecho de `ServerMove`):
```
if ( ClientLoc == vect(0,0,0) ) return;
else if ( Level.TimeSeconds - LastUpdateTime > 0.3 ) ClientErr = 10000;
else if ( Level.TimeSeconds - LastUpdateTime > 180.0/Player.CurrentNetSpeed ) { LocDiff = Pawn.Location - ClientLoc; ClientErr = LocDiff Dot LocDiff; }
if ( ClientErr > 3 ) { ... PendingAdjustment ...; LastUpdateTime = Level.TimeSeconds; }
```
- A tolerância é o **literal `3` sobre o quadrado da distância** (`LocDiff Dot LocDiff`), cerca de 1,7 UU.
- `MAXPOSITIONERRORSQUARED` e `ClientErrorTime` não existem neste build (nenhum hit em `Engine.u`).
- Correção forçada: se não houve correção há mais de 0,3 s, a próxima checagem força `ClientErr = 10000`. `LastUpdateTime` é atualizado só no ramo de correção (`Engine.u`, linha 26105) e na morte (linha 25723).
- Envio: `event SendClientAdjustment()`, no máximo uma vez por tick. Escolhe `ShortClientAdjustPosition` (sem velocidade), `ClientAdjustPosition` (com velocidade) ou `LongClientAdjustPosition` (spider).

### 1.4 Cliente recebe a correção

- `Engine.u · PlayerController.LongClientAdjustPosition`: descarta se `CurrentTimeStamp >= TimeStamp`, aplica `NewLocation`/`NewVelocity` e chama `ClientUpdatePosition()`.
- `Engine.u · PlayerController.ClientUpdatePosition()`: descarta `SavedMoves` com `TimeStamp <= CurrentTimeStamp` e reexecuta os restantes com `MoveAutonomous(CurrentMove.Delta, ...)` (replay).
- `bDynamicNetSpeed` (`User.ini`, `[Engine.PlayerController]`, linha 243 = `True`): em `LongClientAdjustPosition`, aumenta `Level.MoveRepSize` em 8 até 64; depois reduz `NetSpeed` em 1000 se `>= 6000`.

## 2. Overrides LM (classes LM_*): o que muda e como dispara

Cadeia de herança verificada nos dumps. Controller: `LM_xPlayer` (`XGame.u`, linha 26178: `class LM_xPlayer extends xPlayer`) → `xPlayer` (`XGame.u`, linha 12308: `class xPlayer extends UnrealPlayer`) → `UnrealPlayer` (`WPGames.u`, linha 11840: `class UnrealPlayer extends LM_PlayerController`) → `LM_PlayerController` (`Engine.u`, linha 37083: `class LM_PlayerController extends PlayerController`; sem funções de movimento, só config de AFK) → `PlayerController`. Pawn: `LM_xPawn` (`XGame.u`, linha 28292: `class LM_xPawn extends xPawn`) → `xPawn` (`XGame.u`, linha 13091: `class xPawn extends UnrealPawn`) → `UnrealPawn` (`WPGames.u`, linha 12359: `class UnrealPawn extends LM_Pawn`) → `LM_Pawn` (`Engine.u`, linha 37219: `class LM_Pawn extends Pawn`) → `Pawn` → `Actor`. Consequência: `LM_PlayerController(Pawn.Controller)` em `LM_BoosterBase.DeaccelBooster` resolve para o `LM_xPlayer`, então o ajuste de FOV roda para humanos; e `SetMovement` (nativo em `LM_Pawn`) é alcançado pela cadeia de `LM_xPawn`. `LM_BoosterBase extends Actor` (`Engine.u`, linha 37574). `LM_TeamGame` e `LM_TeamOperation` (`XGame.u`) não tocam física: a única ocorrência de movimento é `MoveToFailStartPoint()`, do tutorial. Não há `LM_*.u` separado para pawn: `LM_Pawn` e `LM_BoosterBase` estão dentro de `Engine.u`.

| Ação | Disparo (função/exec) | Roda em | Caminho e autoridade | Replicação |
|---|---|---|---|---|
| **Booster: ativar** | `XGame.u · LM_xPawn.EnableBooster` (exec, linha 29187): `if(ClientState != WS_ReadyToFire) return; super.EnableBooster();` | cliente checa; servidor executa o RPC | `Engine.u · LM_Pawn.EnableBooster` (exec): retorna se `fBoosterRemains < fCanBoostAmount`, `VSize(Acceleration) == 0`, `bIsWalking`, `bIsCrouched` ou `Physics == PHYS_Falling`; senão chama `ServerEnableBooster()`. No servidor, `ServerEnableBooster` chama `Booster.EnableBooster()` só em `NM_DedicatedServer` e depois `ClientEnableBooster()` (inferido: em listen server o efeito passa por `ClientEnableBooster`) | `Engine.u · LM_Pawn.replication`: `reliable if(Role < ROLE_Authority) ServerEnableBooster, ServerDisableBooster;` e `reliable if(Role == ROLE_Authority) ClientEnableBooster, ClientDisableBooster;` |
| **Booster: desativar** | `exec DisableBooster()` (`LM_Pawn`) → `ServerDisableBooster()` | idem | `LM_BoosterBase.DisableBooster`: `if(Role == ROLE_Authority) bIsEnabled = false;` | idem |
| **Booster: efeito de velocidade** | `event Tick(float DeltaTime)` em `Engine.u · LM_BoosterBase` (linha 37762) | ambos (Actor, inferido) | Se `bIsEnabled`: `Pawn.GroundSpeed = Pawn.fDefaultGroundSpeed + fAccelRate` (e Air/Water). Se `fBoosterRemains > 0 && VSize(Pawn.Acceleration) > 0 && !bIsWalking && !bIsCrouched`: `fBoosterRemains -= GetDeclaireAmount(Pawn) * DeltaTime` (`heat_power`); senão `Pawn.DisableBooster()`. Recarga com `heat_charge`. `DeaccelBooster` (cliente) reduz a velocidade e ajusta FOV via `PC.SetFOV` | `Engine.u · LM_BoosterBase.replication`: `reliable if(bNetDirty && Role==ROLE_Authority) bIsEnabled, fBoosterRemains;` e `unreliable if(bNetInitial && Role==ROLE_Authority) fAccelRate, fDeaccelRate, fCanBoostAmount, fBoosterIncRate, fDefaultAccelRate;` |
| **Booster: atalho** | `User.ini`, `[Engine.Input]`, linha 43: `Aliases[34]=(Command="EnableBooster\|OnRelease DisableBooster",Alias=BoosterInput)` | cliente | | |
| **Chaff** | `XGame.u · LM_xPlayer.ChaffFire` (exec, linha 28057): checa `bChaffFire` e `m_nChaffCount`, toca som; se `Level.NetMode != NM_DedicatedServer` chama `ServerChaffFire()`; depois `bChaffFire = true` | cliente decide; servidor cria | `XGame.u · LM_xPlayer.ServerChaffFire` (linha 28030): `if( m_nChaffCount <= 0 ) return;` depois `SpawnProjectile(StartProj, Aim)` (spawna `LM_ChaffLauncherDam`), `ClientChaffFire(StartProj, Aim)` e `m_nChaffCount--` | `XGame.u · LM_xPlayer.replication`: `reliable if(Role < ROLE_Authority) ... ServerChaffFire ...;` e `reliable if(Role == ROLE_Authority) ClientChaffFire, m_nChaffCount, ...;` |
| **Chaff: atalho** | `User.ini`, `[Engine.Input]`, linha 100: `Q=ChaffFire` | cliente | | |
| **Pulo e pulo duplo** | `bPressedJump` → flags `NewbJumpStatus` / `NewbDoubleJump` em `ServerMove` → `XGame.u · LM_xPlayer.ProcessMove` (estado `PlayerWalking`, linha 28171): `if(bDoubleJump && (bUpdating || Pawn.CanDoubleJump())) Pawn.DoDoubleJump(bUpdating); else if(bPressedJump) Pawn.DoJump(bUpdating);` | predição no cliente e execução no servidor | `DoJump` e `DoDoubleJump` são do `xPawn` (`XGame.u`, linhas 14720 e 14733). **LM_xPawn não sobrescreve `DoJump`**: a linha `//function bool DoJump( bool bUpdating )` está comentada (`XGame.u`, linha 29587) (inferido: o corpo que segue é fragmento do bloco comentado) | sem RPC próprio: usa as flags de `ServerMove` |
| **Esquiva (dodge)** | Duplo clique (`DoubleClickMove`) → `XGame.u · xPawn.Dodge(eDoubleClickDir)` (linha 14651) → `PerformDodge` (linha 14690) | ambos | **LM não sobrescreve** `PerformDodge` (nenhuma definição em `body_LM_xPawn.txt`) | sem RPC próprio |
| **Knockback / velocidade externa** | `XGame.u · LM_xPawn.AddVelocity` (linha 31017): `if(Role == ROLE_Authority) ClientAddVelocity(NewVelocity);` e aplica `Velocity += NewVelocity` | servidor decide; cliente aplica | `SetPhysics(PHYS_Falling)` se o pawn estava em `PHYS_Walking` com `VSize >= 100` | `XGame.u · LM_xPawn.replication`: `reliable if(Role == ROLE_Authority) ClientAddVelocity, g_instigatedBy, isTeamGame;` |
| **Movimento próprio: autoridade de posição** | `XGame.u · LM_xPlayer.CallServerMove` (linha 28124): `LM_xPawn(Pawn).ServerUpdateMovement(Pawn.Location, Pawn.Rotation, Pawn.Velocity, Pawn.Physics);` antes de `super.CallServerMove(...)` | cliente envia; servidor aplica | `XGame.u · LM_xPawn.ServerUpdateMovement(CurLocation, CurRotation, CurVelocity, CurPhysics)` (linha 30951) guarda os valores; `LM_xPawn.AutonomousPhysics` (linha 30963) aplica `SetMovement` (seção 4) | `XGame.u · LM_xPawn.replication` (linha 28456): `reliable if(Role < ROLE_Authority) ServerUpdateMovement, ServerJumpOffPawn, ServerFellOutOfWorld, ServerTakeDamage;` |
| **Correção de posição no LM** | `XGame.u · LM_xPlayer.LongClientAdjustPosition` (linha 27421, dentro de `state RoundEnded`): se `PlayerReplicationInfo.bOnlySpectator` e modo de operação LM, `GotoState(newState)`; senão `super` | cliente | não altera física do pawn; em `PlayerWalking` vale o GLOBAL do `PlayerController` | |
| **Movimento de espectador** | `XGame.u · LM_xPlayer.PlayerMove` nos estados `BehindCamera` (linhas 26714, 26794), `CinematicCamera` (26928) e `FixedCamera` (27053) | cliente | só câmera e espectador, não pawn | |

**Overrides por classe e estado** (parser de chaves sobre `Engine.u`, `WPGames.u` e `XGame.u`, em `scratchpad\state_ctx.py`; ver nota da seção 6):
- `CallServerMove`: `LM_xPlayer` define a versão `GLOBAL` (`XGame.u`, linha 28124). Na cadeia, `PlayerController` (`Engine.u`) tem a versão GLOBAL e versões por estado só em `PlayerSpaceFlying`, `PlayerRocketing` e `PlayerTurreting`. `UnrealPlayer`, `xPlayer` e `LM_PlayerController` não definem. **Em `PlayerWalking` não há versão de estado em nenhuma classe**, então a `GLOBAL` do `LM_xPlayer` é a que roda ao andar.
- `ServerMove`, `ReplicateMove`, `MoveAutonomous`, `SendClientAdjustment`, `ClientUpdatePosition`: só `PlayerController` (`Engine.u`), com versões de estado para espectador, morte e fim de rodada (`Dead`, `RoundEnded`, `GameEnded`). Nenhum override LM.
- `ProcessMove` em `PlayerWalking`: `PlayerController` (`Engine.u`, linha 118004) → `UnrealPlayer` (`WPGames.u`) → `LM_xPlayer` (`XGame.u`, linha 28171). A versão LM é a final.
- `LM_xPlayer.LongClientAdjustPosition` (`XGame.u`, linha 27421) está dentro de `state RoundEnded`: fora desse estado vale o `PlayerController.LongClientAdjustPosition` GLOBAL (inferido: escopo atribuído pelo parser de chaves).
- `PerformDodge`, `Dodge`, `DoJump`, `DoDoubleJump`, `CanDoubleJump`: definidos em `xPawn` (`XGame.u`) e em `UnrealPawn` (`WPGames.u`, só `Dodge`/`PerformDodge`) e `Pawn` (`Engine.u`). **`LM_xPawn` não define nenhum deles** (a linha `//function bool DoJump` está comentada).
- Overrides LM de pawn confirmados (GLOBAL): `LM_xPawn.AutonomousPhysics`, `ServerUpdateMovement`, `SetPhysics`, `TakeFallingDamage`, `Landed`, `AddVelocity`.

**`LM_xPlayer.ProcessMove` (estado `PlayerWalking`, linha 28171):** o trecho lido copia o `PlayerWalking` padrão: grava `Pawn.Acceleration = NewAccel`, trata pulo, agachamento e `SetViewPitch`. (inferido: o restante do corpo não foi lido.)

## 3. Pawn replicado para os outros jogadores

- **Actor (UE2, sem override LM):** `Engine.u · Actor.replication`: `unreliable if((!bSkipActorPropertyReplication || bNetInitial) && bReplicateMovement && (((RemoteRole == ROLE_AutonomousProxy) && bNetInitial) || ((RemoteRole == ROLE_SimulatedProxy) && (bNetInitial || bUpdateSimulatedPosition) && ...) || ...)) Location;`. O mesmo padrão vale para `Rotation` (DrawType mesh), `Base`, `RelativeLocation/Rotation`, `AttachmentBone` e `Velocity` (SimulatedProxy com `bUpdateSimulatedPosition`, ou DumbProxy caindo). `Physics` vem depois, truncado no dump.
- **Pawn (UE2):** `Engine.u · Pawn.replication`: `reliable if( bNetDirty && (Role==ROLE_Authority) ) bSimulateGravity, bIsCrouched, bIsWalking, PlayerReplicationInfo, AnimAction, HitDamageType, ...` (lista truncada no dump).
- **LM_Pawn (customizado):** `Engine.u · LM_Pawn.replication`: `reliable if(Role == ROLE_Authority) Booster;`; `reliable if(Role == ROLE_Authority) fDefaultGroundSpeed, fDefaultAirSpeed, fDefaultWaterSpeed, fAirSpeedPct, fWaterSpeedPct;`; RPCs de booster listados na seção 2.
- **LM_BoosterBase (customizado):** `bIsEnabled` e `fBoosterRemains` confiáveis quando `bNetDirty`; constantes de booster `unreliable` na criação.
- **LM_xPawn (customizado):** `ClientAddVelocity`, `g_instigatedBy`, `isTeamGame` (servidor para cliente); `ServerUpdateMovement`, `ServerJumpOffPawn`, `ServerFellOutOfWorld`, `ServerTakeDamage` (cliente para servidor, todos `reliable`). `XGame.u`, linhas 28438-28461.
- **Localização, rotação e velocidade de jogador remoto:** vêm do Actor UE2 sem override LM (nenhum `Location` ou `Velocity` nos blocos `replication` de LM_Pawn e LM_xPawn). (inferido) A interpolação do jogador remoto é nativa e não foi lida.
- `native nativereplication;` em `LM_Pawn` e `LM_BoosterBase` (`Engine.u`): parte da replicação passa por código C++ (inferido: não lido em `Engine.dll`).

## 4. Autoridade

**Parcial.** Para pawn humano, o servidor aceita posição, rotação e velocidade enviadas pelo cliente. Para bots (não `IsHumanControlled`), o servidor recalcula com física nativa (inferido).

Caminho principal:
1. `XGame.u · LM_xPlayer.CallServerMove`: envia `ServerUpdateMovement(Pawn.Location, Pawn.Rotation, Pawn.Velocity, Pawn.Physics)` (confiável) antes do `ServerMove`.
2. `XGame.u · LM_xPawn.AutonomousPhysics`: `if( Level.NetMode != NM_Client && Level.NetMode != NM_Standalone && ... && IsHumanControlled() ) { SetMovement(NewLocation, NewRotation, NewPhysics); Velocity = NewVelocity; } else super.AutonomousPhysics(DeltaSeconds);`
3. `Engine.u · PlayerController.MoveAutonomous` chama `Pawn.AutonomousPhysics(DeltaTime)`, e `ServerMove` chama `MoveAutonomous`.

Sombreamento: `CallServerMove` não tem versão em `PlayerWalking` (seção 2), e `ServerUpdateMovement` e `AutonomousPhysics` são GLOBAL em `LM_xPawn`. Então o caminho acima é o que roda ao andar, e não há override de estado que o desvie.

Consequências:
- **A correção de posição quase nunca dispara para humanos (inferido).** O teste `ClientErr > 3` roda depois de `MoveAutonomous` no `ServerMove`. `Pawn.Location` já foi sobrescrito por `SetMovement`, então a diferença fica perto de zero. A correção ainda ocorre: (a) pela correção forçada após 0,3 s sem correção; (b) quando `DeltaTime == 0` (speed hack, então `SetMovement` não roda); (c) quando `ServerUpdateMovement` chega atrasado ou fora de ordem em relação ao `ServerMove` (RPC confiável e unreliable não têm ordem garantida).
- **O servidor valida:** `CheckSpeedHack(DeltaTime)` (nativo, `Engine.dll · ENGINE_CheckSpeedHack`); `m_nChaffCount <= 0` em `LM_xPlayer.ServerChaffFire`; `AcknowledgedPawn == Pawn` em `ServerMove`.
- **O servidor não valida:** posição e velocidade de humanos (acima). A ativação do booster: `Engine.u · LM_Pawn.ServerEnableBooster` chama `Booster.EnableBooster()` sem reavaliar `fBoosterRemains` nem `VSize(Acceleration)`, e `LM_BoosterBase.EnableBooster` só testa `Role == ROLE_Authority`. A aceleração do cliente (`InAccel`) vai direto para `Pawn.Acceleration` no `ProcessMove`.
- **Bots:** `AutonomousPhysics` nativo recalcula a partir da aceleração (inferido).

**Menor mudança para o servidor confiar no cliente:** ele já confia. Não precisa de mudança. Para o inverso (servidor autoritativo), a mudança mínima é de script: remover o ramo `IsHumanControlled()` de `LM_xPawn.AutonomousPhysics` em `XGame.u`, caindo sempre em `super.AutonomousPhysics`, e deixar de enviar `ServerUpdateMovement`. Isso exige recompilar `XGame.u`. Nenhuma chave de `.ini` controla isso: `bClientSideMovement` não existe em nenhum `.u`, `.dll` ou `.ini` deste build.

**Chaves de `.ini` relevantes** (`D:\landmass\cliente\system\`):

| Chave | Valor | Seção | Arquivo e linha | Efeito |
|---|---|---|---|---|
| `MaxClientRate` | 15000 | `[IpDrv.TcpNetDriver]` | `LandMass.ini` 201 | limite de banda do cliente (inferido) |
| `NetServerMaxTickRate` | 20 | `[IpDrv.TcpNetDriver]` | `LandMass.ini` 207 | taxa de ticks de rede do servidor (inferido: frequência de `ServerMove` e ajustes) |
| `LanServerMaxTickRate` | 35 | `[IpDrv.TcpNetDriver]` | `LandMass.ini` 208 | o mesmo, em LAN |
| `MaxClientRate` / `NetServerMaxTickRate` | 25000 / 30 | `[Engine.DemoRecDriver]` | `LandMass.ini` 238 / 247 | só gravação de demo (inferido pelo nome da seção) |
| `bDynamicNetSpeed` | `True` | `[Engine.PlayerController]` | `User.ini` 243 | ajusta `MoveRepSize` e `NetSpeed` (seção 1.4) |
| `MaxPlayers` | 16 | `[Engine.GameInfo]` | `LandMass.ini` 444 | não afeta movimento |

## 5. Entrada na partida (só nomes; o endereço do Game Server é de outro agente)

- `XInterface.u · LM_Connection.OnConnect(GUIComponent Sender)` (classe `LM_Connection extends GUIPage`): monta `open <ip>?name=<nick>?sex=<Male|Female>?character=<M_|F_><tipo>01_<0?team=0|1?team=1>` e chama `PlayerOwner().ConsoleCommand(url)`. É a função que inicia a conexão à partida. O prefixo de IP fixo na string fica com o outro agente.
- `XInterface.u · LM_GUIController`: `ConsoleCommand("open tutorial?Game=xGame.LM_Tutorial?Tuto=N")` (tutorial local).
- `XInterface.u · ExtendedConsole` (estende `Console`): `ViewportOwner.Actor.ClientTravel(URL$"?password="$...)`.
- Formato `?name=`, `?key=`, `?team=`, `?voice=`, `?SpectatorOnly=1`: strings em bytecode de `XInterface.u`, sem fonte. A função dona não foi identificada.
- Login de conta (Message Server, não a partida): `XInterface.u · LM_LoginComponent.LogIn()` chama `LM_ServerInterfacePage.NetLogin(id, pw, false)`; `LM_TempLoginPage.InternalOnClick` chama `NetLogin`; `NetGuidLogin` em `XInterface.u`; `LM_Engine.u · LM_ServerInterface.GuidLogin` monta `/GuidLogin`.
- `?listen`: sem string nos dumps. `LM_Engine.dll` exporta `UServerLevel::Listen` (`?Listen@UServerLevel@@QAEHPAGAAVFString@@@Z`).
- Handshake UE2: `Engine.dll` contém `LOGIN URL=%s`, `LOGIN`, `FAILCODE LOGIN %s` e `Socket close at ULevel::NotifyReceivedText LOGIN %s`. O envio é nativo; nenhuma função UnrealScript dispara o `LOGIN` (inferido). Parei aqui.

## 6. O que falta provar

- Ordem real entre `ServerUpdateMovement` (confiável) e `ServerMove` (unreliable). Não medido.
- Corpo de `execSetMovement@ALM_Pawn` em `Engine.dll`. Não lido: o que `SetMovement` faz além de posição, rotação e física é (inferido).
- Se os `physWalking`/`physFalling` nativos rodam no servidor para pawn humano (via `Tick`/`performPhysics`). Não verificado.
- Valores default de `MaxResponseTime` e `MaxTimeMargin`: não localizados no dump.
- Função dona do bloco `?name=?key=?team=?voice=` em `XInterface.u` (bytecode).
- `PHYS_Boosting`: declarado em `EPhysics` (`Engine.u`) e citado em `LM_BoosterBase.Tick` em trecho fragmentado (`Engine.u`, linha 37790, possivelmente comentado). Uso efetivo não confirmado.
- Predição do booster no cliente (drena e recarrega no `Tick` dos dois lados): sem medição em execução.
- Fragmentos do `strs.py` em `LM_xPawn.DoJump` (`XGame.u`, linha 29587) e `LM_BoosterBase.Tick` foram reconstituídos (inferido).
- Atribuição de estado (`CallServerMove`, `LongClientAdjustPosition` em `RoundEnded`): o parser de `scratchpad\state_ctx.py` pareia `{`/`}` a partir das runs ASCII, porque o `strs.py` descarta chaves isoladas. A atribuição é (inferido) e deve ser confirmada pelo `.u` original ou pelo compilador.
- Nada foi confirmado em execução: o jogo não foi aberto.
