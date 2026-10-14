"""Rotas dos bots: geração por geometria (D225) e, como complemento, gravação humana (D226).

Fonte principal: o LMEmuBake (tools/unreal/LMEmu/Classes/LMEmuBake.uc) roda no servidor headless com
?lmemubake=1 e escreve no log as linhas `LMEmuBake mapa`, `node`, `link` e `start`. Este script lê
essas linhas, grava a seção `[<mapa> LMEmuRoutes]` de LMEmuRoutes.ini e imprime o resumo: contagens
por flag e se as duas bases (time 0 e time 1) se alcançam nos dois sentidos. A poda é a própria
inundação a partir dos PlayerStart: só nós alcançados entram.

Complemento: sem linhas LMEmuBake no log, o script monta o grafo a partir das linhas `LMEmuRec` do
LMEmuRecorder (uma a cada 0,5 s por jogador humano).

Uso: uv run python tools/routes/rotas.py --log <arquivo.log ou pasta> [--log ...]
     [--mapa ONS-Airport] [--ini <caminho>]
"""

import argparse
import math
import re
import sys
from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

PADRAO_INI = Path(__file__).resolve().parents[1] / "server-patch" / "system" / "LMEmuRoutes.ini"
SECAO = "LMEmuRoutes"
CABECALHO = "; gerado por tools/routes/rotas.py a partir do LMEmuBake (D225)"
CABECALHO_SECAO = re.compile(r"^\s*\[([^\]]*)\]\s*$")
FLAGS = "wfjb"
BAKE_MAPA = re.compile(r"LMEmuBake mapa (?P<mapa>\S+) ")
BAKE_NO = re.compile(r"LMEmuBake node (?P<id>\d+) (?P<x>\S+) (?P<y>\S+) (?P<z>\S+)\s*$")
BAKE_ARESTA = re.compile(r"LMEmuBake link (?P<a>\d+) (?P<b>\d+) (?P<flags>[wfjb])\s*$")
BAKE_INICIO = re.compile(r"LMEmuBake start (?P<x>\S+) (?P<y>\S+) (?P<z>\S+) time (?P<time>\d+)\s*$")
LINHA = re.compile(
    r"LMEmuRec map=(?P<mapa>\S+) t=(?P<t>\S+) pid=(?P<pid>-?\d+) vida=(?P<vida>\d+) "
    r"x=(?P<x>\S+) y=(?P<y>\S+) z=(?P<z>\S+) fis=(?P<fis>\w+) vz=(?P<vz>\S+) boost=(?P<boost>[01])"
)
# Valores padrão do gravador (unidades do motor). Um nó junta amostras a até RAIO_NO no plano e
# DIF_Z_NO em altura. Intervalo acima de LACUNA_S ou salto acima de PASSO_MAX quebra a cadeia.
RAIO_NO = 150.0
DIF_Z_NO = 100.0
LACUNA_S = 1.5
PASSO_MAX = 1500.0
# Subida no ar acima disto entre dois pisos marca pulo (aresta com j).
DEGRAU = 40.0

Ponto = tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class Grafo:
    nos: tuple[Ponto, ...]
    # flags: w andar, f queda, j pulo, b booster
    arestas: tuple[tuple[int, int, str], ...]


@dataclass(frozen=True, slots=True)
class Bake:
    grafo: Grafo
    inicios: tuple[tuple[Ponto, int], ...]  # PlayerStart: (posição, time)


@dataclass(frozen=True, slots=True)
class Amostra:
    mapa: str
    t: float
    pid: int
    vida: int
    x: float
    y: float
    z: float
    fis: str  # walk, fall, fly ou other (nome do estado de física do LMEmuRecorder)
    vz: float
    boost: bool

    @property
    def chao(self) -> bool:
        return self.fis == "walk"


