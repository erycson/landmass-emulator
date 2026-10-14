// Bots do LMEmu (D220): cada bot vem de uma linha `Bots=?Name=...` da seção do LMEmu.ini.
// A linha dá a aparência (registro de jogador da espécie do morat), o equipamento e o skill.
// Nome e número seguem a ordem de criação: Bot1, Bot2... (o motor cria pelo nome do registro e este
// objeto reclama o bot novo para aplicar a linha). Só servidor: nada aqui é replicado.
class LMEmuBots extends Object;

var LMEmuLoadout Source;
var int Taken;                   // bots já criados pelo lote, o número do próximo nome é Taken + 1
var array<Controller> Who;       // bots reclamados
var array<string> Lines;         // linha efetiva de cada bot reclamado (mesmo índice de Who)
var string Current;              // linha do bot cujo RestartPlayer está em curso
var int ChatSkill;               // skill pedido por /bot add (-1: usa o da linha)

static function LMEmuBots Open(LMEmuLoadout L)
{
    local LMEmuBots B;

    if (L == None || L.Bots.Length == 0)
        return None;
    B = new(None) class'LMEmuBots';
    B.Source = L;
    B.ChatSkill = -1;
    Log("LMEmu: bots" @ L.Bots.Length @ "linhas");
    return B;
}

// Próxima linha com nome Bot<k> prefixado (ParseOption devolve a primeira ocorrência) e skill opcional.
function string NextLine()
{
    local string Line;

    Taken++;
    Line = "?Name=Bot" $ string(Taken);
    if (ChatSkill >= 0)
        Line = Line $ "?Skill=" $ string(ChatSkill);
    return Line $ Source.Bots[(Taken - 1) % Source.Bots.Length];
}

function string Opt(string Line, string Key)
{
    return class'GameInfo'.static.ParseOption(Line, Key);
}

function bool Known(Controller C)
{
    local int i;

    for (i = 0; i < Who.Length; i++)
        if (Who[i] == C)
            return true;
    return false;
}

function string LineOf(Controller C)
{
    local int i;

    for (i = 0; i < Who.Length; i++)
        if (Who[i] == C)
            return Lines[i];
    return "";
}

// Reclama o primeiro bot da lista de controladores sem linha (o que o motor acabou de criar).
function ClaimNewest(Controller First, string Line)
{
    local Controller C;
    local LM_xPlayerReplicationInfo PRI;

    for (C = First; C != None; C = C.nextController)
    {
        if (Bot(C) == None || Known(C))
            continue;
        Who[Who.Length] = C;
        Lines[Lines.Length] = Line;
        if (C.PlayerReplicationInfo != None)
        {
            C.PlayerReplicationInfo.PlayerName = Opt(Line, "Name");
            C.PlayerReplicationInfo.bBot = true;
            C.PlayerReplicationInfo.Ping = 0;
            PRI = LM_xPlayerReplicationInfo(C.PlayerReplicationInfo);
            if (PRI != None)
            {
                // Booster e gerador são dados (PartsData) que o pawn lê do PRI, não itens de inventário.
                PRI.strBoosterDataClass = Opt(Line, "Booster");
                PRI.strGeneratorDataClass = Opt(Line, "Generator");
            }
        }
        if (Bot(C) != None)
        {
            Bot(C).Skill = float(Opt(Line, "Skill"));
            if (Opt(Line, "MainWeapon") != "" && !(Opt(Line, "MainWeapon") ~= "none"))
                Bot(C).FavoriteWeapon = class<Weapon>(DynamicLoadObject(Opt(Line, "MainWeapon"), class'Class'));
        }
        Log("LMEmu: bot" @ Opt(Line, "Name") @ "morat" @ Opt(Line, "Morat") @ "especie" @ Opt(Line, "Species") @ "skill" @ Opt(Line, "Skill"));
        return;
    }
    Log("LMEmu: bot criado sem reclamar linha" @ Opt(Line, "Name"));
}

// Tira o bot mais recente da partida (vaga para um humano ou /bot remove). Falso se não há bot.
function bool RemoveNewest(GameInfo G)
{
    local Controller C;
    local int i;

    for (i = Who.Length - 1; i >= 0; i--)
    {
        C = Who[i];
        Who.Remove(i, 1);
        Lines.Remove(i, 1);
        if (C != None && !C.bDeleteMe)
        {
            Log("LMEmu: bot removido" @ C.PlayerReplicationInfo.PlayerName);
            G.Logout(C);
            if (C.Pawn != None)
                C.Pawn.Destroy();
            C.Destroy();
            return true;
        }
    }
    return false;
}

function int Count()
{
    return Who.Length;
}

function EquipPiece(LM_xPawn P, string Line, string Key)
{
    local string Cls;
    local int i;

    Cls = Opt(Line, Key);
    if (Cls == "" || Cls ~= "none")
        return;
    for (i = 0; i < 50; i++)
        if (P.RequiredEquipment[i] == "")
            break;
    if (i >= 50)
        return;
    P.RequiredEquipment[i] = Cls;
    if (!P.NewCreateInventory(Cls))
        Log("LMEmu: equipamento" @ Cls @ "de" @ Key @ "nao criado para" @ Opt(Line, "Name"));
}

// Aplica o equipamento da linha no pawn do bot. Substitui o AddDefaultInventory do pawn, que lê o
// PlayerController do jogador humano (Accessed None 'Controller' no bot).
function Equip(Pawn P, string Line)
{
    local LM_xPawn X;

    X = LM_xPawn(P);
    if (X == None)
    {
        Log("LMEmu: pawn do bot nao e LM_xPawn" @ Opt(Line, "Name"));
        return;
    }
    EquipPiece(X, Line, "MainWeapon");
    EquipPiece(X, Line, "SubWeapon");
    EquipPiece(X, Line, "MeleeWeapon");
    EquipPiece(X, Line, "EtcWeapon1");
    EquipPiece(X, Line, "EtcWeapon2");
    EquipPiece(X, Line, "EtcWeapon3");
}

// Depois do RestartPlayer (pawn possuído): booster e gerador pelo PRI e troca para a melhor arma.
function Finish(Controller C, string Line)
{
    local LM_xPawn X;

    if (C == None || C.Pawn == None)
        return;
    X = LM_xPawn(C.Pawn);
    if (X != None)
    {
        X.SpawnBooster();
        X.SpawnGenerator();
    }
    if (Bot(C) != None)
        Bot(C).SwitchToBestWeapon();
    Log("LMEmu: bot" @ Opt(Line, "Name") @ "arma" @ C.Pawn.Weapon);
}
