"""Bots (D220, D221, D228, D231): sorteio de morat, apelido e peças, linha `Bots=`, `Owner=`,
registro de jogador do `MORATS.upl` e classes do catálogo. O wdb e o `MORATS.upl` daqui são pequenos
e feitos no teste; o teste com os arquivos reais é pulado sem o cliente e o servidor de partida."""

import random
import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest

from landmass_emu.db.item_catalog import ItemCatalog
from landmass_emu.domain.bots import BOT_NAMES, BOT_PREFIX, BotLoadout, player_records
from landmass_emu.domain.equipment import class_allows, slot_of
from landmass_emu.domain.loadout import LoadoutService, owner_entries
from landmass_emu.hosting.loadout import LoadoutFile
from landmass_emu.hosting.player_records import PlayerRecordFile

WDB_REAL = Path("D:/landmass/cliente/system/landmass.wdb")
UPL_REAL = Path("D:/landmass/servidor-partida/system/MORATS.upl")

# Morat 101000001 (Assault, classe 1) e 102000001 (Sniper, classe 10) têm registro; a espécie
# XGame.SPECIES_Sem (morat 104000001) não tem, então não sorteia.
UPL = """\
[Public]
Player=(DefaultName="M_Assault01_0", Mesh=A, species=xGame.SPECIES_AssaultA, Sex=male)
Player=(DefaultName="F_Assault01_0", Mesh=A, species=xGame.SPECIES_AssaultA, Sex=female)
;Player=(DefaultName="M_Human", Mesh=H, species=xGame.SPECIES_Human, Sex=male)
Player=(DefaultName="M_Sniper01_1", Mesh=S, species=xGame.SPECIES_SniperA, Sex=male)
Player=(DefaultName="M_Sniper01_0", Mesh=S, species=xGame.SPECIES_SniperA, Sex=male)
"""

ASSAULT_ONLY = {"xgame.species_assaulta": "M_Assault01_0"}
SNIPER_ONLY = {"xgame.species_snipera": "M_Sniper01_0"}


class _Registros:
    """`RecordSource` fixo: o registro por espécie que o teste quiser."""

    def __init__(self, dados: dict[str, str]) -> None:
        self._dados = dados

    def records(self) -> dict[str, str]:
        return self._dados


def _tabela(con: sqlite3.Connection, nome: str, linhas: list[tuple[str, str, str, str]]) -> None:
    con.execute(f"CREATE TABLE {nome} (type TEXT, section TEXT, key TEXT, value TEXT)")
    con.executemany(f"INSERT INTO {nome} VALUES (?, ?, ?, ?)", linhas)