class LeitorBake:
    """Linhas LMEmuBake por mapa; um bloco `LMEmuBake mapa` repetido substitui o anterior."""

    def mapas(self, texto: str) -> dict[str, Bake]:
        blocos: dict[str, list[str]] = {}
        atual: str | None = None
        for linha in texto.splitlines():
            casa = BAKE_MAPA.search(linha)
            if casa is not None:
                atual = casa["mapa"]
                blocos[atual] = []
            elif atual is not None and "LMEmuBake " in linha:
                blocos[atual].append(linha)
        return {mapa: self._bake(linhas) for mapa, linhas in blocos.items()}

    def _bake(self, linhas: list[str]) -> Bake:
        nos: dict[int, Ponto] = {}
        arestas: list[tuple[int, int, str]] = []
        inicios: list[tuple[Ponto, int]] = []
        for linha in linhas:
            if (casa := BAKE_NO.search(linha)) is not None:
                nos[int(casa["id"])] = (
                    round(float(casa["x"])),
                    round(float(casa["y"])),
                    round(float(casa["z"])),
                )
            elif (casa := BAKE_ARESTA.search(linha)) is not None:
                arestas.append((int(casa["a"]), int(casa["b"]), casa["flags"]))
            elif (casa := BAKE_INICIO.search(linha)) is not None:
                ponto = (round(float(casa["x"])), round(float(casa["y"])), round(float(casa["z"])))
                inicios.append((ponto, int(casa["time"])))
        ids = sorted(nos)
        novo = {antigo: n for n, antigo in enumerate(ids)}
        validas = tuple((novo[a], novo[b], f) for a, b, f in arestas if a in novo and b in novo)
        grafo = Grafo(nos=tuple(nos[i] for i in ids), arestas=validas)
        return Bake(grafo=grafo, inicios=tuple(inicios))


class LeitorLog:
    """Amostras `LMEmuRec` de um texto de log; outras linhas e valores inválidos são ignorados."""

    def amostras(self, texto: str) -> list[Amostra]:
        saida: list[Amostra] = []
        for linha in texto.splitlines():
            casa = LINHA.search(linha)
            if casa is None:
                continue
            try:
                saida.append(
                    Amostra(
                        mapa=casa["mapa"],
                        t=float(casa["t"]),
                        pid=int(casa["pid"]),
                        vida=int(casa["vida"]),
                        x=float(casa["x"]),
                        y=float(casa["y"]),
                        z=float(casa["z"]),
                        fis=casa["fis"],
                        vz=float(casa["vz"]),
                        boost=casa["boost"] == "1",
                    )
                )
            except ValueError:
                continue
        return saida


