// Geração automática das rotas do mapa (D225). Só roda com ?lmemubake=1 na URL e sai ao terminar.
// Flood-fill a partir dos PlayerStart sobre a grade (Cell): cada nó é uma célula com piso caminhável.
// Saída no LOG= como "LMEmuBake node id x y z" e "LMEmuBake link a b flags" (w, f, j, b); rotas.py
// monta o LMEmuRoutes.ini. Fatiado por Timer (PerTick expansões por tick). Só servidor.
class LMEmuBake extends Info
    config(LMEmu);

const WALK_NZ = 0.7;       // normal Z mínima de piso caminhável
const HASH_SIZE = 65536;   // tabela de células; bem acima do teto de nós

var config float Cell;     // lado da célula (uu)
var config float StepH;    // degrau que o pawn anda sem pular
var config float MaxDrop;  // maior queda numa aresta
var config float FlyMax;   // maior subida numa aresta (booster)
var config float Reach;    // folga da caixa dos PlayerStart (segurança)
var config int NodeCap;    // teto de nós
var config int PerTick;    // expansões por tick do Timer

var string MapName;
var bool bReady, bDone, bCap;
var int NCols, NHits, NFloor, NBad, NHead, NHoriz, NMid;   // diagnóstico: quantas vezes cada teste barrou
var float Rad, Hgt, Grav, Apex, JumpReach;
var int Head, Links, LastLog;
var vector Lo, Hi;
var array<vector> NPos;
var array<int> NIX, NIY, NIZ;
var array<int> Table;      // célula -> nó + 1 (0 = vazio); sondagem linear

static function bool Wanted(string Options)
{
    return class'GameInfo'.static.ParseOption(Options, "lmemubake") == "1";
}

static function Start(LevelInfo L)
{
    L.Spawn(class'LMEmuBake');
}

event PostBeginPlay()
{
    MapName = class'LMEmuRoutes'.static.MapOf(Level);
    SetTimer(0.1, true);
}

event Timer()
{
    local int n;

    if (bDone)
        return;
    if (!bReady)
    {
        Setup();
        return;
    }
    for (n = 0; n < PerTick && Head < NPos.Length; n++)
    {
        Expand(Head);
        Head++;
    }
    if (Head - LastLog >= 500)
    {
        LastLog = Head;
        Log("LMEmuBake prog" @ string(Head) @ string(NPos.Length) @ string(Links) @ string(Level.TimeSeconds));
    }
    if (Head >= NPos.Length)
        Finish();
}

function Setup()
{
    local PlayerStart P;
    local float fz;
    local int seeds;

    bReady = true;
    Table.Length = HASH_SIZE;
    Rad = class'LM_Pawn'.default.CollisionRadius;
    Hgt = class'LM_Pawn'.default.CollisionHeight;
    Grav = -class'PhysicsVolume'.default.Gravity.Z;
    if (Grav <= 0.0)
        Grav = 950.0;
    Apex = class'LM_Pawn'.default.JumpZ * class'LM_Pawn'.default.JumpZ / (2.0 * Grav);
    JumpReach = class'LM_Pawn'.default.GroundSpeed * (2.0 * class'LM_Pawn'.default.JumpZ / Grav) * 0.8;
    Log("LMEmuBake const raio" @ string(Rad) @ "altura" @ string(Hgt) @ "jumpz" @ string(class'LM_Pawn'.default.JumpZ) @ "speed" @ string(class'LM_Pawn'.default.GroundSpeed) @ "grav" @ string(Grav) @ "apex" @ string(Apex) @ "alcance" @ string(JumpReach) @ "cell" @ string(Cell));

    Lo = vect(99999.0, 99999.0, 99999.0);
    Hi = vect(-99999.0, -99999.0, -99999.0);
    foreach AllActors(class'PlayerStart', P)
    {
        Lo.X = MinF(Lo.X, P.Location.X);
        Lo.Y = MinF(Lo.Y, P.Location.Y);
        Lo.Z = MinF(Lo.Z, P.Location.Z);
        Hi.X = MaxF(Hi.X, P.Location.X);
        Hi.Y = MaxF(Hi.Y, P.Location.Y);
        Hi.Z = MaxF(Hi.Z, P.Location.Z);
        seeds++;
    }
    if (seeds == 0)
    {
        Log("LMEmuBake sem start");
        Finish();
        return;
    }
    Log("LMEmuBake mapa" @ MapName @ "limites" @ string(Lo.X) @ string(Lo.Y) @ string(Lo.Z) @ string(Hi.X) @ string(Hi.Y) @ string(Hi.Z));
    foreach AllActors(class'PlayerStart', P)
    {
        Log("LMEmuBake start" @ string(P.Location.X) @ string(P.Location.Y) @ string(P.Location.Z) @ "time" @ string(P.TeamNumber));
        if (FirstFloor(P.Location.X, P.Location.Y, P.Location.Z + 300.0, P.Location.Z - 1000.0, fz))
            NodeAt(P.Location.X, P.Location.Y, fz + Hgt);
        else
            Log("LMEmuBake start sem piso" @ string(P.Location.X) @ string(P.Location.Y) @ string(P.Location.Z));
    }
}

