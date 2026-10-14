// Squad de TDM do LMEmu (D227): igual ao LMEmuRouteDMSquad, para os times. Criado pelo
// LMEmuRouteTeamAI.
class LMEmuRouteSquad extends SquadAI;

function bool AssignSquadResponsibility(Bot B)
{
    local LMEmuTeamDeathMatch G;

    G = LMEmuTeamDeathMatch(Level.Game);
    if (G != None && G.Routes != None && G.Routes.Assign(B))
        return true;
    return Super.AssignSquadResponsibility(B);
}
