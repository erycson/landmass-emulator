// Comandos do dono da sala (D220, D254): `/bot add [0-9]` (0-9 vira skill 0-7) e `/bot remove`.
// O chat da partida vai ao canal (240 com " //GAMECHAT", SendMsgEx do XInterface), não ao servidor de
// jogo. O emulador separa o /bot do dono e o repassa por esta conexão local (`?lmemuctl=` da URL),
// uma linha por comando. A resposta ao dono é ClientMessage.
class LMEmuControl extends TcpLink;

var LMEmuLoadout Loadout;
var LMEmuBots Botset;
var GameInfo Game;
var string Key;

function Start(GameInfo G, LMEmuLoadout L, LMEmuBots B, string K, int Port)
{
    local IpAddr Addr;

    Game = G;
    Loadout = L;
    Botset = B;
    Key = K;
    LinkMode = MODE_Line;
    ReceiveMode = RMODE_Event;
    StringToIpAddr("127.0.0.1", Addr);
    Addr.Port = Port;
    if (BindPort() == 0 || !Open(Addr))
        Log("LMEmu: canal de comandos sem conexao na porta" @ Port);
}

event Opened()
{
    SendText("hello" @ Key);
    Log("LMEmu: canal de comandos aberto");
}

event Closed()
{
    Log("LMEmu: canal de comandos fechado");
}

event ReceivedLine(string Line)
{
    // O motor pode deixar o CR do CRLF.
    if (Right(Line, 1) == Chr(13))
        Line = Left(Line, Len(Line) - 1);
    Log("LMEmu: comando [" $ Line $ "]");
    Command(OwnerPRI(), Line);
}

// O dono é quem tem o apelido em hex igual ao Owner do LMEmu.ini; o emulador já conferiu no canal.
function PlayerReplicationInfo OwnerPRI()
{
    local Controller C;

    for (C = Level.ControllerList; C != None; C = C.NextController)
        if (PlayerController(C) != None && C.PlayerReplicationInfo != None
            && class'LMEmuLoadout'.static.HexOf(C.PlayerReplicationInfo.PlayerName) == Loadout.Owner)
            return C.PlayerReplicationInfo;
    return None;
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

    Log("LMEmu: resposta ao dono:" @ Text);
    SendText(Text);  // o emulador registra no log dele
    for (C = Level.ControllerList; C != None; C = C.NextController)
        if (PlayerController(C) != None && C.PlayerReplicationInfo == Sender)
        {
            PlayerController(C).ClientMessage(Text);
            return;
        }
}