class ConstrutorGrafo:
    """Grafo por mapa a partir das gravações. Nós: agrupamento guloso no chão, em ordem de tempo.
    Arestas: chão consecutivo da mesma pessoa e vida; o ar entre os dois define o flag."""

    def __init__(
        self,
        *,
        raio: float = RAIO_NO,
        dif_z: float = DIF_Z_NO,
        lacuna: float = LACUNA_S,
        passo_max: float = PASSO_MAX,
        degrau: float = DEGRAU,
    ) -> None:
        self._raio = raio
        self._dif_z = dif_z
        self._lacuna = lacuna
        self._passo_max = passo_max
        self._degrau = degrau

    def construir(self, amostras: Iterable[Amostra]) -> dict[str, Grafo]:
        por_mapa: dict[str, list[Amostra]] = {}
        for amostra in amostras:
            por_mapa.setdefault(amostra.mapa, []).append(amostra)
        return {mapa: self._grafo(lista) for mapa, lista in sorted(por_mapa.items())}

    def _grafo(self, amostras: list[Amostra]) -> Grafo:
        cadeias = self._cadeias(amostras)
        chao = [a for cadeia in cadeias for a in cadeia if a.chao]
        nos, atribuicao = self._agrupa(chao)
        no_de = {id(a): n for a, n in zip(chao, atribuicao, strict=True)}
        arestas = self._arestas(cadeias, no_de)
        return Grafo(nos=tuple(nos), arestas=tuple(arestas))

    def _cadeias(self, amostras: list[Amostra]) -> list[list[Amostra]]:
        grupos: dict[tuple[int, int], list[Amostra]] = {}
        for amostra in amostras:
            grupos.setdefault((amostra.pid, amostra.vida), []).append(amostra)
        cadeias: list[list[Amostra]] = []
        for chave in sorted(grupos):
            atual: list[Amostra] = []
            for amostra in sorted(grupos[chave], key=lambda a: a.t):
                if atual and self._quebra(atual[-1], amostra):
                    cadeias.append(atual)
                    atual = []
                atual.append(amostra)
            if atual:
                cadeias.append(atual)
        return cadeias

    def _quebra(self, antes: Amostra, depois: Amostra) -> bool:
        salto = math.hypot(depois.x - antes.x, depois.y - antes.y)
        return depois.t - antes.t > self._lacuna or salto > self._passo_max

    def _agrupa(self, pontos: list[Amostra]) -> tuple[list[Ponto], list[int]]:
        # centros: [soma x, soma y, soma z, contagem]
        centros: list[list[float]] = []
        atribuicao: list[int] = []
        for p in pontos:
            idx = self._mais_proximo(centros, p)
            if idx is None:
                centros.append([p.x, p.y, p.z, 1.0])
                idx = len(centros) - 1
            else:
                centro = centros[idx]
                centro[0] += p.x
                centro[1] += p.y
                centro[2] += p.z
                centro[3] += 1.0
            atribuicao.append(idx)
        medias = [(round(c[0] / c[3]), round(c[1] / c[3]), round(c[2] / c[3])) for c in centros]
        ordem = sorted(range(len(medias)), key=lambda i: medias[i])
        novo = {antigo: n for n, antigo in enumerate(ordem)}
        return [medias[i] for i in ordem], [novo[i] for i in atribuicao]

    def _mais_proximo(self, centros: list[list[float]], p: Amostra) -> int | None:
        melhor: int | None = None
        melhor_d = self._raio
        for idx, c in enumerate(centros):
            d = math.hypot(c[0] / c[3] - p.x, c[1] / c[3] - p.y)
            if d <= melhor_d and abs(c[2] / c[3] - p.z) <= self._dif_z:
                melhor, melhor_d = idx, d
        return melhor

    def _arestas(
        self, cadeias: list[list[Amostra]], no_de: Mapping[int, int]
    ) -> list[tuple[int, int, str]]:
        marcas: dict[tuple[int, int], list[bool]] = {}
        for cadeia in cadeias:
            anterior: Amostra | None = None
            ar: list[Amostra] = []
            for amostra in cadeia:
                if not amostra.chao:
                    ar.append(amostra)
                    continue
                if anterior is not None and no_de[id(anterior)] != no_de[id(amostra)]:
                    pulo, booster = self._salto(anterior, ar)
                    chave = (no_de[id(anterior)], no_de[id(amostra)])
                    marca = marcas.setdefault(chave, [False, False])
                    marca[0] = marca[0] or pulo
                    marca[1] = marca[1] or booster
                anterior = amostra
                ar = []
        return [
            (a, b, ("j" if pulo else "") + ("b" if booster else "") or "w")
            for (a, b), (pulo, booster) in sorted(marcas.items())
        ]

    def _salto(self, antes: Amostra, ar: list[Amostra]) -> tuple[bool, bool]:
        if not ar:
            return False, False
        subida = max(p.z for p in ar) - antes.z
        return subida > self._degrau, any(p.boost for p in ar)


def _perto(nos: tuple[Ponto, ...], ponto: Ponto) -> int:
    return min(
        range(len(nos)),
        key=lambda i: math.dist(nos[i], ponto),
    )


def _alcance(origens: set[int], vizinhos: Mapping[int, list[int]]) -> dict[int, int]:
    """Distância em passos (arestas) de qualquer origem até cada nó alcançado."""
    dist = dict.fromkeys(origens, 0)
    fila = deque(sorted(origens))
    while fila:
        u = fila.popleft()
        for v in vizinhos.get(u, ()):
            if v not in dist:
                dist[v] = dist[u] + 1
                fila.append(v)
    return dist