// Expande o nó u: as 8 células vizinhas, cada coluna varrida de cima para baixo (todos os pisos).
function Expand(int u)
{
    local vector P, S, E, HL, HN;
    local float uf, cx, cy;
    local int ax, ay, k;

    P = NPos[u];
    uf = P.Z - Hgt;
    for (ax = -1; ax <= 1; ax++)
    {
        for (ay = -1; ay <= 1; ay++)
        {
            if (ax == 0 && ay == 0)
                continue;
            cx = P.X + ax * Cell;
            cy = P.Y + ay * Cell;
            if (!InBox(cx, cy, P.Z))
                continue;
            S.X = cx; S.Y = cy; S.Z = uf + FlyMax + 30.0;
            E.X = cx; E.Y = cy; E.Z = uf - MaxDrop - 10.0;
            NCols++;
            for (k = 0; k < 24; k++)
            {
                if (!Under(S, E, HL, HN))
                    break;
                if (VSize(HL - S) < 1.0)
                {
                    // começou dentro de sólido (espessura do piso): desce e procura de novo
                    S.Z -= 8.0;
                    if (S.Z <= E.Z)
                        break;
                    continue;
                }
                NHits++;
                if (HN.Z >= WALK_NZ)
                {
                    NFloor++;
                    TryEdge(u, P, uf, cx, cy, HL.Z);
                }
                S.Z = HL.Z - 2.0;
                if (S.Z <= E.Z)
                    break;
            }
        }
    }
}

// Aresta de u para o piso fz da célula (cx,cy): classifica pela diferença de altura e checa destino,
// passagem e (para 'w') o piso no meio do caminho. Só então cria ou reaproveita o nó de destino.
function TryEdge(int u, vector P, float uf, float cx, float cy, float fz)
{
    local vector A, B, D, Pe, Pb;
    local string F;
    local float dz, dh;
    local int v;

    dz = fz - uf;
    if (dz <= -StepH)
        F = "f";
    else if (dz < StepH)
        F = "w";
    else if (dz <= Apex)
        F = "j";
    else
        F = "b";
    D.X = cx - P.X;
    D.Y = cy - P.Y;
    dh = VSize(D);
    if (F == "j" && dh > JumpReach)
        return;
    A = P;
    B.X = cx; B.Y = cy; B.Z = fz + Hgt;
    if (Bad(B))
    {
        NBad++;
        return;
    }
    // Folga: raio até o teto e passagem no centro. Andar e cair também checam acima do degrau (o pawn
    // passa por cima do que tem até StepH). Pulo e booster não andam em linha reta: só o centro.
    Pe = vect(0.0, 0.0, 1.0) * (StepH + 8.0 - Hgt);
    Pb = vect(0.0, 0.0, 1.0) * Hgt;
    if (Obstruido(B, B + Pb))
    {
        NHead++;
        return;
    }
    if (Obstruido(A, B) || ((F == "w" || F == "f") && Obstruido(A + Pe, B + Pe)))
    {
        NHoriz++;
        return;
    }
    if (F == "w" && !MidFloor((A.X + B.X) * 0.5, (A.Y + B.Y) * 0.5, MinF(A.Z, B.Z) - Hgt - StepH, MaxF(A.Z, B.Z) - Hgt + StepH))
    {
        NMid++;
        return;
    }
    v = NodeAt(cx, cy, B.Z);
    if (v < 0)
        return;
    Log("LMEmuBake link" @ string(u) @ string(v) @ F);
    Links++;
}

// Ponto que o pawn não pode ocupar: água, dano ou morte por Z. Volume que toca a esfera do pawn conta
// (conservador: barra também a beira da água).
function bool Bad(vector L)
{
    local PhysicsVolume PV;

    foreach CollidingActors(class'PhysicsVolume', PV, Rad, L)
    {
        if (PV.bWaterVolume || PV.IsA('PainVolume') || PV.IsA('KillZVolume'))
            return true;
    }
    return false;
}

