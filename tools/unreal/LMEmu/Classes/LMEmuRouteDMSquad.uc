// Squad de DM do LMEmu (D227). Sem inimigo, tenta a rota do mapa (LMEmuRoutes.Assign) antes do roam e
// dos itens do motor. Sem seção de rota no mapa, Assign falha e o squad do jogo decide como antes.
class LMEmuRouteDMSquad extends DMSquad;

function bool AssignSquadResponsibility(Bot B)
{
    local LMEmuDeathMatch G;

    G = LMEmuDeathMatch(Level.Game);
    if (G != None && G.Routes != None && G.Routes.Assign(B))
        return true;
    return Super.AssignSquadResponsibility(B);
}