@pytest.fixture
def wdb(tmp_path: Path) -> Callable[..., Path]:
    """`landmass.wdb` mínimo com o formato EAV. Munição de `201030001` é outra seção do mesmo id.
    `201010003` tem `item_slot` mas nenhuma linha `item_id`: não tem classe. `999999999` no
    `DefaultSet` não existe no catálogo."""

    def criar(*, extra_etc: bool = False) -> Path:
        path = tmp_path / "landmass.wdb"
        path.unlink(missing_ok=True)  # cada chamada recria o arquivo do zero
        con = sqlite3.connect(path)
        try:
            _tabela(
                con,
                "Morats",
                [
                    ("101000001", "XGame.SPECIES_AssaultA", "required_class", "1"),
                    ("101000001", "XGame.SPECIES_AssaultA", "defaultset", "1"),
                    ("102000001", "XGame.SPECIES_SniperA", "required_class", "10"),
                    ("102000001", "XGame.SPECIES_SniperA", "defaultset", "2"),
                    ("104000001", "XGame.SPECIES_Sem", "required_class", "1000"),
                    ("104000001", "XGame.SPECIES_Sem", "defaultset", "1"),
                ],
            )
            equip = [
                ("201030001", "XGame.LM_AssaultRifle_AA", "item_id", "201030001"),
                ("201030001", "XGame.LM_AssaultRifle_AA", "item_slot", "0"),
                ("201030001", "XGame.LM_AssaultRifle_AA", "item_required_class", "1"),
                ("201030001", "XGame.LM_AssaultAmmo", "item_name", "Munição"),
                ("201070001", "XGame.LM_BigGun_AA", "item_id", "201070001"),
                ("201070001", "XGame.LM_BigGun_AA", "item_slot", "1"),
                ("201070001", "XGame.LM_BigGun_AA", "item_required_class", "10"),
                ("201090001", "XGame.LM_Knife", "item_id", "201090001"),
                ("201090001", "XGame.LM_Knife", "item_slot", "2"),
                ("201090001", "XGame.LM_Knife", "item_required_class", "0"),
                ("203000001", "XGame.LM_PartsDataBoosterA", "item_id", "203000001"),
                ("203000001", "XGame.LM_PartsDataBoosterA", "item_slot", "6"),
                ("203000001", "XGame.LM_PartsDataBoosterA", "item_required_class", "0"),
                ("202000001", "XGame.LM_PartsDataGeneratorA", "item_id", "202000001"),
                ("202000001", "XGame.LM_PartsDataGeneratorA", "item_slot", "7"),
                ("202000001", "XGame.LM_PartsDataGeneratorA", "item_required_class", "0"),
                ("201010003", "XGame.LM_GLauncher_AC", "item_slot", "4"),
                ("201010003", "XGame.LM_GLauncher_AC", "item_required_class", "1111"),
            ]
            if extra_etc:
                equip += [
                    ("201010001", "XGame.LM_GLauncher_AA", "item_id", "201010001"),
                    ("201010001", "XGame.LM_GLauncher_AA", "item_slot", "3"),
                    ("201010001", "XGame.LM_GLauncher_AA", "item_required_class", "1"),
                    ("201010002", "XGame.LM_GLauncher_AB", "item_id", "201010002"),
                    ("201010002", "XGame.LM_GLauncher_AB", "item_slot", "3"),
                    ("201010002", "XGame.LM_GLauncher_AB", "item_required_class", "0"),
                ]
            _tabela(con, "Item_Equip", equip)
            _tabela(con, "item", [])
            _tabela(
                con,
                "DefaultSet",
                [
                    ("1", "Character", "MainWeapon", "201030001"),
                    ("1", "Character", "SubWeapon", "201070001"),
                    ("1", "Character", "EtcWeapon1", "999999999"),
                    ("1", "Character", "Booster", "203000001"),
                    ("1", "Character", "Generator", "202000001"),
                    ("2", "Character", "MainWeapon", "201030001"),
                    ("2", "Character", "SubWeapon", "201070001"),
                ],
            )
            con.commit()
        finally:
            con.close()
        return path

    return criar


def _catalogo(wdb: Callable[..., Path], **kw: bool) -> ItemCatalog:
    return ItemCatalog.open(wdb(**kw))


def _campos(linha: str) -> dict[str, str]:
    """Opções de uma linha `?nome=valor...` (com ou sem o prefixo `Bots=`)."""
    return dict(par.split("=", 1) for par in linha.split("?") if par and "=" in par)


def test_registro_pega_o_primeiro_time_0_por_especie_e_ignora_comentada() -> None:
    assert player_records(UPL) == {
        "xgame.species_assaulta": "M_Assault01_0",
        "xgame.species_snipera": "M_Sniper01_0",
    }


def test_linha_de_bot_tem_o_formato_exato(wdb: Callable[..., Path]) -> None:
    bots = BotLoadout(
        catalog=_catalogo(wdb), records=_Registros(ASSAULT_ONLY), rng=random.Random(1)
    )

    [linha] = bots.lines(1)

    nome, _, resto = linha.partition("?Skill=")
    assert nome.removeprefix("?Name=" + BOT_PREFIX) in BOT_NAMES
    assert "?Skill=" + resto == (
        "?Skill=3?Species=XGame.SPECIES_AssaultA?Morat=101000001"
        "?MainWeapon=XGame.LM_AssaultRifle_AA?MainWeaponId=201030001"
        "?SubWeapon=none?SubWeaponId=0"  # BigGun é classe 10: o Assault não a leva (D228)
        "?MeleeWeapon=XGame.LM_Knife?MeleeWeaponId=201090001"
        "?EtcWeapon1=none?EtcWeapon1Id=0?EtcWeapon2=none?EtcWeapon2Id=0"
        "?EtcWeapon3=none?EtcWeapon3Id=0"
        "?Booster=XGame.LM_PartsDataBoosterA?BoosterId=203000001"
        "?Generator=XGame.LM_PartsDataGeneratorA?GeneratorId=202000001"
        "?Record=M_Assault01_0"
    )


