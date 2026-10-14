"""Gerador de rotas (tools/routes/rotas.py, D225/D226): bake, LMEmuRec, flags e escrita do ini.

O script fica em tools/, fora do pacote `src`, então é carregado pelo caminho do arquivo.
"""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def rotas() -> ModuleType:
    spec = importlib.util.spec_from_file_location("rotas", RAIZ / "tools" / "routes" / "rotas.py")
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _linha(
    rotas: ModuleType,
    *,
    t: float,
    x: float,
    y: float,
    z: float,
    fis: str = "walk",
    vz: float = 0.0,
    boost: int = 0,
    pid: int = 1,
    vida: int = 1,
    mapa: str = "ONS-AirPort",
) -> str:
    return (
        f"LMEmuRec map={mapa} t={t:.6f} pid={pid} vida={vida} x={x:.6f} y={y:.6f} z={z:.6f} "
        f"fis={fis} vz={vz:.6f} boost={boost}"
    )


def _grafo(rotas: ModuleType, linhas: list[str]) -> object:
    amostras = rotas.LeitorLog().amostras("\n".join(linhas))
    return rotas.ConstrutorGrafo().construir(amostras)["ONS-AirPort"]


def test_le_so_linhas_lmemurec_e_ignora_valor_invalido(rotas: ModuleType) -> None:
    texto = "\n".join(
        [
            "LMEmu: bot Bot1 morat 1",
            _linha(rotas, t=1.0, x=0, y=0, z=0),
            "LMEmuRec map=ONS-AirPort t=abc pid=1 vida=1 x=0 y=0 z=0 fis=walk vz=0 boost=0",
        ]
    )
    amostras = rotas.LeitorLog().amostras(texto)
    assert len(amostras) == 1
    assert amostras[0].mapa == "ONS-AirPort"
    assert amostras[0].chao


def test_amostras_proximas_viram_um_no(rotas: ModuleType) -> None:
    grafo = _grafo(
        rotas,
        [
            _linha(rotas, t=1.0, x=0, y=0, z=0),
            _linha(rotas, t=1.5, x=60, y=40, z=5),
        ],
    )
    assert len(grafo.nos) == 1
    assert grafo.nos[0][:2] == (30, 20)
    assert grafo.arestas == ()


def test_aresta_dirigida_entre_nos_consecutivos(rotas: ModuleType) -> None:
    grafo = _grafo(
        rotas,
        [
            _linha(rotas, t=1.0, x=0, y=0, z=0),
            _linha(rotas, t=1.5, x=1000, y=0, z=0),
            _linha(rotas, t=2.0, x=1000, y=0, z=0),
        ],
    )
    assert len(grafo.nos) == 2
    assert grafo.arestas == ((0, 1, "w"),)


def test_lacuna_de_tempo_quebra_a_cadeia(rotas: ModuleType) -> None:
    grafo = _grafo(
        rotas,
        [
            _linha(rotas, t=1.0, x=0, y=0, z=0),
            _linha(rotas, t=10.0, x=1000, y=0, z=0),
        ],
    )
    assert grafo.arestas == ()


def test_salto_grande_de_posicao_quebra_a_cadeia(rotas: ModuleType) -> None:
    grafo = _grafo(
        rotas,
        [
            _linha(rotas, t=1.0, x=0, y=0, z=0),
            _linha(rotas, t=1.5, x=5000, y=0, z=0),
        ],
    )
    assert grafo.arestas == ()


def test_pulo_marca_aresta_quando_o_ar_sobe_acima_do_degrau(rotas: ModuleType) -> None:
    grafo = _grafo(
        rotas,
        [
            _linha(rotas, t=1.0, x=0, y=0, z=0),
            _linha(rotas, t=1.5, x=200, y=0, z=200, fis="fall", vz=300.0),
            _linha(rotas, t=2.0, x=400, y=0, z=0),
        ],
    )
    assert len(grafo.nos) == 2
    assert grafo.arestas == ((0, 1, "j"),)