def resumo(mapa: str, bake: Bake) -> list[str]:
    """Contagem por flag e conectividade entre as bases (time 0 e time 1), nos dois sentidos."""
    grafo = bake.grafo
    contagem = " ".join(f"{f} {sum(1 for _, _, fl in grafo.arestas if fl == f)}" for f in FLAGS)
    linhas = [f"{mapa}: {len(grafo.nos)} nos, {len(grafo.arestas)} arestas ({contagem})"]
    if not grafo.nos:
        return linhas
    vizinhos: dict[int, list[int]] = {}
    for a, b, _ in grafo.arestas:
        vizinhos.setdefault(a, []).append(b)
    bases = {time: {_perto(grafo.nos, p) for p, t in bake.inicios if t == time} for time in (0, 1)}
    linhas.append(f"bases: time0 {len(bases[0])} nos de partida, time1 {len(bases[1])}")
    for origem, destino in ((0, 1), (1, 0)):
        if not bases[origem] or not bases[destino]:
            linhas.append(f"time{origem} -> time{destino}: sem base")
            continue
        dist = _alcance(bases[origem], vizinhos)
        alcancados = [dist[n] for n in bases[destino] if n in dist]
        if alcancados:
            linhas.append(f"time{origem} -> time{destino}: sim, {min(alcancados)} passos")
        else:
            linhas.append(f"time{origem} -> time{destino}: nao")
    return linhas


class EscritorRotas:
    """Grava as seções `[<mapa> LMEmuRoutes]`. Seções de outros mapas ficam como estão; as dos mapas
    gravados são trocadas. Texto em cp1252, como o LMEmu.ini."""

    def __init__(self, caminho: Path) -> None:
        self._caminho = caminho

    def gravar(self, grafos: Mapping[str, Grafo]) -> None:
        antigo = (
            self._caminho.read_text(encoding="cp1252").splitlines()
            if self._caminho.exists()
            else []
        )
        nomes = {f"{mapa} {SECAO}" for mapa in grafos}
        linhas = _sem_secoes(antigo, nomes) or [CABECALHO]
        for mapa, grafo in sorted(grafos.items()):
            linhas += ["", f"[{mapa} {SECAO}]"]
            linhas += [f"Waypoint={x},{y},{z}" for x, y, z in grafo.nos]
            linhas += [f"Link={a},{b},{flags}" for a, b, flags in grafo.arestas]
        self._caminho.parent.mkdir(parents=True, exist_ok=True)
        self._caminho.write_text("\n".join(linhas) + "\n", encoding="cp1252")


def _sem_secoes(linhas: list[str], nomes: set[str]) -> list[str]:
    saida: list[str] = []
    descartando = False
    for linha in linhas:
        casa = CABECALHO_SECAO.match(linha)
        if casa is not None:
            descartando = casa.group(1).strip() in nomes
        if not descartando:
            saida.append(linha)
    while saida and saida[-1] == "":
        saida.pop()
    return saida


def _arquivos(caminhos: list[Path]) -> list[Path]:
    saida: list[Path] = []
    for caminho in caminhos:
        if caminho.is_dir():
            saida += sorted(caminho.glob("*.log"))
        else:
            saida.append(caminho)
    return saida


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gera LMEmuRoutes.ini a partir do LMEmuBake.")
    parser.add_argument("--log", type=Path, action="append", required=True)
    parser.add_argument("--mapa", help="gera só este mapa (ex.: ONS-Airport)")
    parser.add_argument("--ini", type=Path, default=PADRAO_INI)
    args = parser.parse_args(argv)

    texto = "\n".join(p.read_text(encoding="latin-1") for p in _arquivos(args.log) if p.is_file())
    bakes = LeitorBake().mapas(texto)
    if bakes:
        if args.mapa is not None:
            bakes = {m: b for m, b in bakes.items() if m == args.mapa}
        if not bakes:
            print(f"sem LMEmuBake do mapa {args.mapa} nos logs", file=sys.stderr)
            return 1
        EscritorRotas(args.ini).gravar({m: b.grafo for m, b in bakes.items()})
        for mapa, bake in sorted(bakes.items()):
            for linha in resumo(mapa, bake):
                print(linha)
        print(f"gravado em {args.ini}")
        return 0

    amostras = LeitorLog().amostras(texto)
    if not amostras:
        print("nenhuma linha LMEmuBake nem LMEmuRec nos logs", file=sys.stderr)
        return 1
    grafos = ConstrutorGrafo().construir(amostras)
    if args.mapa is not None:
        grafos = {m: g for m, g in grafos.items() if m == args.mapa}
    EscritorRotas(args.ini).gravar(grafos)
    for mapa, grafo in grafos.items():
        pulos = sum("j" in flags for _, _, flags in grafo.arestas)
        print(f"{mapa}: {len(grafo.nos)} nos, {len(grafo.arestas)} arestas ({pulos} de pulo)")
    print(f"gravado em {args.ini}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
