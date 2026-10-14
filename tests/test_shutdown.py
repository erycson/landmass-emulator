"""Desligamento (D202): prazo, avisos escalonados, saída antecipada, encurtamento e sinais.
O tempo é um relógio falso: `sleep` só avança o relógio, então o teste não espera de verdade."""

import asyncio
import signal

import pytest

from landmass_emu.shutdown import Shutdown, format_remaining, install_signals, notice_text


class _Relogio:
    def __init__(self) -> None:
        self.agora = 0.0

    def __call__(self) -> float:
        return self.agora

    async def dormir(self, segundos: float) -> None:
        self.agora += segundos


class _Porta:
    """Canal falso: guarda cada aviso com a hora em que saiu e conta o encerramento de partidas."""

    def __init__(self, relogio: _Relogio, jogadores: int) -> None:
        self._relogio = relogio
        self.jogadores = jogadores
        self.avisos: list[tuple[float, str]] = []
        self.partidas_encerradas = 0

    def notify(self, text: str) -> None:
        self.avisos.append((self._relogio.agora, text))

    def players(self) -> int:
        return self.jogadores

    async def end_matches(self) -> None:
        self.partidas_encerradas += 1


@pytest.mark.parametrize(
    ("segundos", "esperado"),
    [(300, "5 min"), (299.2, "5 min"), (60, "1 min"), (59.9, "1 min"), (10, "10 s"), (9.9, "10 s")],
)
def test_formato_do_tempo_arredonda_para_cima(segundos: float, esperado: str) -> None:
    assert format_remaining(segundos) == esperado


def test_formato_do_tempo_nao_fica_negativo() -> None:
    assert format_remaining(-3) == "0 s"


def test_texto_do_aviso_usa_a_mensagem_ou_o_padrao() -> None:
    assert notice_text("", 300) == "O servidor será desligado. Desligamento em 5 min."
    assert notice_text("  Manutenção às 22h.  ", 60) == (
        "Manutenção às 22h. Desligamento em 1 min."
    )


async def test_avisos_nos_instantes_e_encerramento_no_prazo() -> None:
    relogio = _Relogio()
    porta = _Porta(relogio, jogadores=2)
    desliga = Shutdown([300, 60, 10], clock=relogio)
    desliga.attach(porta)
    desliga.begin(100, "Manutenção.")

    await desliga.run(sleep=relogio.dormir, poll=0.5)

    assert porta.avisos == [
        (0.0, "Manutenção. Desligamento em 2 min."),  # o aviso de 300 s já está coberto
        (40.0, "Manutenção. Desligamento em 1 min."),
        (90.0, "Manutenção. Desligamento em 10 s."),
    ]
    assert relogio.agora == 100.0
    assert porta.partidas_encerradas == 1


async def test_lobby_vazio_encerra_antes_do_prazo_com_um_aviso() -> None:
    relogio = _Relogio()
    porta = _Porta(relogio, jogadores=0)
    desliga = Shutdown([300, 60, 10], clock=relogio)
    desliga.attach(porta)
    desliga.begin(300)

    await desliga.run(sleep=relogio.dormir)

    assert len(porta.avisos) == 1
    assert relogio.agora == 0.0
    assert porta.partidas_encerradas == 1


async def test_pedido_seguinte_so_encurta_o_prazo() -> None:
    relogio = _Relogio()
    porta = _Porta(relogio, jogadores=1)
    desliga = Shutdown(clock=relogio)
    desliga.attach(porta)
    desliga.begin(100)
    desliga.begin(500)  # mais longe: não vale
    assert not desliga.accepting()
    desliga.begin(20)  # mais perto: vale
    await desliga.run(sleep=relogio.dormir)
    assert relogio.agora == 20.0


async def test_sem_avisos_configurados_sai_no_prazo_com_o_aviso_do_pedido() -> None:
    relogio = _Relogio()
    porta = _Porta(relogio, jogadores=1)
    desliga = Shutdown(clock=relogio)
    desliga.attach(porta)
    desliga.begin(30)
    await desliga.run(sleep=relogio.dormir)
    assert [texto for _, texto in porta.avisos] == [
        "O servidor será desligado. Desligamento em 30 s."
    ]
    assert relogio.agora == 30.0


async def test_aceite_fecha_no_primeiro_pedido() -> None:
    desliga = Shutdown(clock=_Relogio())
    assert desliga.accepting()
    desliga.begin(0)
    assert not desliga.accepting()


async def test_run_sem_porta_e_erro() -> None:
    desliga = Shutdown()
    desliga.begin(0)
    with pytest.raises(RuntimeError, match="attach"):
        await desliga.run()


async def test_sinal_pede_o_desligamento_e_segundo_sinal_encerra_ja() -> None:
    relogio = _Relogio()
    porta = _Porta(relogio, jogadores=1)
    desliga = Shutdown(clock=relogio)
    desliga.attach(porta)
    anterior = signal.getsignal(signal.SIGINT)
    restaura = install_signals(desliga, grace=300)
    try:
        signal.raise_signal(signal.SIGINT)
        await asyncio.sleep(0)  # o tratador agenda o pedido no loop
        assert not desliga.accepting()
        signal.raise_signal(signal.SIGINT)
        await asyncio.sleep(0)
        await desliga.run(sleep=relogio.dormir)
    finally:
        restaura()
    assert relogio.agora == 0.0  # o segundo sinal zerou o prazo
    assert porta.partidas_encerradas == 1
    assert signal.getsignal(signal.SIGINT) is anterior
