// Bots do LMEmu (D220): cada bot vem de uma linha `Bots=?Name=[BOT] ...` da seção do LMEmu.ini.
// A linha dá o apelido (D231), a aparência (registro de jogador da espécie do morat), o equipamento e o
// skill. O motor cria o bot pelo nome do registro e este objeto reclama o bot novo para aplicar a linha.
// Só servidor: nada aqui é replicado.
class LMEmuBots extends Object;

var LMEmuLoadout Source;
var array<string> Usados;        // apelidos já dados nesta partida (não repetem; D231)
var array<string> Pending;       // linhas pedidas que ainda não viraram bot (ordem de pedido; D229)
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

// Próxima linha: a primeira cujo apelido ainda não foi usado na partida (D231). Com o pool gasto, o
// apelido que não está em bot presente (shortcut: pool = MaxPlayers, um apelido sai da lista só ao gastar).
// Skill do /bot add vai antes da linha, porque ParseOption devolve a primeira ocorrência.
function string NextLine()
{
    local int i;
    local string Line;

    for (i = 0; i < Source.Bots.Length; i++)
        if (!Usado(Opt(Source.Bots[i], "Name")))
            break;
    if (i == Source.Bots.Length)
        for (i = 0; i < Source.Bots.Length; i++)
            if (!Presente(Opt(Source.Bots[i], "Name")))
                break;
    if (i == Source.Bots.Length)
        i = 0;
    Line = Source.Bots[i];
    Usados[Usados.Length] = Opt(Line, "Name");
    if (ChatSkill >= 0)
        Line = "?Skill=" $ string(ChatSkill) $ Line;
    return Line;
}

function bool Usado(string Nome)
{
    local int i;

    for (i = 0; i < Usados.Length; i++)
        if (Usados[i] == Nome)
            return true;
    return false;
}

function bool Presente(string Nome)
{
    local int i;

    for (i = 0; i < Lines.Length; i++)
        if (Opt(Lines[i], "Name") == Nome)
            return true;
    return false;
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

// Linha pedida (AddBot que deu certo) e ainda sem bot. O motor pode entregar o controlador depois do
// AddBot (o time cria pelo roster), então quem chega primeiro leva a linha mais antiga (D229).
function Expect(string Line)
{
    Pending[Pending.Length] = Line;
}

// Reclama o controlador mais novo sem linha, se há linha pedida (o motor acabou de criar o bot).
function ClaimNewest(Controller First)
{
    local Controller C;

    for (C = First; C != None; C = C.nextController)
        if (Bot(C) != None && !Known(C))
        {
            ClaimNext(C);
            return;
        }
}

// Reclama o bot que chega ao RestartPlayer sem linha (o motor criou depois do AddBot).
function ClaimIfNew(Controller C)
{
    if (Bot(C) != None && !Known(C))
        ClaimNext(C);
}

function ClaimNext(Controller C)
{
    local string Line;

    if (Pending.Length == 0)
        return;
    Line = Pending[0];
    Pending.Remove(0, 1);
    Who[Who.Length] = C;
    Lines[Lines.Length] = Line;
    if (C.PlayerReplicationInfo != None)
    {
        C.PlayerReplicationInfo.PlayerName = Opt(Line, "Name");
        C.PlayerReplicationInfo.bBot = true;
        C.PlayerReplicationInfo.Ping = 0;
    }
    Bot(C).Skill = float(Opt(Line, "Skill"));
    if (Opt(Line, "MainWeapon") != "" && !(Opt(Line, "MainWeapon") ~= "none"))
        Bot(C).FavoriteWeapon = class<Weapon>(DynamicLoadObject(Opt(Line, "MainWeapon"), class'Class'));
    Log("LMEmu: bot" @ Opt(Line, "Name") @ "morat" @ Opt(Line, "Morat") @ "especie" @ Opt(Line, "Species") @ "skill" @ Opt(Line, "Skill"));
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
            Sync(G);
            return true;
        }
    }
    return false;
}

function int Count()
{
    return Who.Length;
}

// Mínimo da partida = jogadores + bots, até o máximo (D229). O motor completa a sala com bots até o
// mínimo; chamado só em ação do dono ou de jogador (não na criação automática, que sobe o total).
// MinPlayers e da UnrealMPGameInfo (WPGames), herdado por LM_DeathMatch; so as partidas LMEmu chegam aqui.
function Sync(GameInfo G)
{
    LM_DeathMatch(G).MinPlayers = Min(G.NumPlayers + G.NumBots, G.MaxPlayers);
}

