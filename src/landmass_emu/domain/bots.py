"""Bots da partida (D220, D221, D228, D231): apelido, morat e peças sorteados por bot, em linhas
`Bots=` do LMEmu.ini. Só regras: o catálogo e os registros de jogador entram por porta, e o `Random`
é injetado (teste com semente). O arquivo é lido em `hosting/player_records.py`.

Valor de cada linha (o host põe `Bots=` na frente):
`?Name=[BOT] <apelido>?Skill=3?Species=<Morats.section>?Morat=<id>?MainWeapon=<classe>`
`?MainWeaponId=<id>...?Record=<registro>`. Peça sem candidato da classe e do slot: `none` e id `0`.
"""

import random
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from landmass_emu.domain.equipment import EquipSpec, MoratStats, class_allows, slot_of

# (opção do LMEmu, nome do slot em `SLOT_NAMES`), na ordem da linha. Cabeça, corpo, braço e perna
# não entram nesta fase; a pintura também não.
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
# Prefixo do apelido de bot (D231). Conta de jogador não pode começar com ele (`account create`).
BOT_PREFIX = "[BOT] "
# Apelidos de bot (D231): palavras de jogo, curtas e ASCII, sem nome de pessoa. Com o prefixo, o
# nome cabe em 16 bytes (10 caracteres de apelido). Cada partida sorteia sem repetir.
_APELIDOS = (
    "Ace Alpha Apex Arrow Atlas Avalanche Axe Azure Badger Bandit Baron Blaze Blitz Bolt "
    "Brawler Breaker Bulldog Cannon Cobra Comet Condor Cosmic Coyote Crater Crimson Cyclone "
    "Dagger Daemon Dasher Delta Demon Dingo Drifter Dynamo Eagle Echo Ember Enigma Falcon Fang "
    "Flare Fury Gecko Ghost Glacier Golem Griffin Hammer Harbor Havoc Hawk Hornet Hunter Ignite "
    "Impact Iron Jackal Jaguar Jet Jolt Kraken Lancer Laser Lynx Mammoth Maverick Meteor "
    "Midnight Mirage Mongoose Monsoon Nebula Nitro Nomad Oblivion Onyx Orbit Otter Outlaw "
    "Panther Phantom Pilot Pixel Pirate Pulsar Quake Raptor Razor Rebel Reaper Rhino Ripple "
    "Rocket Rogue Saber Sentry Shadow Shark Sierra Slasher Smoke Spartan Spectre Spike Storm "
    "Striker Sulfur Sunset Talon Thunder Titan Tornado Tracer Turbo Typhoon Ulti Valkyrie Vapor "
    "Venom Vortex Warden Wasp Wraith Yeti Zenith Zephyr Zigzag Zombie"
)
BOT_NAMES: tuple[str, ...] = tuple(_APELIDOS.split())
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
    """Sorteia apelido, morat e equipamento de cada bot. Morat só entra se a espécie tem registro.
    Cada peça sai de um candidato da classe do morat e do slot da peça (D228); sem candidato, `none`
    com id `0`. O `DefaultSet` do morat não entra: ele pode trazer peça fora da classe."""

    def __init__(self, *, catalog: BotCatalog, records: RecordSource, rng: random.Random) -> None:
        self._catalog = catalog
        self._records = records
        self._rng = rng

    def lines(self, count: int) -> tuple[str, ...]:
        """Valores de `Bots=`, um por bot, com apelidos distintos da lista (D231). Sem morat
        sorteável ou `count` maior que a lista, levanta ValueError: a partida sobe sem bots."""
        pool = self._pool()
        if not pool:
            raise ValueError("nenhum morat com registro de jogador (MORATS.upl)")
        if count > len(BOT_NAMES):
            raise ValueError(f"{count} bots pedidos, a lista tem {len(BOT_NAMES)} apelidos")
        return tuple(self._linha(apelido, pool) for apelido in self._rng.sample(BOT_NAMES, count))

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

    def _linha(self, apelido: str, pool: list[_Morat]) -> str:
        morat = self._rng.choice(pool)
        campos = [
            f"Name={BOT_PREFIX}{apelido}",
            f"Skill={BOT_SKILL}",
            f"Species={morat.species}",
            f"Morat={morat.catalog_id}",
        ]
        for opcao, slot in BOT_PIECES:
            peca = self._peca(slot_of(slot), morat.stats.morat_class)
            campos += [f"{opcao}={self._classe(peca)}", f"{opcao}Id={peca}"]
        campos.append(f"Record={morat.record}")
        return "?" + "?".join(campos)

    def _peca(self, slot: int | None, classe: int) -> int:
        # `equip_ids` vem em ordem, então o sorteio é o mesmo para a mesma semente.
        candidatos = [cid for cid in self._catalog.equip_ids() if self._serve(cid, slot, classe)]
        return self._rng.choice(candidatos) if candidatos else 0

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
        if peca == 0:
            return NONE
        return self._catalog.section(peca) or NONE