def test_queda_sem_subida_nao_marca_pulo(rotas: ModuleType) -> None:
    grafo = _grafo(
        rotas,
        [
            _linha(rotas, t=1.0, x=0, y=0, z=200),
            _linha(rotas, t=1.5, x=200, y=0, z=150, fis="fall", vz=-200.0),
            _linha(rotas, t=2.0, x=400, y=0, z=0),
        ],
    )
    assert grafo.arestas == ((0, 1, "w"),)


def test_booster_no_ar_marca_aresta(rotas: ModuleType) -> None:
    grafo = _grafo(
        rotas,
        [
            _linha(rotas, t=1.0, x=0, y=0, z=0),
            _linha(rotas, t=1.5, x=300, y=0, z=20, fis="fly", boost=1),
            _linha(rotas, t=2.0, x=600, y=0, z=0),
        ],
    )
    assert grafo.arestas == ((0, 1, "b"),)


def test_vida_nova_ou_pessoa_nova_nao_liga_cadeias(rotas: ModuleType) -> None:
    grafo = _grafo(
        rotas,
        [
            _linha(rotas, t=1.0, x=0, y=0, z=0, vida=1),
            _linha(rotas, t=1.5, x=1000, y=0, z=0, vida=2),
            _linha(rotas, t=2.0, x=1000, y=0, z=0, vida=2, pid=2),
        ],
    )
    assert grafo.arestas == ()


def test_saida_e_deterministica(rotas: ModuleType) -> None:
    linhas = [
        _linha(rotas, t=1.0, x=0, y=0, z=0),
        _linha(rotas, t=1.5, x=900, y=0, z=0),
        _linha(rotas, t=2.0, x=900, y=900, z=0),
        _linha(rotas, t=2.5, x=0, y=900, z=0),
    ]
    assert _grafo(rotas, linhas) == _grafo(rotas, linhas)


def test_escrita_troca_so_a_secao_do_mapa(rotas: ModuleType, tmp_path: Path) -> None:
    ini = tmp_path / "LMEmuRoutes.ini"
    ini.write_text(
        "; outro\n[Outro LMEmuRoutes]\nWaypoint=1,1,1\n\n"
        "[ONS-AirPort LMEmuRoutes]\nWaypoint=9,9,9\n",
        encoding="cp1252",
    )
    grafo = rotas.Grafo(nos=((0, 0, 0), (900, 0, 0)), arestas=((0, 1, "jw"),))
    rotas.EscritorRotas(ini).gravar({"ONS-AirPort": grafo})
    assert ini.read_text(encoding="cp1252") == (
        "; outro\n[Outro LMEmuRoutes]\nWaypoint=1,1,1\n\n"
        "[ONS-AirPort LMEmuRoutes]\nWaypoint=0,0,0\nWaypoint=900,0,0\nLink=0,1,jw\n"
    )


def test_escrita_em_arquivo_novo_tem_cabecalho(rotas: ModuleType, tmp_path: Path) -> None:
    ini = tmp_path / "sub" / "LMEmuRoutes.ini"
    grafo = rotas.Grafo(nos=((5, 6, 7),), arestas=())
    rotas.EscritorRotas(ini).gravar({"M": grafo})
    assert ini.read_text(encoding="cp1252") == (
        f"{rotas.CABECALHO}\n\n[M LMEmuRoutes]\nWaypoint=5,6,7\n"
    )


def test_main_grava_a_partir_de_pasta_de_logs(rotas: ModuleType, tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "partida.log").write_text(
        "\n".join(
            [
                _linha(rotas, t=1.0, x=0, y=0, z=0),
                _linha(rotas, t=1.5, x=900, y=0, z=0),
            ]
        ),
        encoding="latin-1",
    )
    ini = tmp_path / "LMEmuRoutes.ini"
    assert rotas.main(["--log", str(logs), "--ini", str(ini)]) == 0
    assert "[ONS-AirPort LMEmuRoutes]" in ini.read_text(encoding="cp1252")
    assert "Link=0,1,w" in ini.read_text(encoding="cp1252")


