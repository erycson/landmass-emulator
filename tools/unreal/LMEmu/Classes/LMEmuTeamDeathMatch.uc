// LM_TeamDeathMatch com o equipamento de cada jogador vindo do emulador (LMEmuLoadout) e bots das
// linhas Bots= (LMEmuBots, D220). Vaga: um bot sai quando um humano entra na sala cheia.
class LMEmuTeamDeathMatch extends LM_TeamDeathMatch;

var LMEmuLoadout Loadout;
var LMEmuBots Botset;
var LMEmuRoutes Routes;
var bool bBake;

event InitGame(string Options, out string Error)
{
    Super.InitGame(Options, Error);
    bBake = class'LMEmuBake'.static.Wanted(Options);
    Loadout = class'LMEmuLoadout'.static.Open(ParseOption(Options, "lmemu"));
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
    if (Botset != None && Loadout.Owner != "")
        InstallChat();
}

// Cadeia de chat: o handler do dono fica na frente e só intercepta /bot.
function InstallChat()
{
    local LMEmuBroadcast H;

    H = Spawn(class'LMEmuBroadcast');
    H.Loadout = Loadout;
    H.Botset = Botset;
    H.Game = self;
    H.NextBroadcastHandler = BroadcastHandler;
    BroadcastHandler = H;
    Log("LMEmu: comandos /bot do dono instalados");
}

// O cliente carrega a classe do jogo pelo nome no GRI e compara com a original (xBombingRun no HUD);
// ele nao tem o pacote LMEmu.
function InitGameReplicationInfo()
{
    Super.InitGameReplicationInfo();
    GameReplicationInfo.GameClass = "XGame.LM_TeamDeathMatch";
}

event PlayerController Login(string Portal, string Options, out string Error)
{
    if (Botset != None && Botset.Count() > 0 && NumPlayers + NumBots >= MaxPlayers)
        Botset.RemoveNewest(self);
    if (Loadout != None)
        Options = Loadout.Inject(Options);
    return Super.Login(Portal, Options, Error);
}

// Humano entrou: o mínimo passa a contar com ele (D229). A vaga tirada no Login já saiu do total.
event PostLogin(PlayerController NewPlayer)
{
    Super.PostLogin(NewPlayer);
    if (Botset != None)
        Botset.Sync(self);
}

// O XGame arredonda o mínimo para par em time. Aqui o mínimo é o total exato de jogadores e bots, para
// que /bot add crie um bot e não dois (D229). Times com diferença de um jogador: ver docs/architecture/08-bots.md.
function int GetMinPlayers()
{
    return MinPlayers;
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
    TeamAIType(0)=class'LMEmuRouteTeamAI'
    TeamAIType(1)=class'LMEmuRouteTeamAI'
}