// /bot add (chat e teste de headless, D229): cria um bot se há vaga, com o skill pedido, e eleva o
// mínimo. Falso se não criou.
function bool Add(GameInfo G, int Skill)
{
    local bool bOk;

    if (G.NumPlayers + G.NumBots >= G.MaxPlayers)
        return false;
    ChatSkill = Skill;
    bOk = LM_DeathMatch(G).AddBot();
    ChatSkill = -1;
    if (bOk)
        LM_DeathMatch(G).MinPlayers = Min(G.NumPlayers + G.NumBots + 1, G.MaxPlayers);
    return bOk;
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
    Parts(X, Line);
    EquipPiece(X, Line, "MainWeapon");
    EquipPiece(X, Line, "SubWeapon");
    EquipPiece(X, Line, "MeleeWeapon");
    EquipPiece(X, Line, "EtcWeapon1");
    EquipPiece(X, Line, "EtcWeapon2");
    EquipPiece(X, Line, "EtcWeapon3");
}

// Depois do RestartPlayer (pawn possuído): troca para a melhor arma e recalcula a velocidade.
function Finish(Controller C, string Line)
{
    local LM_xPawn X;

    if (C == None || C.Pawn == None)
        return;
    X = LM_xPawn(C.Pawn);
    if (Bot(C) != None)
        Bot(C).SwitchToBestWeapon();
    if (X != None)
        Speed(X);
    Log("LMEmu: bot" @ Opt(Line, "Name") @ "arma" @ C.Pawn.Weapon);
}

// Classe de PartsData da linha (Booster= ou Generator=), ou None para `none` e linha sem a chave.
function class<LM_PartsData> PartClass(string Line, string Key)
{
    local string Nome;

    Nome = Opt(Line, Key);
    if (Nome == "" || Nome ~= "none")
        return None;
    return class<LM_PartsData>(DynamicLoadObject(Nome, class'Class'));
}

// Booster e gerador do pawn, antes das armas: o peso dos dois entra na velocidade. O motor só os cria
// em SpawnBooster, que lê a classe do PRI, e o PRI do bot é PlayerReplicationInfo, não o de jogador.
function Parts(LM_xPawn P, string Line)
{
    if (P.BoosterData == None && PartClass(Line, "Booster") != None)
        P.BoosterData = P.Spawn(PartClass(Line, "Booster"), P);
    if (P.GeneratorData == None && PartClass(Line, "Generator") != None)
        P.GeneratorData = P.Spawn(PartClass(Line, "Generator"), P);
}

// Velocidade do bot. LM_WeaponBase.CalcPawnSpeedValues retorna cedo quando o pawn não é de jogador
// humano, então o bot ficava com fDefaultGroundSpeed e GroundSpeed em 0 e não andava. Esta é a mesma
// conta do motor (agilidade, peso da arma, booster e gerador, força), com a arma atual.
function Speed(LM_xPawn P)
{
    local float fPeso, fBooster, fGerador, fPenal, fBoosterPenal;

    fBooster = 0;
    fGerador = 0;
    if (P.BoosterData != None)
        fBooster = P.BoosterData.item_weight;
    if (P.GeneratorData != None)
        fGerador = P.GeneratorData.item_weight;
    fPeso = 0;
    if (LM_WeaponBase(P.Weapon) != None)
        fPeso = LM_WeaponBase(P.Weapon).item_weight;
    fPenal = ((fPeso + fBooster + fGerador) - (P.strength - 150.0) * 3.0) / 2.5;

    P.fDefaultGroundSpeed = (P.agility * 0.0324) * 50;
    fBoosterPenal = 0;
    if (fPenal > 0)
    {
        P.fDefaultGroundSpeed = P.fDefaultGroundSpeed - fPenal;
        if (P.Booster != None && P.fDefaultGroundSpeed != 0)
            fBoosterPenal = P.Booster.fDefaultAccelRate * (((fPenal * 100) / P.fDefaultGroundSpeed) / 100);
    }
    P.fDefaultAirSpeed = P.fDefaultGroundSpeed * P.fAirSpeedPct;
    P.fDefaultWaterSpeed = P.fDefaultGroundSpeed * P.fWaterSpeedPct;
    P.GroundSpeed = P.fDefaultGroundSpeed;
    P.AirSpeed = P.fDefaultAirSpeed;
    P.WaterSpeed = P.fDefaultWaterSpeed;
    if (P.Booster != None)
        P.Booster.fAccelRate = P.booster_max_speed - fBoosterPenal;
}
