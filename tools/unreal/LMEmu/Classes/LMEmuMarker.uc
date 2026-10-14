// Nó da rota onde o bot quer chegar (D226): o motor anda até ele pelo MoveTarget. Sem colisão, sem
// replicação e invisível; só servidor.
// Vigia do dono (D248): parado sem inimigo à vista, o motor pode não chamar mais o squad. O MoveToward do
// Roaming não termina empurrando parede, e o RestFormation espera em latente (sem rede não acha destino).
// Sem o squad não há Assign, que troca o destino travado. O vigia chama o WhatToDoNext.
class LMEmuMarker extends Actor;

const PRESO = 4.0;    // segundos sem sair do lugar; acima do ROUTE_STALL do LMEmuRoutes para ele disparar
const ANDOU = 250.0;  // deslocamento que conta como sair do lugar (o ROUTE_MOVED do LMEmuRoutes)

var Bot Dono;
var vector Visto;     // onde o dono estava quando saiu do lugar pela última vez
var float VistoEm;

event PostBeginPlay()
{
    SetTimer(1.0, true);
}

event Timer()
{
    // Lutar parado (RangedAttack) e cair não são trava. PHYS_None conta: o WhatToDoNext a desfaz.
    if (Dono == None || Dono.Pawn == None || Dono.Pawn.Physics == PHYS_Falling || (Dono.Enemy != None && Dono.EnemyVisible())
        || VSize(Dono.Pawn.Location - Visto) > ANDOU)
    {
        if (Dono != None && Dono.Pawn != None)
            Visto = Dono.Pawn.Location;
        VistoEm = Level.TimeSeconds;
        return;
    }
    if (Level.TimeSeconds - VistoEm > PRESO)
    {
        VistoEm = Level.TimeSeconds;
        Dono.WhatToDoNext(60);
    }
}

defaultproperties
{
    RemoteRole=ROLE_None
    bHidden=true
    bCollideActors=false
    bCollideWorld=false
    bBlockActors=false
    bBlockPlayers=false
    CollisionRadius=30.0
    CollisionHeight=30.0
}
