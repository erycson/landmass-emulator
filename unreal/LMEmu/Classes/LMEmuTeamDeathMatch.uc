// LM_TeamDeathMatch com o equipamento de cada jogador vindo do emulador (LMEmuLoadout).
class LMEmuTeamDeathMatch extends LM_TeamDeathMatch;

var LMEmuLoadout Loadout;

event InitGame(string Options, out string Error)
{
    Super.InitGame(Options, Error);
    Loadout = class'LMEmuLoadout'.static.Open(ParseOption(Options, "lmemu"));
}

event PlayerController Login(string Portal, string Options, out string Error)
{
    if (Loadout != None)
        Options = Loadout.Inject(Options);
    return Super.Login(Portal, Options, Error);
}
