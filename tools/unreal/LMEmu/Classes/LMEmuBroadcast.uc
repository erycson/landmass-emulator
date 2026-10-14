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
    local int p;
    local bool bDono;

    // /bot em qualquer ponto: o primeiro teste com o cliente real mostrou "/bot add 7" no chat, sem comando.
    p = InStr(Locs(Msg), "/bot");
    if (p >= 0 && SenderPRI != None && Loadout != None)
    {
        bDono = Loadout.Owner != "" && class'LMEmuLoadout'.static.HexOf(SenderPRI.PlayerName) == Loadout.Owner;
        if (Receiver != None && Receiver.PlayerReplicationInfo == SenderPRI)
        {
            Log("LMEmu: chat /bot de" @ SenderPRI.PlayerName @ "hex" @ class'LMEmuLoadout'.static.HexOf(SenderPRI.PlayerName)
                @ "dono" @ Loadout.Owner @ "tipo" @ string(Type) @ "msg [" $ Msg $ "]");
            if (bDono)
                Command(SenderPRI, Mid(Msg, p));
        }
        if (bDono)
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
    if (Botset.Add(Game, Skill))
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