def test_municao_do_mesmo_id_nao_vira_peca(wdb: Callable[..., Path]) -> None:
    [linha] = BotLoadout(
        catalog=_catalogo(wdb), records=_Registros(ASSAULT_ONLY), rng=random.Random(2)
    ).lines(1)

    assert _campos(linha)["MainWeapon"] == "XGame.LM_AssaultRifle_AA"


def test_sniper_nunca_recebe_o_rifle_do_defaultset_de_classe_1(wdb: Callable[..., Path]) -> None:
    # O DefaultSet do Sniper (morat 102000001) dá o rifle de classe 1; o sorteio não o usa.
    # Arma principal: `none` (sem candidato de classe 10 no slot 0). Sub: sai de classe 10.
    catalogo = _catalogo(wdb)
    for semente in range(50):
        for linha in BotLoadout(
            catalog=catalogo, records=_Registros(SNIPER_ONLY), rng=random.Random(semente)
        ).lines(10):
            campos = _campos(linha)
            assert (campos["MainWeapon"], campos["MainWeaponId"]) == ("none", "0")
            assert (campos["SubWeapon"], campos["SubWeaponId"]) == (
                "XGame.LM_BigGun_AA",
                "201070001",
            )


def test_peca_sem_candidato_no_slot_vira_none(wdb: Callable[..., Path]) -> None:
    [linha] = BotLoadout(
        catalog=_catalogo(wdb), records=_Registros(ASSAULT_ONLY), rng=random.Random(4)
    ).lines(1)

    # Não há lança-granada de classe 1 ou 0 no fixture sem `extra_etc`: EtcWeapon1..3 ficam `none`.
    campos = _campos(linha)
    assert (campos["EtcWeapon1"], campos["EtcWeapon1Id"]) == ("none", "0")
    assert (campos["EtcWeapon2"], campos["EtcWeapon2Id"]) == ("none", "0")
    assert (campos["EtcWeapon3"], campos["EtcWeapon3Id"]) == ("none", "0")


def test_cada_peca_sai_da_classe_do_morat_e_do_slot_em_muitos_sorteios(
    wdb: Callable[..., Path],
) -> None:
    # D228: nenhum sorteio sai fora da classe do morat, por slot. Vários morats, várias sementes.
    catalogo = _catalogo(wdb, extra_etc=True)
    registros = _Registros({**ASSAULT_ONLY, **SNIPER_ONLY})
    classes = {"XGame.SPECIES_AssaultA": 1, "XGame.SPECIES_SniperA": 10}
    sorteados = 0
    for semente in range(200):
        for linha in BotLoadout(
            catalog=catalogo, records=registros, rng=random.Random(semente)
        ).lines(20):
            campos = _campos(linha)
            classe = classes[campos["Species"]]
            for opcao, slot in (
                ("MainWeapon", "main_weapon"),
                ("SubWeapon", "sub_weapon"),
                ("MeleeWeapon", "melee_weapon"),
                ("EtcWeapon1", "etc_weapon_00"),
                ("EtcWeapon2", "etc_weapon_01"),
                ("EtcWeapon3", "etc_weapon_02"),
                ("Booster", "booster"),
                ("Generator", "generator"),
            ):
                ident = int(campos[f"{opcao}Id"])
                if ident == 0:
                    assert campos[opcao] == "none"
                    continue
                spec = catalogo.equip_spec(ident)
                assert spec is not None and spec.slot == slot_of(slot), (opcao, ident)
                assert class_allows(spec.class_mask, classe), (opcao, ident, classe)
                assert campos[opcao] == catalogo.section(ident)
                sorteados += 1
    assert sorteados > 0


def test_nomes_de_bot_sao_distintos_e_cabem_no_limite_do_nome(wdb: Callable[..., Path]) -> None:
    # D231: sem repetir na partida; apelido de até 10 caracteres ASCII; com o prefixo, até 16 bytes.
    bots = BotLoadout(
        catalog=_catalogo(wdb), records=_Registros(ASSAULT_ONLY), rng=random.Random(13)
    )

    nomes = [_campos(linha)["Name"] for linha in bots.lines(30)]

    assert len(set(nomes)) == 30
    assert all(nome.startswith(BOT_PREFIX) for nome in nomes)
    assert len(set(BOT_NAMES)) == len(BOT_NAMES)
    assert all(len(apelido) <= 10 and apelido.isascii() for apelido in BOT_NAMES)
    assert all(len((BOT_PREFIX + apelido).encode("cp1252")) <= 16 for apelido in BOT_NAMES)


