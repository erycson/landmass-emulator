"""Bots da partida (D220, D221): morat e equipamento sorteados por bot, em linhas `Bots=` do
LMEmu.ini. Só regras: o catálogo e os registros de jogador entram por porta, e o `Random` é
injetado (teste com semente). O arquivo é lido em `hosting/player_records.py`.

Valor de cada linha (o host põe `Bots=` na frente):
`?Name=Bot<k>?Skill=3?Species=<Morats.section>?Morat=<id>?MainWeapon=<classe>?MainWeaponId=<id>...
?Record=<registro>`. Peça sem item: `none` e id `0`.
"""

import random
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from landmass_emu.domain.equipment import EquipSpec, MoratStats, class_allows, slot_of

# (opção do LMEmu, nome do slot em `SLOT_NAMES`), na ordem da linha. Cabeça, corpo, braço e perna
# não entram nesta fase; o `DefaultSet` do morat não é usado para eles.
BOT_PIECES: tuple[tuple[str, str], ...] = (
    ("MainWeapon", "main_weapon"),
    ("SubWeapon", "sub_weapon"),
    ("MeleeWeapon", "melee_weapon"),
    ("EtcWeapon1", "etc_weapon_00"),
    ("EtcWeapon2", "etc_weapon_01"),
    ("EtcWeapon3", "etc_weapon_02"),
    ("Booster", "booster"),
    ("Generator", "generator"),
)
BOT_SKILL = 3
NONE = "none"
# Linha `Player=(DefaultName="...", ... species=...` do MORATS.upl. `;Player=` (comentada) não casa.
PLAYER_RECORD = re.compile(r'^Player=\(DefaultName="([^"]+)".*?\bspecies=([^,\s]+)')
TIME_ZERO_SUFFIX = "_0"


def player_records(texto: str) -> dict[str, str]:
    """Registro de jogador de cada espécie, com a chave em minúsculas (o wdb e o arquivo diferem no
    `X`/`x`). Vale o primeiro `_0` do arquivo, que é o time 0 e vem antes do `F_` (D221)."""
    registros: dict[str, str] = {}
    for linha in texto.splitlines():
        casa = PLAYER_RECORD.match(linha)
        if casa is not None and casa.group(1).endswith(TIME_ZERO_SUFFIX):
            registros.setdefault(casa.group(2).lower(), casa.group(1))
    return registros


class BotCatalog(Protocol):
    def morat_ids(self) -> tuple[int, ...]: ...

    def section(self, catalog_id: int) -> str | None: ...

    def morat_stats(self, catalog_id: int) -> MoratStats | None: ...

    def equip_ids(self) -> tuple[int, ...]: ...

    def equip_spec(self, catalog_id: int) -> EquipSpec | None: ...

    def default_set(self, morat_id: int) -> dict[str, int]: ...


class RecordSource(Protocol):
    def records(self) -> Mapping[str, str]:
        """Registro de jogador por espécie (chave em minúsculas). Levanta ValueError se não lê."""
        ...


@dataclass(frozen=True, slots=True)
class _Morat:
    """Morat que pode sortear: espécie com registro de jogador e atributos no wdb."""

    catalog_id: int
    species: str  # Morats.section, como o wdb grava (ex.: XGame.SPECIES_AssaultA)
    record: str  # DefaultName do registro de time 0 (ex.: M_Assault01_0)
    stats: MoratStats


class BotLoadout:
    """Sorteia morat e equipamento de cada bot. Morat só entra se a espécie tem registro. Peça sem
    candidato válido (classe e slot) vem do `DefaultSet` do morat, se o id existe no catálogo;
    senão `none:0`."""

    def __init__(self, *, catalog: BotCatalog, records: RecordSource, rng: random.Random) -> None:
        self._catalog = catalog
        self._records = records
        self._rng = rng

    def lines(self, count: int) -> tuple[str, ...]:
        """Valores de `Bots=`, um por bot (k de 1 a `count`). Sem morat sorteável, levanta
        ValueError: a partida sobe sem bots."""
        pool = self._pool()
        if not pool:
            raise ValueError("nenhum morat com registro de jogador (MORATS.upl)")
        return tuple(self._linha(k, pool) for k in range(1, count + 1))

    def _pool(self) -> list[_Morat]:
        registros = self._records.records()
        pool: list[_Morat] = []
        for morat_id in self._catalog.morat_ids():
            especie = self._catalog.section(morat_id)
            stats = self._catalog.morat_stats(morat_id)
            if especie is None or stats is None:
                continue
            registro = registros.get(especie.lower())
            if registro is not None:
                pool.append(_Morat(morat_id, especie, registro, stats))
        return pool

    def _linha(self, k: int, pool: list[_Morat]) -> str:
        morat = self._rng.choice(pool)
        padroes = self._catalog.default_set(morat.catalog_id)
        campos = [
            f"Name=Bot{k}",
            f"Skill={BOT_SKILL}",
            f"Species={morat.species}",
            f"Morat={morat.catalog_id}",
        ]
        for opcao, slot in BOT_PIECES:
            peca = self._peca(slot_of(slot), morat.stats.morat_class, padroes.get(opcao, 0))
            campos += [f"{opcao}={self._classe(peca)}", f"{opcao}Id={peca}"]
        campos.append(f"Record={morat.record}")
        return "?" + "?".join(campos)

    def _peca(self, slot: int | None, classe: int, padrao: int) -> int:
        # `equip_ids` vem em ordem, então o sorteio é o mesmo para a mesma semente.
        candidatos = [cid for cid in self._catalog.equip_ids() if self._serve(cid, slot, classe)]
        if candidatos:
            return self._rng.choice(candidatos)
        return padrao if padrao and self._catalog.section(padrao) is not None else 0

    def _serve(self, catalog_id: int, slot: int | None, classe: int) -> bool:
        spec = self._catalog.equip_spec(catalog_id)
        return (
            spec is not None
            and spec.slot == slot
            and class_allows(spec.class_mask, classe)
            and self._catalog.section(catalog_id) is not None
        )

    def _classe(self, peca: int) -> str:
        # Id 0 não tem seção: vira `none`. Id com seção é a classe da peça.
        return self._catalog.section(peca) or NONE
