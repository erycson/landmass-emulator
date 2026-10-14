// Rota de um mapa para os bots (D225/D226). Lida de System\LMEmuRoutes.ini, seção [<mapa> LMEmuRoutes]:
//   Waypoint=x,y,z   um nó; o índice é a ordem da linha
//   Link=a,b,flags   aresta dirigida do nó a para o nó b; flags: w andar, f queda, j pulo, b booster
// Gerada pelo LMEmuBake (rotas.py monta o arquivo). Só o servidor usa. Assign (chamado pelo squad, sem
// inimigo) manda o bot andar nó a nó pelo MoveTarget do motor, com um LMEmuMarker por bot. O alvo é a base
// mais longe do bot (nó mais próximo do centro dos PlayerStart de cada time), então o bot vai e volta.
// Plano por bot: A* guardado como árvore de origem; replaneja se o bot sai do caminho. Nada é replicado.
class LMEmuRoutes extends Object
    config(LMEmuRoutes)
    perobjectconfig;

var config array<string> Waypoint;
var config array<string> Link;

const ROUTE_RANGE = 400.0;   // o bot precisa estar a até isto de um nó para estar na rede
const ROUTE_AT = 150.0;      // perto o bastante do nó para pular a partir dele
const ROUTE_STALL = 4;       // decisões seguidas sem sair do mesmo nó antes de largar a rota
const ROUTE_BOOST = false;   // arestas b só entram no A* quando o booster do bot estiver ligado (não feito)

var LevelInfo Level;
var array<vector> Pos;
var array<int> FirstLink;    // arestas do nó n: FirstLink[n] até FirstLink[n+1] - 1
var array<int> LinkTo;
var array<string> LinkFlag;
var array<int> BaseNode;     // nó mais próximo do centro dos PlayerStart do time 0 e do time 1
var array<Controller> Who;   // bots com rota; os arrays abaixo seguem a mesma ordem
var array<int> Goal;         // nó de destino, -1 sem rota
var array<int> LastCur;      // nó mais próximo na última decisão
var array<int> Stall;        // decisões seguidas no mesmo nó
var array<LMEmuMarker> Mark;
var array<int> Came;         // árvore do A* por bot: Came[i * nós + v] = nó anterior de v, -1 na raiz
var array<float> Gs;         // custo acumulado do A* em curso
var array<int> Hq;           // heap do A*: nó e chave
var array<float> Hk;
var int Hn;

// Nome do pacote do mapa ("ONS-Airport" de "ONS-Airport.myLevel"). GetURLMap() volta vazio no servidor.
static function string MapOf(LevelInfo L)
{
    local string S;
    local int P;

    S = string(L);
    P = InStr(S, ".");
    if (P >= 0)
        return Left(S, P);
    return S;
}

static function LMEmuRoutes Open(LevelInfo L, string MapName)
{
    local LMEmuRoutes R;

    if (MapName == "")
        return None;
    R = new(None, MapName) class'LMEmuRoutes';
    if (R.Waypoint.Length < 2)
        return None;
    R.Init(L);
    Log("LMEmu: rotas de" @ MapName @ string(R.Pos.Length) @ "nos" @ string(R.LinkTo.Length) @ "arestas");
    return R;
}

// Campo k de uma linha separada por vírgula ("" se não existe).
static function string Part(string S, int K)
{
    local int P;

    while (K > 0)
    {
        P = InStr(S, ",");
        if (P < 0)
            return "";
        S = Mid(S, P + 1);
        K--;
    }
    P = InStr(S, ",");
    if (P >= 0)
        S = Left(S, P);
    return S;
}

static function vector Vec(string S)
{
    local vector V;

    V.X = float(Part(S, 0));
    V.Y = float(Part(S, 1));
    V.Z = float(Part(S, 2));
    return V;
}

