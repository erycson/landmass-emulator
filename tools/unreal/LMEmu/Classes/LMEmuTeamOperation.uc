// LM_TeamOperation com o equipamento de cada jogador vindo do emulador (LMEmuLoadout).
class LMEmuTeamOperation extends LM_TeamOperation;

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
    GameReplicationInfo.GameClass = "XGame.LM_TeamOperation";
}

event PostBeginPlay()
{
    Super.PostBeginPlay();
    class'LMEmuRecorder'.static.Start(Level);
}

event PlayerController Login(string Portal, string Options, out string Error)
{
    if (Loadout != None)
        Options = Loadout.Inject(Options);
    return Super.Login(Portal, Options, Error);
}
