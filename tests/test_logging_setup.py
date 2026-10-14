"""Log do processo (D205): uma linha JSON por registro, com o erro em `exc`; texto por padrão."""

import io
import json
import logging
import sys

from landmass_emu.logging_setup import JsonFormatter, LogSetup


def test_formato_json_tem_um_objeto_por_linha_e_escapa_o_texto() -> None:
    fluxo = io.StringIO()
    raiz = logging.getLogger()
    nivel = raiz.level
    handler = LogSetup("INFO", as_json=True, stream=fluxo).apply()
    try:
        logging.getLogger("landmass_emu.teste").info('ação: "a" ação')
    finally:
        raiz.removeHandler(handler)
        raiz.setLevel(nivel)

    [linha] = fluxo.getvalue().splitlines()
    dados = json.loads(linha)
    assert set(dados) == {"ts", "level", "logger", "msg"}
    assert (dados["level"], dados["logger"]) == ("INFO", "landmass_emu.teste")
    assert dados["msg"] == 'ação: "a" ação'


def test_erro_vai_no_campo_exc() -> None:
    try:
        raise ValueError("ruim")
    except ValueError:
        registro = logging.LogRecord(
            "x", logging.ERROR, __file__, 1, "falhou", None, sys.exc_info()
        )
    dados = json.loads(JsonFormatter().format(registro))
    assert dados["msg"] == "falhou"
    assert "ValueError: ruim" in dados["exc"]


def test_texto_e_o_padrao_sem_json() -> None:
    fluxo = io.StringIO()
    raiz = logging.getLogger()
    nivel = raiz.level
    handler = LogSetup("INFO", as_json=False, stream=fluxo).apply()
    try:
        logging.getLogger("landmass_emu.teste").warning("atenção")
    finally:
        raiz.removeHandler(handler)
        raiz.setLevel(nivel)

    [linha] = fluxo.getvalue().splitlines()
    assert linha.endswith(" atenção")
    assert not linha.startswith("{")