// Monta a lista de adjacência (CSR) e as duas bases. Aresta com índice fora da faixa ou laço é descartada.
function Init(LevelInfo L)
{
    local int i, n, e, a, b, k, t, cnt;
    local array<int> Cur;
    local PlayerStart P;
    local vector C;
    local float dd;

    Level = L;
    n = Waypoint.Length;
    Pos.Length = n;
    for (i = 0; i < n; i++)
        Pos[i] = Vec(Waypoint[i]);
    FirstLink.Length = n + 1;
    Cur.Length = n;
    for (i = 0; i <= n; i++)
        FirstLink[i] = 0;
    for (e = 0; e < Link.Length; e++)
    {
        a = int(Part(Link[e], 0));
        b = int(Part(Link[e], 1));
        if (a < 0 || a >= n || b < 0 || b >= n || a == b)
            continue;
        FirstLink[a + 1] = FirstLink[a + 1] + 1;
    }
    for (i = 1; i <= n; i++)
        FirstLink[i] = FirstLink[i] + FirstLink[i - 1];
    LinkTo.Length = FirstLink[n];
    LinkFlag.Length = FirstLink[n];
    for (i = 0; i < n; i++)
        Cur[i] = FirstLink[i];
    for (e = 0; e < Link.Length; e++)
    {
        a = int(Part(Link[e], 0));
        b = int(Part(Link[e], 1));
        if (a < 0 || a >= n || b < 0 || b >= n || a == b)
            continue;
        k = Cur[a];
        LinkTo[k] = b;
        LinkFlag[k] = Part(Link[e], 2);
        Cur[a] = Cur[a] + 1;
    }

    BaseNode.Length = 2;
    for (t = 0; t < 2; t++)
    {
        C = vect(0.0, 0.0, 0.0);
        cnt = 0;
        foreach L.AllActors(class'PlayerStart', P)
        {
            if (P.TeamNumber == t)
            {
                C = C + P.Location;
                cnt++;
            }
        }
        BaseNode[t] = -1;
        if (cnt > 0 && n > 0)
        {
            C = C * (1.0 / cnt);
            BaseNode[t] = Nearest(C, dd);
        }
        Log("LMEmu: base do time" @ string(t) @ "no" @ string(BaseNode[t]));
    }
}

// Nó mais próximo de P; a distância sai em D.
function int Nearest(vector P, out float D)
{
    local int i, best;
    local float d2;

    best = -1;
    D = 99999999.0;
    for (i = 0; i < Pos.Length; i++)
    {
        d2 = VSize(Pos[i] - P);
        if (d2 < D)
        {
            D = d2;
            best = i;
        }
    }
    return best;
}

function float NodeDist(int a, int b)
{
    return VSize(Pos[a] - Pos[b]);
}

// Custo multiplicador do flag: pulo e booster custam mais que andar (o A* prefere andar).
function float CostMul(string F)
{
    if (InStr(F, "b") >= 0)
        return 3.0;
    if (InStr(F, "j") >= 0)
        return 2.0;
    return 1.0;
}

function int EdgeOf(int A, int B)
{
    local int e;

    for (e = FirstLink[A]; e < FirstLink[A + 1]; e++)
        if (LinkTo[e] == B)
            return e;
    return -1;
}

// Base mais longe do nó cur (a outra base); -1 sem bases.
function int OtherBase(int cur)
{
    if (BaseNode[0] < 0 || BaseNode[1] < 0)
        return -1;
    if (NodeDist(cur, BaseNode[0]) <= NodeDist(cur, BaseNode[1]))
        return BaseNode[1];
    return BaseNode[0];
}

function HSwap(int a, int b)
{
    local int ti;
    local float tk;

    ti = Hq[a];
    Hq[a] = Hq[b];
    Hq[b] = ti;
    tk = Hk[a];
    Hk[a] = Hk[b];
    Hk[b] = tk;
}

function HPush(int v, float k)
{
    local int c, p;

    if (Hn >= Hq.Length)
    {
        Hq.Length = Hn + 64;
        Hk.Length = Hn + 64;
    }
    c = Hn;
    Hn++;
    Hq[c] = v;
    Hk[c] = k;
    while (c > 0)
    {
        p = (c - 1) / 2;
        if (Hk[p] <= Hk[c])
            break;
        HSwap(p, c);
        c = p;
    }
}

// Tira o menor da heap; a chave sai em k.
function int HPop(out float k)
{
    local int top, c, l, r, m;

    top = Hq[0];
    k = Hk[0];
    Hn--;
    if (Hn > 0)
    {
        Hq[0] = Hq[Hn];
        Hk[0] = Hk[Hn];
        c = 0;
        while (true)
        {
            l = 2 * c + 1;
            r = l + 1;
            m = c;
            if (l < Hn && Hk[l] < Hk[m])
                m = l;
            if (r < Hn && Hk[r] < Hk[m])
                m = r;
            if (m == c)
                break;
            HSwap(c, m);
            c = m;
        }
    }
    return top;
}

