// Equipamento de cada jogador de uma partida, gravado pelo emulador em System\LMEmu.ini.
// Seção [<chave> LMEmuLoadout], chave vinda de ?lmemu= na URL do servidor.
// Cada linha: Players=<apelido em hex, 4 dígitos por caractere>|?Team=..?morats=..?weapon_main=..
// O motor original montava essas opções a partir do canal (LM_Engine NotifyReceivedText); aqui
// elas entram na frente das do cliente, e ParseOption devolve a primeira ocorrência.
class LMEmuLoadout extends Object
    config(LMEmu)
    perobjectconfig;

var config array<string> Players;
// Bots da partida (D220): uma linha `Bots=?Name=Bot1?Record=..?Morat=..?MainWeapon=..` por bot
// possível, na ordem em que o motor cria (LMEmuBots).
var config array<string> Bots;
// Apelido em hex do dono da sala: só ele usa /bot add e /bot remove (LMEmuBroadcast).
var config string Owner;

static function LMEmuLoadout Open(string Key)
{
    local LMEmuLoadout L;

    if (Key == "")
        return None;
    L = new(None, Key) class'LMEmuLoadout';
    Log("LMEmu: chave" @ Key @ "com" @ L.Players.Length @ "jogadores");
    return L;
}

static function string HexOf(string S)
{
    local int i, c;
    local string R, D;

    D = "0123456789ABCDEF";
    for (i = 0; i < Len(S); i++)
    {
        c = Asc(Mid(S, i, 1));
        R = R $ Mid(D, (c >> 12) & 15, 1) $ Mid(D, (c >> 8) & 15, 1) $ Mid(D, (c >> 4) & 15, 1) $ Mid(D, c & 15, 1);
    }
    return R;
}

function string Inject(string Options)
{
    local string Key;
    local int i;

    Key = HexOf(class'GameInfo'.static.ParseOption(Options, "Name")) $ "|";
    for (i = 0; i < Players.Length; i++)
    {
        if (Left(Players[i], Len(Key)) == Key)
        {
            Log("LMEmu: login" @ Options @ "recebe" @ Mid(Players[i], Len(Key)));
            return Mid(Players[i], Len(Key)) $ Options;
        }
    }
    Log("LMEmu: login sem equipamento" @ Options);
    return Options;
}
