// LM_DeathMatch com o equipamento de cada jogador vindo do emulador (LMEmuLoadout) e bots das
// linhas Bots= (LMEmuBots, D220). Vaga: um bot sai quando um humano entra na sala cheia.
class LMEmuDeathMatch extends LM_DeathMatch;

var LMEmuLoadout Loadout;
var LMEmuBots Botset;
var LMEmuRoutes Routes;
var bool bBake;
var LMEmuControl Control;
var string CtlKey;
var int CtlPort;

event InitGame(string Options, out string Error)
{
    Super.InitGame(Options, Error);
    bBake = class'LMEmuBake'.static.Wanted(Options);
    CtlKey = ParseOption(Options, "lmemu");
    CtlPort = int(ParseOption(Options, "lmemuctl"));
    Loadout = class'LMEmuLoadout'.static.Open(CtlKey);
    if (Loadout != None)
        Botset = class'LMEmuBots'.static.Open(Loadout);
}

event PostBeginPlay()
{
    Super.PostBeginPlay();
    if (bBake)
    {
        class'LMEmuBake'.static.Start(Level);
        return;
    }
    class'LMEmuRecorder'.static.Start(Level);
    if (Botset != None)
        Routes = class'LMEmuRoutes'.static.Open(Level, class'LMEmuRoutes'.static.MapOf(Level));
    if (Botset != None && Loadout.Owner != "" && CtlPort > 0)
    {
        Control = Spawn(class'LMEmuControl');
        Control.Start(self, Loadout, Botset, CtlKey, CtlPort);
    }
}

// O cliente carrega a classe do jogo pelo nome no GRI e compara com a original (xBombingRun no HUD);
// ele nao tem o pacote LMEmu.
function InitGameReplicationInfo()
{
    Super.InitGameReplicationInfo();
    GameReplicationInfo.GameClass = "XGame.LM_DeathMatch";
}

event PlayerController Login(string Portal, string Options, out string Error)
{
    if (Botset != None && Botset.Count() > 0 && NumPlayers + NumBots >= MaxPlayers)
        Botset.RemoveNewest(self);
    if (Loadout != None)
        Options = Loadout.Inject(Options);
    return Super.Login(Portal, Options, Error);
}

// Humano entrou: o mínimo passa a contar com ele, sem baixar (D229). A vaga tirada no Login já saiu do total.
event PostLogin(PlayerController NewPlayer)
{
    Super.PostLogin(NewPlayer);
    if (Botset != None)
        Botset.Grow(self);
}

function EndGame(PlayerReplicationInfo Winner, string Reason)
{
    Super.EndGame(Winner, Reason);
    class'LMEmuBots'.static.LogEnd(Level);
}

// O MatchOver do LM desconecta todos depois do RestartWait e para (bMatchOver), sem viajar nem sair. O
// cliente volta à sala sem mandar 500; o servidor sai e o emulador fecha a partida pela saída (D253).
state MatchOver
{
    function Timer()
    {
        Super.Timer();
        if (bMatchOver)
        {
            Log("LMEmu: fim da partida, servidor saindo");
            Level.ConsoleCommand("exit");
        }
    }
}

// O LastMan do LM conta só humanos: um humano sozinho (ou um time só de bots) encerrava a partida em
// segundos, com o motivo trocado para TimeLimit (ControlEndReason). Com bots, só encerra sem humano.
function CheckLastMan()
{
    if (Botset == None)
    {
        Super.CheckLastMan();
        return;
    }
    // bRecordBots (só teste sem humano): a partida segue para medir os bots por mais de 40 s.
    if (NumPlayers == 0 && !class'LMEmuRecorder'.default.bRecordBots)
    {
        Log("LMEmu: fim sem humano");
        EndGame(None, "LastMan");
    }
}

// Bot criado pelo nome do registro de jogador da linha (aparencia valida); depois reclama o bot novo.
function bool AddBot(optional string botName)
{
    local string Line;
    local bool bOk;

    if (Botset == None)
        return Super.AddBot(botName);
    Line = Botset.NextLine();
    bOk = Super.AddBot(Botset.Opt(Line, "Record"));
    if (bOk)
    {
        Botset.Expect(Line);
        Botset.ClaimNewest(Level.ControllerList);
    }
    return bOk;
}

function RestartPlayer(Controller aPlayer)
{
    local string Line;

    if (Botset != None && Bot(aPlayer) != None)
    {
        Botset.ClaimIfNew(aPlayer);
        Line = Botset.LineOf(aPlayer);
    }
    if (Line != "")
        Botset.Current = Line;
    Super.RestartPlayer(aPlayer);
    if (Line != "")
    {
        Botset.Current = "";
        Botset.Finish(aPlayer, Line);
    }
}

// Equipamento do bot pela linha; humano segue o caminho do jogo.
function AddDefaultInventory(pawn PlayerPawn)
{
    if (Botset != None && Botset.Current != "")
    {
        Botset.Equip(PlayerPawn, Botset.Current);
        return;
    }
    Super.AddDefaultInventory(PlayerPawn);
}

defaultproperties
{
    DMSquadClass=class'LMEmuRouteDMSquad'
}