def test_item_sem_linha_item_id_nao_e_sorteado(wdb: Callable[..., Path]) -> None:
    # 201010003 tem item_slot 4 e classe 1111, mas nenhuma linha item_id: não tem classe.
    linhas = BotLoadout(
        catalog=_catalogo(wdb), records=_Registros(ASSAULT_ONLY), rng=random.Random(5)
    ).lines(30)

    assert all("GLauncher_AC" not in linha and "201010003" not in linha for linha in linhas)


def test_sem_registro_o_morat_nao_sorteia(wdb: Callable[..., Path]) -> None:
    linhas = BotLoadout(
        catalog=_catalogo(wdb), records=_Registros(ASSAULT_ONLY), rng=random.Random(6)
    ).lines(30)

    assert {_campos(linha)["Species"] for linha in linhas} == {"XGame.SPECIES_AssaultA"}
    assert all("SPECIES_Sem" not in linha for linha in linhas)


def test_sem_nenhum_morat_sorteavel_levanta_valueerror(wdb: Callable[..., Path]) -> None:
    bots = BotLoadout(catalog=_catalogo(wdb), records=_Registros({}), rng=random.Random(7))

    with pytest.raises(ValueError, match="nenhum morat"):
        bots.lines(1)


def test_mesma_semente_da_as_mesmas_linhas_e_sorteia_entre_candidatos(
    wdb: Callable[..., Path],
) -> None:
    catalogo = _catalogo(wdb, extra_etc=True)
    registros = _Registros({**ASSAULT_ONLY, **SNIPER_ONLY})

    primeiro = BotLoadout(catalog=catalogo, records=registros, rng=random.Random(11)).lines(40)
    segundo = BotLoadout(catalog=catalogo, records=registros, rng=random.Random(11)).lines(40)

    assert primeiro == segundo
    campos = [_campos(linha) for linha in primeiro]
    assert {c["Species"] for c in campos} == {"XGame.SPECIES_AssaultA", "XGame.SPECIES_SniperA"}
    # Assault aceita os dois lança-granadas (classe 1 e sem classe): o sorteio cai nos dois.
    assault = [c["EtcWeapon1Id"] for c in campos if c["Species"] == "XGame.SPECIES_AssaultA"]
    assert set(assault) == {"201010001", "201010002"}


def test_cada_id_sorteado_existe_no_catalogo_com_a_classe_da_linha(
    wdb: Callable[..., Path],
) -> None:
    catalogo = _catalogo(wdb, extra_etc=True)
    linhas = BotLoadout(
        catalog=catalogo, records=_Registros({**ASSAULT_ONLY, **SNIPER_ONLY}), rng=random.Random(8)
    ).lines(20)

    for linha in linhas:
        campos = _campos(linha)
        for peca in (
            "MainWeapon",
            "SubWeapon",
            "MeleeWeapon",
            "EtcWeapon1",
            "Booster",
            "Generator",
        ):
            ident = int(campos[f"{peca}Id"])
            classe = catalogo.section(ident) or "none"
            assert campos[peca] == classe, (peca, ident)


def test_linha_do_bot_vem_com_prefixo_bots_e_owner_so_com_apelido(
    wdb: Callable[..., Path],
) -> None:
    catalogo = _catalogo(wdb)
    # Inventário e contas não entram nos bots; o serviço recebe None.
    servico = LoadoutService(
        catalog=catalogo,
        inventory=None,
        accounts=None,
        bots=BotLoadout(catalog=catalogo, records=_Registros(ASSAULT_ONLY), rng=random.Random(9)),
    )

    [(chave, valor)] = servico.bot_lines(1)
    assert chave == "Bots"
    assert valor.startswith("?Name=" + BOT_PREFIX)
    assert "?Skill=3?Species=XGame.SPECIES_AssaultA?Morat=101000001" in valor
    assert servico.bot_lines(0) == ()
    assert owner_entries("Ana") == (("Owner", "0041006E0061"),)
    assert owner_entries(None) == ()
    assert owner_entries("") == ()


