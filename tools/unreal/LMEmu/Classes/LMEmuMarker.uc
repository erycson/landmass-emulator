// Nó da rota onde o bot quer chegar (D226): o motor anda até ele pelo MoveTarget. Sem colisão, sem
// replicação e invisível; só servidor.
class LMEmuMarker extends Actor;

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
