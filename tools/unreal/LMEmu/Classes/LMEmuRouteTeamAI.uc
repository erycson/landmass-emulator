// TeamAI do TDM do LMEmu (D227): cria squads LMEmuRouteSquad, que tentam a rota antes do motor.
class LMEmuRouteTeamAI extends TeamAI;

// O motor reparte ordens pela OrderList e dá FOLLOW a parte dos bots: o bot entra no squad do humano e fica
// com ele. Aqui todo bot nasce freelance e sai sozinho atrás do time inimigo (D245).
function SetBotOrders(Bot NewBot, RosterEntry R)
{
    PutOnFreelance(NewBot);
}

defaultproperties
{
    SquadType=class'LMEmuRouteSquad'
}