def test_arquivo_de_bots_grava_bots_e_owner_sem_perder_outras_secoes(tmp_path: Path) -> None:
    (tmp_path / "LMEmu.ini").write_bytes(b"[LMEmu.Outra]\r\nChave=1\r\n")

    LoadoutFile(tmp_path / "LMEmu.ini").write(
        "m00000001",
        [
            "0041006E0061|?Team=0?morats=101000001",
            ("Bots", "?Name=[BOT] Maverick?Skill=3?Species=XGame.SPECIES_AssaultA"),
            *owner_entries("Ana"),
        ],
    )

    assert (tmp_path / "LMEmu.ini").read_bytes() == (
        b"[LMEmu.Outra]\r\nChave=1\r\n"
        b"[m00000001 LMEmuLoadout]\r\n"
        b"Players=0041006E0061|?Team=0?morats=101000001\r\n"
        b"Bots=?Name=[BOT] Maverick?Skill=3?Species=XGame.SPECIES_AssaultA\r\n"
        b"Owner=0041006E0061\r\n"
    )


def test_registro_le_o_upl_na_primeira_consulta_e_tenta_de_novo_se_falhar(tmp_path: Path) -> None:
    arquivo = PlayerRecordFile(tmp_path / "MORATS.upl")

    with pytest.raises(ValueError, match="não lido"):
        arquivo.records()

    (tmp_path / "MORATS.upl").write_text(UPL, encoding="cp1252")

    assert arquivo.records()["xgame.species_assaulta"] == "M_Assault01_0"


@pytest.mark.skipif(
    not (WDB_REAL.is_file() and UPL_REAL.is_file()),
    reason="landmass.wdb ou MORATS.upl ausente em D:\\landmass (cliente e servidor de partida)",
)
def test_wdb_real_classes_das_pecas_e_nove_morats_com_registro() -> None:
    catalogo = ItemCatalog.open(WDB_REAL)

    assert catalogo.section(201030001) == "XGame.LM_AssaultRifle_AA"  # não a munição
    assert catalogo.section(203000001) == "XGame.LM_PartsDataBoosterA"
    assert catalogo.section(202000001) == "XGame.LM_PartsDataGeneratorA"
    assert catalogo.section(101000001) == "XGame.SPECIES_AssaultA"
    assert catalogo.section(201010003) is None  # sem linha item_id

    registros = player_records(UPL_REAL.read_text(encoding="cp1252", errors="replace"))
    com_registro = [
        m for m in catalogo.morat_ids() if (catalogo.section(m) or "").lower() in registros
    ]
    assert len(com_registro) == 9

    for semente in range(30):
        bots = BotLoadout(
            catalog=catalogo, records=PlayerRecordFile(UPL_REAL), rng=random.Random(semente)
        )
        for linha in bots.lines(20):
            campos = _campos(linha)
            # Valor sem espaço, `?`, `|` nem `=`: o formato do LMEmu.ini não comporta. O apelido
            # tem espaço (prefixo `[BOT] `), então é conferido à parte.
            sem_nome = [valor for chave, valor in campos.items() if chave != "Name"]
            assert all(not set(valor) & set(" ?|=") for valor in sem_nome)
            assert campos["Name"].startswith(BOT_PREFIX)
            assert int(campos["Morat"]) in com_registro
            assert campos["Record"] == registros[campos["Species"].lower()]
            stats = catalogo.morat_stats(int(campos["Morat"]))
            assert stats is not None
            classe = stats.morat_class
            for peca, slot in (
                ("MainWeapon", "main_weapon"),
                ("SubWeapon", "sub_weapon"),
                ("MeleeWeapon", "melee_weapon"),
                ("EtcWeapon1", "etc_weapon_00"),
                ("EtcWeapon2", "etc_weapon_01"),
                ("EtcWeapon3", "etc_weapon_02"),
                ("Booster", "booster"),
                ("Generator", "generator"),
            ):
                ident = int(campos[f"{peca}Id"])
                assert campos[peca] == (catalogo.section(ident) or "none"), (peca, ident)
                if ident:
                    spec = catalogo.equip_spec(ident)
                    assert spec is not None and spec.slot == slot_of(slot), (peca, ident)
                    assert class_allows(spec.class_mask, classe), (peca, ident, classe)
