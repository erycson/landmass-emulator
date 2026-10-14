// Comandos do dono da sala no chat (D220): `/bot add [0-9]` (0-9 vira skill 0-7) e `/bot remove`.
// Só o jogador cujo apelido em hex é Owner do LMEmu.ini usa o comando; a mensagem não vai aos outros.
// Fica na frente da cadeia de BroadcastHandler, e a resposta ao dono é ClientMessage.
class LMEmuBroadcast extends BroadcastHandler;

var LMEmuLoadout Loadout;
var LMEmuBots Botset;
var GameInfo Game;

// Chamado uma vez por destinatário: o comando roda só na cópia do próprio dono, e a mensagem some
// para todos.
function bool AcceptBroadcastText(PlayerController Receiver, PlayerReplicationInfo SenderPRI, out string Msg, optional name Type)
{
    if (Left(Msg, 4) ~= "/bot" && SenderPRI != None && Loadout != None && Loadout.Owner != ""
        && class'LMEmuLoadout'.static.HexOf(SenderPRI.PlayerName) == Loadout.Owner)
    {
        if (Receiver != None && Receiver.PlayerReplicationInfo == SenderPRI)
            Command(SenderPRI, Msg);
        return false;
    }
    return Super.AcceptBroadcastText(Receiver, SenderPRI, Msg, Type);
}

function Command(PlayerReplicationInfo Sender, string Msg)
{
    if (Left(Msg, 11) ~= "/bot remove")
    {
        if (Botset != None && Botset.RemoveNewest(Game))
            Reply(Sender, "Bot removido.");
        else
            Reply(Sender, "Nao ha bot para remover.");
        return;
    }
    if (Left(Msg, 8) ~= "/bot add")
    {
        Add(Sender, Mid(Msg, 9));
        return;
    }
    Reply(Sender, "Comandos: /bot add [0-9] | /bot remove");
}

function Add(PlayerReplicationInfo Sender, string Digit)
{
    local bool bOk;
    local int Skill;

    if (Botset == None)
    {
        Reply(Sender, "Bots desligados nesta partida.");
        return;
    }
    if (Game.NumPlayers + Game.NumBots >= Game.MaxPlayers)
    {
        Reply(Sender, "Sala cheia.");
        return;
    }
    Skill = 3;
    if (Digit != "")
        Skill = int(Digit);
    if (Skill < 0)
        Skill = 0;
    if (Skill > 7)
        Skill = 7;
    Botset.ChatSkill = Skill;
    if (LMEmuTeamDeathMatch(Game) != None)
        bOk = LMEmuTeamDeathMatch(Game).AddBot();
    else if (LMEmuDeathMatch(Game) != None)
        bOk = LMEmuDeathMatch(Game).AddBot();
    Botset.ChatSkill = -1;
    if (bOk)
        Reply(Sender, "Bot adicionado (skill" @ string(Skill) $ ").");
    else
        Reply(Sender, "Nao foi possivel adicionar o bot.");
}

function Reply(PlayerReplicationInfo Sender, string Text)
{
    local Controller C;

    for (C = Game.Level.ControllerList; C != None; C = C.nextController)
        if (PlayerController(C) != None && C.PlayerReplicationInfo == Sender)
        {
            PlayerController(C).ClientMessage(Text);
            return;
        }
}