def test_main_sem_amostra_nao_grava(rotas: ModuleType, tmp_path: Path) -> None:
    log = tmp_path / "vazio.log"
    log.write_text("LMEmu: nada aqui\n", encoding="latin-1")
    ini = tmp_path / "LMEmuRoutes.ini"
    assert rotas.main(["--log", str(log), "--ini", str(ini)]) == 1
    assert not ini.exists()


def _bake(mapa: str, *linhas: str) -> str:
    return "\n".join([f"LMEmuBake mapa {mapa} limites 0 0 0 1 1 1", *linhas])


def test_bake_le_nos_arestas_e_inicios(rotas: ModuleType) -> None:
    texto = _bake(
        "ONS-Airport",
        "ScriptLog: LMEmuBake node 0 0.00 0.00 0.00",
        "ScriptLog: LMEmuBake node 1 160.00 0.00 0.00",
        "ScriptLog: LMEmuBake link 0 1 w",
        "ScriptLog: LMEmuBake link 1 0 j",
        "ScriptLog: LMEmuBake start 0.00 0.00 0.00 time 0",
        "ScriptLog: LMEmuBake start 160.00 0.00 0.00 time 1",
        "ScriptLog: LMEmuBake fim nos 2 arestas 2",
    )
    bake = rotas.LeitorBake().mapas(texto)["ONS-Airport"]
    assert bake.grafo.nos == ((0, 0, 0), (160, 0, 0))
    assert bake.grafo.arestas == ((0, 1, "w"), (1, 0, "j"))
    assert bake.inicios == (((0, 0, 0), 0), ((160, 0, 0), 1))


def test_bake_remapeia_ids_que_nao_comecam_em_zero(rotas: ModuleType) -> None:
    texto = _bake(
        "M",
        "LMEmuBake node 5 0 0 0",
        "LMEmuBake node 9 160 0 0",
        "LMEmuBake link 5 9 w",
    )
    bake = rotas.LeitorBake().mapas(texto)["M"]
    assert bake.grafo.arestas == ((0, 1, "w"),)


def test_resumo_mostra_conectividade_nos_dois_sentidos(rotas: ModuleType) -> None:
    bake = rotas.Bake(
        grafo=rotas.Grafo(nos=((0, 0, 0), (160, 0, 0)), arestas=((0, 1, "w"),)),
        inicios=(((0, 0, 0), 0), ((160, 0, 0), 1)),
    )
    linhas = rotas.resumo("M", bake)
    assert linhas[0] == "M: 2 nos, 1 arestas (w 1 f 0 j 0 b 0)"
    assert "time0 -> time1: sim, 1 passos" in linhas
    assert "time1 -> time0: nao" in linhas


def test_main_com_bake_grava_so_o_mapa_pedido(rotas: ModuleType, tmp_path: Path) -> None:
    log = tmp_path / "bake.log"
    log.write_text(
        _bake("ONS-Airport", "LMEmuBake node 0 0 0 0", "LMEmuBake start 0 0 0 time 0")
        + "\n"
        + _bake("Outro", "LMEmuBake node 0 0 0 0"),
        encoding="latin-1",
    )
    ini = tmp_path / "LMEmuRoutes.ini"
    assert rotas.main(["--log", str(log), "--mapa", "ONS-Airport", "--ini", str(ini)]) == 0
    texto = ini.read_text(encoding="cp1252")
    assert "[ONS-Airport LMEmuRoutes]" in texto
    assert "[Outro LMEmuRoutes]" not in texto
    assert rotas.main(["--log", str(log), "--mapa", "Nao", "--ini", str(ini)]) == 1
