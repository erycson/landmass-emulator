// Gravação de posições para as rotas dos bots (D225). Ligada pela chave [LMEmuRecorder] bRecord=True
// no System\LMEmu.ini; sem ela a classe não cria nada. A cada 0,5 s, uma linha por pawn humano vivo no
// log da partida (LOG=). bRecordBots=True inclui os bots, só para teste sem humano. Só servidor.
// Teste sem cliente (D229): TesteAdd=N faz N `/bot add` aos 15 s, e a cada 10 s o log traz a contagem.
class LMEmuRecorder extends Info
    config(LMEmu);

var config bool bRecord;
var config bool bRecordBots;
var config int TesteAdd;

var string MapName;
var array<Controller> Ctl;   // controlador já visto (mesmo índice de Last e Lives)
var array<Pawn> Last;        // pawn atual de cada controlador; troca de pawn é nova vida
var array<int> Lives;
var bool bAdicionou;
var float ProximaContagem;

static function Start(LevelInfo L)
{
    if (default.bRecord)
        L.Spawn(class'LMEmuRecorder');
}

event PostBeginPlay()
{
    MapName = class'LMEmuRoutes'.static.MapOf(Level);
    SetTimer(0.5, true);
    Log("LMEmu: gravacao de posicoes ligada em" @ MapName);
}

event Timer()
{
    local Controller C;
    local Pawn P;
    local int i;

    if (!bAdicionou && default.TesteAdd > 0 && Level.TimeSeconds >= 15)
    {
        bAdicionou = true;
        AddBots(default.TesteAdd);
    }
    if (Level.TimeSeconds >= ProximaContagem)
    {
        ProximaContagem = Level.TimeSeconds + 10;
        Log("LMEmu: contagem t=" $ string(Level.TimeSeconds) $ " jogadores=" $ string(Level.Game.NumPlayers)
            $ " bots=" $ string(Level.Game.NumBots) $ " minimo=" $ string(LM_DeathMatch(Level.Game).MinPlayers)
            $ " max=" $ string(Level.Game.MaxPlayers));
    }
    for (C = Level.ControllerList; C != None; C = C.nextController)
    {
        P = C.Pawn;
        if (P == None || P.Health <= 0 || !Tracked(C))
            continue;
        i = Slot(C, P);
        Log(Line(C, P, Lives[i]));
    }
}

// Mesmo caminho do chat: LMEmuBots.Add, com skill 3. Só existe onde a partida tem o LMEmuBots.
function AddBots(int N)
{
    local LMEmuBots B;
    local int i;

    if (LMEmuDeathMatch(Level.Game) != None)
        B = LMEmuDeathMatch(Level.Game).Botset;
    else if (LMEmuTeamDeathMatch(Level.Game) != None)
        B = LMEmuTeamDeathMatch(Level.Game).Botset;
    if (B == None)
        return;
    for (i = 0; i < N; i++)
        if (!B.Add(Level.Game, 3))
            break;
    Log("LMEmu: teste /bot add criou" @ string(i) @ "de" @ string(N));
}

function bool Tracked(Controller C)
{
    if (PlayerController(C) != None)
        return true;
    return default.bRecordBots && Bot(C) != None;
}

function int Slot(Controller C, Pawn P)
{
    local int i;

    for (i = 0; i < Ctl.Length; i++)
        if (Ctl[i] == C)
            break;
    if (i == Ctl.Length)
    {
        Ctl.Length = i + 1;
        Last.Length = i + 1;
        Lives.Length = i + 1;
        Ctl[i] = C;
        Last[i] = None;
        Lives[i] = 0;
    }
    if (Last[i] != P)
    {
        Last[i] = P;
        Lives[i] = Lives[i] + 1;
    }
    return i;
}

function string Line(Controller C, Pawn P, int Vida)
{
    local int Id;
    local LM_xPawn X;

    Id = -1;
    if (C.PlayerReplicationInfo != None)
        Id = C.PlayerReplicationInfo.PlayerID;
    X = LM_xPawn(P);
    return "LMEmuRec map=" $ MapName $ " t=" $ string(Level.TimeSeconds) $ " pid=" $ string(Id)
        $ " vida=" $ string(Vida) $ " x=" $ string(P.Location.X) $ " y=" $ string(P.Location.Y)
        $ " z=" $ string(P.Location.Z) $ " fis=" $ PhysName(P) $ " vz=" $ string(P.Velocity.Z)
        $ " boost=" $ BoostOn(P) $ " gs=" $ string(P.GroundSpeed)
        $ " vxy=" $ string(VSize(P.Velocity)) $ " acc=" $ string(VSize(P.Acceleration))
        $ " ctl=" $ string(C.GetStateName())
        $ " pri=" $ string(C.PlayerReplicationInfo != None)
        $ " bd=" $ string(X != None && X.BoosterData != None)
        $ " gd=" $ string(X != None && X.GeneratorData != None)
        $ " ag=" $ string(X.agility) $ " fgs=" $ string(X.fDefaultGroundSpeed)
        $ " mt=" $ string(C.MoveTarget) $ " goal=" $ GoalOf(C);
}

// Objetivo de depuração do bot (o motor e LMEmuRoutes escrevem); vazio para humano.
function string GoalOf(Controller C)
{
    if (Bot(C) == None)
        return "";
    return Bot(C).GoalString;
}

function string PhysName(Pawn P)
{
    if (P.Physics == PHYS_Walking)
        return "walk";
    if (P.Physics == PHYS_Falling)
        return "fall";
    if (P.Physics == PHYS_Flying)
        return "fly";
    return "other";
}

function string BoostOn(Pawn P)
{
    local LM_Pawn X;

    X = LM_Pawn(P);
    if (X != None && X.Booster != None && X.Booster.bIsEnabled)
        return "1";
    return "0";
}

defaultproperties
{
    RemoteRole=ROLE_None
    bHidden=true
}
