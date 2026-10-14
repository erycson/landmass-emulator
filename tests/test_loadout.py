"""Equipamento da partida para o LMEmu (D190): apelido em hex, opções do morat (peça montada ou
padrão do `DefaultSet`), pinturas, eventslot, grupo só em modo de time e o serviço sobre as
portas."""

import logging

import pytest

from landmass_emu.domain.equipment import SKIN_SLOTS, SLOT_NAMES
from landmass_emu.domain.inventory import ApplyFlag, ItemUnit, MoratUnit
from landmass_emu.domain.loadout import (
    PIECES,
    SKINS,
    LoadoutMember,
    LoadoutService,
    event_options,
    morat_options,
    nickname_hex,
    nickname_option,
    player_line,
    team_options,
)
from landmass_emu.domain.match import GAME_BOMBING, GAME_DEATHMATCH, GAME_OPERATION, GAME_TEAM

DEFAULTS = {
    "MainWeapon": 201030001,
    "SubWeapon": 201070001,
    "EtcWeapon1": 201010001,
    "EtcWeapon3": 0,
    "Booster": 203000001,
    "Skin1": 307010001,
    "Skin2": 0,
}


class _Inventario:
    def __init__(self, morats: list[MoratUnit], items: list[ItemUnit]) -> None:
        self._morats = morats
        self._items = items

    async def morats(self, account_id: int) -> list[MoratUnit]:
        return self._morats

    async def items(self, account_id: int) -> list[ItemUnit]:
        return self._items


class _Contas:
    async def regular_nest(self, account_id: int) -> int:
        return 2


class _Catalogo:
    """`DefaultSet` só para o morat 101000001; os demais não têm set."""

    def default_set(self, morat_id: int) -> dict[str, int]:
        return DEFAULTS if morat_id == 101000001 else {}


def _item(
    index: int,
    catalog_id: int,
    *,
    morat: int | None = None,
    slot: str | None = None,
    system: int | None = None,
) -> ItemUnit:
    return ItemUnit(
        account_id=7,
        inventory_index=index,
        catalog_id=catalog_id,
        item_guid=f"guid-{index}",
        apply_flag=ApplyFlag.REALTIME,
        apply_value=None,
        expires_at=None,
        account_morat_id=morat,
        slot_name=slot,
        system_slot=system,
    )


def _morat(gate: int, morat_id: int, catalog_id: int) -> MoratUnit:
    return MoratUnit(
        account_id=7,
        inventory_index=gate,
        catalog_id=catalog_id,
        item_guid=f"morat-{gate}",
        gate_index=gate,
        apply_flag=ApplyFlag.UNLIMIT,
        apply_value=None,
        expires_at=None,
        id=morat_id,
    )


def _opcoes(linha: str) -> dict[str, str]:
    """Opções de uma linha `<HEX>|?nome=valor...`, como `LMEmuLoadout.Inject` as lê."""
    _, _, resto = linha.partition("|")
    return dict(par.split("=", 1) for par in resto.split("?") if par)


def test_pieces_e_skins_cobrem_os_slots_do_morat() -> None:
    assert {slot for slot, _, _ in PIECES} <= set(SLOT_NAMES)
    assert {slot for slot, _, _ in SKINS} == set(SKIN_SLOTS)


def test_chave_do_jogador_e_hex_com_quatro_digitos_por_caractere() -> None:
    assert nickname_hex("Ana") == "0041006E0061"


def test_apelido_sem_interrogacao_e_sem_o_que_nao_cabe_no_cp1252() -> None:
    # "Ω" não existe em cp1252: o arquivo gravaria `?`, que é separador de opção.
    assert nickname_option("A?naΩ") == "Ana"


def test_peca_montada_vence_o_padrao_e_slot_vazio_vem_do_defaultset() -> None:
    morat = _morat(gate=1, morat_id=5, catalog_id=101000001)
    items = [_item(10, 201030009, morat=5, slot="main_weapon")]

    opcoes = dict(morat_options(morat, items, DEFAULTS))

    assert opcoes["weapon_main"] == 201030009  # montada
    assert opcoes["weapon_sub"] == 201070001  # vazia: DefaultSet
    assert opcoes["weapon_etc0"] == 201010001
    assert opcoes["weapon_etc2"] == 0  # DefaultSet com valor vazio
    assert opcoes["booster"] == 203000001
    assert opcoes["head"] == 0  # sem padrão no set


