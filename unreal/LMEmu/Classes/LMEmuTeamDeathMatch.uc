// LM_TeamDeathMatch com o equipamento de cada jogador vindo do emulador (LMEmuLoadout).
class LMEmuTeamDeathMatch extends LM_TeamDeathMatch;

var LMEmuLoadout Loadout;

event InitGame(string Options, out string Error)
{
    Super.InitGame(Options, Error);
    Loadout = class'LMEmuLoadout'.static.Open(ParseOption(Options, "lmemu"));
}

// O cliente carrega a classe do jogo pelo nome no GRI e compara com a original (xBombingRun no HUD);
// ele não tem o pacote LMEmu.
function InitGameReplicationInfo()
{
    Super.InitGameReplicationInfo();
    GameReplicationInfo.GameClass = "XGame.LM_TeamDeathMatch";
}

event PlayerController Login(string Portal, string Options, out string Error)
{
    if (Loadout != None)
        Options = Loadout.Inject(Options);
    return Super.Login(Portal, Options, Error);
}