// A* de from até to (custo = distância x CostMul, heurística = distância reta). Guarda a árvore em Came
// do bot i. Falso se não há caminho.
function bool Plan(int i, int from, int to)
{
    local int u, v, e, base, n;
    local float k, ng;

    n = Pos.Length;
    base = i * n;
    Gs.Length = n;
    for (v = 0; v < n; v++)
        Gs[v] = 1.0e9;
    Gs[from] = 0.0;
    Came[base + from] = -1;
    Hn = 0;
    HPush(from, NodeDist(from, to));
    while (Hn > 0)
    {
        u = HPop(k);
        if (u == to)
            return true;
        if (k > Gs[u] + NodeDist(u, to) + 0.5)
            continue;
        for (e = FirstLink[u]; e < FirstLink[u + 1]; e++)
        {
            if (!ROUTE_BOOST && InStr(LinkFlag[e], "b") >= 0)
                continue;
            v = LinkTo[e];
            ng = Gs[u] + NodeDist(u, v) * CostMul(LinkFlag[e]);
            if (ng < Gs[v])
            {
                Gs[v] = ng;
                Came[base + v] = u;
                HPush(v, ng + NodeDist(v, to));
            }
        }
    }
    return false;
}

// Primeiro nó depois de cur no plano guardado do bot i até to; -1 se cur não está nele.
function int HopFrom(int i, int cur, int to)
{
    local int x, p, base;

    if (cur == to)
        return -1;
    base = i * Pos.Length;
    x = to;
    p = Came[base + x];
    while (p >= 0 && p != cur)
    {
        x = p;
        p = Came[base + x];
    }
    if (p == cur)
        return x;
    return -1;
}

function int Slot(Bot B)
{
    local int i;

    for (i = 0; i < Who.Length; i++)
        if (Who[i] == B)
            return i;
    Who.Length = i + 1;
    Goal.Length = i + 1;
    LastCur.Length = i + 1;
    Stall.Length = i + 1;
    Mark.Length = i + 1;
    Who[i] = B;
    Goal[i] = -1;
    LastCur[i] = -1;
    Stall[i] = 0;
    Mark[i] = Level.Spawn(class'LMEmuMarker');
    if (Came.Length < (i + 1) * Pos.Length)
        Came.Length = (i + 1) * Pos.Length;
    return i;
}

// Chamado pelo AssignSquadResponsibility do squad (DM e TDM) quando o bot não tem inimigo. Verdadeiro:
// o bot foi mandado para o próximo nó (MoveTarget do marcador, Roaming). Falso: o motor decide.
function bool Assign(Bot B)
{
    local int i, cur, nxt, e;
    local float d;
    local LMEmuMarker M;

    if (B == None || B.Pawn == None || B.Enemy != None || B.Pawn.Health <= 0 || Pos.Length < 2)
        return false;
    i = Slot(B);
    cur = Nearest(B.Pawn.Location, d);
    if (cur < 0 || d > ROUTE_RANGE)
    {
        Goal[i] = -1;
        return false;
    }
    if (cur == Goal[i])
    {
        Log("LMEmu: bot" @ B.PlayerReplicationInfo.PlayerName @ "chegou ao no" @ string(cur));
        Goal[i] = -1;
    }
    if (Goal[i] < 0)
    {
        Goal[i] = OtherBase(cur);
        if (Goal[i] < 0 || !Plan(i, cur, Goal[i]))
        {
            Goal[i] = -1;
            return false;
        }
        Log("LMEmu: bot" @ B.PlayerReplicationInfo.PlayerName @ "rota do no" @ string(cur) @ "ate" @ string(Goal[i]));
    }
    nxt = HopFrom(i, cur, Goal[i]);
    if (nxt < 0)
    {
        if (!Plan(i, cur, Goal[i]))
        {
            Goal[i] = -1;
            return false;
        }
        nxt = HopFrom(i, cur, Goal[i]);
        if (nxt < 0)
        {
            Goal[i] = -1;
            return false;
        }
    }
    if (cur == LastCur[i])
        Stall[i] = Stall[i] + 1;
    else
    {
        LastCur[i] = cur;
        Stall[i] = 0;
    }
    if (Stall[i] > ROUTE_STALL)
    {
        Log("LMEmu: bot" @ B.PlayerReplicationInfo.PlayerName @ "largou a rota no no" @ string(cur));
        Goal[i] = -1;
        return false;
    }
    if (!B.pointReachable(Pos[nxt]))
    {
        Goal[i] = -1;
        return false;
    }
    M = Mark[i];
    M.SetLocation(Pos[nxt]);
    e = EdgeOf(cur, nxt);
    if (e >= 0 && d <= ROUTE_AT && B.Pawn.Physics == PHYS_Walking && InStr(LinkFlag[e], "j") >= 0)
    {
        B.Pawn.bCanJump = true;
        B.Pawn.DoJump(false);
        Log("LMEmu: bot" @ B.PlayerReplicationInfo.PlayerName @ "pulo no no" @ string(cur));
    }
    B.MoveTarget = M;
    B.GoalString = "rota no " $ string(nxt);
    B.GotoState('Roaming');
    return true;
}

defaultproperties
{
}