def test_peca_de_outro_morat_nao_entra_neste() -> None:
    morat = _morat(gate=1, morat_id=5, catalog_id=101000001)
    items = [_item(10, 201030009, morat=6, slot="main_weapon")]

    assert dict(morat_options(morat, items, DEFAULTS))["weapon_main"] == 201030001


def test_pintura_montada_vence_skin1_do_defaultset() -> None:
    morat = _morat(gate=1, morat_id=5, catalog_id=101000001)

    sem_pintura = dict(morat_options(morat, [], DEFAULTS))
    com_pintura = dict(
        morat_options(morat, [_item(11, 307010005, morat=5, slot="skin_00")], DEFAULTS)
    )

    assert (sem_pintura["skin0"], sem_pintura["skin1"]) == (307010001, 0)
    assert com_pintura["skin0"] == 307010005


def test_eventslot_montado_no_slot_e_zero_nos_vazios() -> None:
    opcoes = dict(event_options([_item(12, 301000001, system=3)]))

    assert len(opcoes) == 10
    assert opcoes["eventslot3"] == 301000001
    assert opcoes["eventslot0"] == 0


def test_grupo_so_em_modo_de_time_e_com_pelo_menos_dois() -> None:
    assert team_options(GAME_DEATHMATCH, 1, 2) == []
    assert team_options(GAME_TEAM, 3, 2) == [("Team", 1)]
    assert team_options(GAME_OPERATION, 2, 1) == [("Team", 0)]  # OP: mínimo de dois grupos
    assert team_options(GAME_BOMBING, 1, 1) == [("Team", 1)]


def test_linha_tem_chave_hex_e_opcoes_em_ordem() -> None:
    assert player_line("Ana", [("Team", 1), ("morats", 101000001)]) == (
        "0041006E0061|?Team=1?morats=101000001"
    )


async def test_servico_monta_a_linha_com_o_morat_do_gate_escolhido() -> None:
    servico = LoadoutService(
        catalog=_Catalogo(),
        inventory=_Inventario(
            [_morat(0, 4, 101000001), _morat(1, 5, 102000001)],
            [_item(10, 201030009, morat=5, slot="main_weapon")],
        ),
        accounts=_Contas(),
    )

    [linha] = await servico.lines([LoadoutMember(7, "Ana", slot=1, gate=1)], GAME_TEAM, 2)

    opcoes = _opcoes(linha)
    assert linha.startswith("0041006E0061|?Team=1?morats=102000001?weapon_main=201030009")
    assert opcoes["nickname"] == "Ana"
    assert (opcoes["gender"], opcoes["nest"], opcoes["pc_room"]) == ("0", "2", "0")
    assert (opcoes["clan"], opcoes["costume"]) == ("0", "0")


async def test_espectador_leva_so_a_opcao_de_espectador_sem_morat() -> None:
    servico = LoadoutService(
        catalog=_Catalogo(),
        inventory=_Inventario([], []),  # sem morat nenhum: o espectador não precisa de um (D197)
        accounts=_Contas(),
    )

    [linha] = await servico.lines(
        [LoadoutMember(9, "Bia", slot=60, gate=0, spectator=True)], GAME_TEAM, 2
    )

    assert linha == nickname_hex("Bia") + "|?SpectatorOnly=1"


async def test_dm_nao_leva_grupo_e_gate_sem_morat_fica_sem_linha(
    caplog: pytest.LogCaptureFixture,
) -> None:
    servico = LoadoutService(
        catalog=_Catalogo(),
        inventory=_Inventario([_morat(0, 4, 101000001)], []),
        accounts=_Contas(),
    )

    with caplog.at_level(logging.WARNING):
        linhas = await servico.lines(
            [LoadoutMember(7, "Ana", slot=0, gate=0), LoadoutMember(9, "Bia", slot=1, gate=3)],
            GAME_DEATHMATCH,
            2,
        )

    assert len(linhas) == 1
    assert "Team" not in _opcoes(linhas[0])
    assert "sem morat no gate 3" in caplog.text


async def test_erro_do_catalogo_sobe_para_quem_chama() -> None:
    class _CatalogoQuebrado:
        def default_set(self, morat_id: int) -> dict[str, int]:
            raise ValueError("catálogo ilegível")

    servico = LoadoutService(
        catalog=_CatalogoQuebrado(),
        inventory=_Inventario([_morat(0, 4, 101000001)], []),
        accounts=_Contas(),
    )

    with pytest.raises(ValueError, match="ilegível"):
        await servico.lines([LoadoutMember(7, "Ana", slot=0, gate=0)], GAME_DEATHMATCH, 2)