// Primeiro hit de S até E (só geometria do mapa); verdadeiro se bateu. Sem batida o motor devolve HL e
// HN zerados (não o fim do trace), então batida é HL diferente de zero.
function bool Under(vector S, vector E, out vector HL, out vector HN)
{
    HL = vect(0.0, 0.0, 0.0);
    HN = vect(0.0, 0.0, 0.0);
    Trace(HL, HN, E, S, false);
    return VSize(HL) >= 1.0;
}

// Há geometria entre S e E (raio pontual)?
function bool Obstruido(vector S, vector E)
{
    local vector HL, HN;

    return Under(S, E, HL, HN);
}

// Primeiro piso caminhável na coluna (X,Y) entre Bot e Top.
function bool FirstFloor(float X, float Y, float Top, float Bot, out float Fz)
{
    local vector S, E, HL, HN;
    local int k;

    S.X = X; S.Y = Y; S.Z = Top;
    E.X = X; E.Y = Y; E.Z = Bot;
    for (k = 0; k < 8; k++)
    {
        if (!Under(S, E, HL, HN))
            return false;
        if (HN.Z >= WALK_NZ)
        {
            Fz = HL.Z;
            return true;
        }
        S.Z = HL.Z - 2.0;
        if (S.Z <= Bot)
            return false;
    }
    return false;
}

// Há piso caminhável na coluna (X,Y) entre Lo e Hi?
function bool MidFloor(float X, float Y, float Lo2, float Hi2)
{
    local vector S, E, HL, HN;
    local int k;

    S.X = X; S.Y = Y; S.Z = Hi2;
    E.X = X; E.Y = Y; E.Z = Lo2;
    for (k = 0; k < 8; k++)
    {
        if (!Under(S, E, HL, HN))
            return false;
        if (HN.Z >= WALK_NZ)
            return true;
        S.Z = HL.Z - 2.0;
        if (S.Z <= Lo2)
            return false;
    }
    return false;
}

// Índice do nó da célula de (X,Y,Z), criando-o se é novo. -1 se o teto ou a caixa barram.
function int NodeAt(float X, float Y, float Z)
{
    local int ix, iy, iz, h, n;

    ix = CellOf(X, Cell);
    iy = CellOf(Y, Cell);
    iz = CellOf(Z, 16.0);
    h = (ix * 73856093 + iy * 19349663 + iz * 83492791) & (HASH_SIZE - 1);
    while (Table[h] != 0)
    {
        n = Table[h] - 1;
        if (NIX[n] == ix && NIY[n] == iy && NIZ[n] == iz)
            return n;
        h = (h + 1) & (HASH_SIZE - 1);
    }
    if (NPos.Length >= NodeCap)
    {
        bCap = true;
        return -1;
    }
    if (!InBox(X, Y, Z))
        return -1;
    n = NPos.Length;
    NPos.Length = n + 1;
    NIX.Length = n + 1;
    NIY.Length = n + 1;
    NIZ.Length = n + 1;
    NPos[n].X = X;
    NPos[n].Y = Y;
    NPos[n].Z = Z;
    NIX[n] = ix;
    NIY[n] = iy;
    NIZ[n] = iz;
    Table[h] = n + 1;
    Log("LMEmuBake node" @ string(n) @ string(X) @ string(Y) @ string(Z));
    return n;
}

function int CellOf(float V, float S)
{
    if (V >= 0.0)
        return int(V / S + 0.5);
    return -int(-V / S + 0.5);
}

function bool InBox(float X, float Y, float Z)
{
    return X >= Lo.X - Reach && X <= Hi.X + Reach && Y >= Lo.Y - Reach && Y <= Hi.Y + Reach && Z >= Lo.Z - Reach && Z <= Hi.Z + Reach;
}

function Finish()
{
    if (bDone)
        return;
    bDone = true;
    SetTimer(0.0, false);
    Log("LMEmuBake diag colunas" @ string(NCols) @ "hits" @ string(NHits) @ "pisos" @ string(NFloor) @ "agua" @ string(NBad) @ "teto" @ string(NHead) @ "lado" @ string(NHoriz) @ "meio" @ string(NMid));
    Log("LMEmuBake fim nos" @ string(NPos.Length) @ "arestas" @ string(Links) @ "teto" @ string(bCap) @ "tempo" @ string(Level.TimeSeconds));
    Level.ConsoleCommand("exit");
}

function float MinF(float A, float B)
{
    if (A < B)
        return A;
    return B;
}

function float MaxF(float A, float B)
{
    if (A > B)
        return A;
    return B;
}

defaultproperties
{
    RemoteRole=ROLE_None
    bHidden=true
    Cell=160.0
    StepH=40.0
    MaxDrop=600.0
    FlyMax=500.0
    Reach=3000.0
    NodeCap=20000
    PerTick=40
}
