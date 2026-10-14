"""Equipamento de cada jogador da partida para o pacote LMEmu (D190).

Cada jogador vira uma linha `Players=<HEX>|?opção=valor...` da seção do `LMEmu.ini` (escrita em
`hosting/loadout.py`). `<HEX>` é o apelido com 4 dígitos hexadecimais por caractere, como
`LMEmuLoadout.HexOf`, e as opções são as que `LMEmuLoadout.Inject` põe antes das do cliente. Todo
valor é id de catálogo. Peça e pintura vêm do morat (montadas, senão o `DefaultSet` do wdb); slot
vazio sem padrão vale 0.
"""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from landmass_emu.domain.equipment import SYSTEM_SLOT_COUNT
from landmass_emu.domain.inventory import ItemUnit, MoratUnit
from landmass_emu.domain.match import GAME_DEATHMATCH, TEAM_COUNT_FOR_TEAM_GAME
from landmass_emu.ports.accounts import AccountRepository
from landmass_emu.ports.inventory import InventoryRepository

log = logging.getLogger(__name__)

# (slot de `SLOT_NAMES`, opção do LMEmu, chave da peça no `DefaultSet`). Etc item fica de fora.
PIECES: tuple[tuple[str, str, str], ...] = (
    ("main_weapon", "weapon_main", "MainWeapon"),
    ("sub_weapon", "weapon_sub", "SubWeapon"),
    ("melee_weapon", "weapon_melee", "MeleeWeapon"),
    ("etc_weapon_00", "weapon_etc0", "EtcWeapon1"),
    ("etc_weapon_01", "weapon_etc1", "EtcWeapon2"),
    ("etc_weapon_02", "weapon_etc2", "EtcWeapon3"),
    ("booster", "booster", "Booster"),
    ("generator", "generator", "Generator"),
    ("head", "head", "Head"),
    ("body", "body", "Body"),
    ("arm", "arm", "Arm"),
    ("leg", "leg", "Leg"),
)
# (slot de `SKIN_SLOTS`, opção do LMEmu, chave da pintura no `DefaultSet`).
SKINS: tuple[tuple[str, str, str], ...] = (
    ("skin_00", "skin0", "Skin1"),
    ("skin_01", "skin1", "Skin2"),
    ("skin_02", "skin2", "Skin3"),
)


@dataclass(frozen=True, slots=True)
class LoadoutMember:
    """Jogador na partida: conta, apelido, grupo (slot) e o gate do morat escolhido (401)."""

    account_id: int
    nickname: str
    slot: int
    gate: int
    # Espectador (slot >= 60) não tem morat: a linha só leva `?SpectatorOnly=1` (D197).
    spectator: bool = False


class LoadoutCatalog(Protocol):
    def default_set(self, morat_id: int) -> dict[str, int]: ...


def nickname_hex(nickname: str) -> str:
    """Chave do jogador no LMEmu: 4 dígitos hexadecimais por caractere (`LMEmuLoadout.HexOf`)."""
    return "".join(f"{ord(c):04X}" for c in nickname)


def nickname_option(nickname: str) -> str:
    """Apelido para `?nickname=`. O cp1252 do `LMEmu.ini` troca o que não cabe por `?`, que é o
    separador de opções, então ele sai antes de virar `?`."""
    return nickname.encode("cp1252", errors="replace").decode("cp1252").replace("?", "")


def player_line(nickname: str, opcoes: Sequence[tuple[str, int | str]]) -> str:
    """Valor de `Players=`: `<HEX>|?nome=valor...`."""
    return nickname_hex(nickname) + "|" + "".join(f"?{nome}={valor}" for nome, valor in opcoes)


def team_options(game_class: str, slot: int, team_count: int) -> list[tuple[str, int | str]]:
    """Grupo do jogador: `slot % team_count`, como `ChangeTeam` (re/rooms.md §4). Só em modo de
    time; em DM não há grupo. OP e Bombing Run usam pelo menos dois times no servidor nativo
    (`CServerRoom::Init`, `re/LM_Engine.dll/all/100163d0_Init.c`, linhas 325 a 361), então o
    mínimo é 2 também aqui (D192)."""
    if game_class == GAME_DEATHMATCH:
        return []
    return [("Team", slot % max(team_count, TEAM_COUNT_FOR_TEAM_GAME))]


def morat_options(
    morat: MoratUnit, items: Sequence[ItemUnit], defaults: Mapping[str, int]
) -> list[tuple[str, int | str]]:
    """Peças e pinturas do morat: a montada nele, senão a do `DefaultSet` da espécie, senão 0."""
    montados = {
        item.slot_name: item.catalog_id
        for item in items
        if item.account_morat_id == morat.id and item.slot_name is not None
    }
    return [
        (opcao, montados.get(slot, defaults.get(padrao, 0)))
        for slot, opcao, padrao in (*PIECES, *SKINS)
    ]


def event_options(items: Sequence[ItemUnit]) -> list[tuple[str, int | str]]:
    """`eventslot0..9`: o item de sistema montado em cada slot (`system_slot`), senão 0."""
    por_slot = {item.system_slot: item.catalog_id for item in items if item.system_slot is not None}
    return [(f"eventslot{n}", por_slot.get(n, 0)) for n in range(SYSTEM_SLOT_COUNT)]


class LoadoutService:
    """Monta o `Players=` de cada jogador da sala com o inventário, o nest da conta e o `DefaultSet`
    do catálogo. Jogador sem morat no gate escolhido fica sem linha (aviso no log): o motor usa o
    padrão do cliente para ele."""

    def __init__(
        self,
        *,
        catalog: LoadoutCatalog,
        inventory: InventoryRepository,
        accounts: AccountRepository,
    ) -> None:
        self._catalog = catalog
        self._inventory = inventory
        self._accounts = accounts

    async def lines(
        self, members: Sequence[LoadoutMember], game_class: str, team_count: int
    ) -> tuple[str, ...]:
        """Erro do catálogo (`ValueError`) sobe para quem chama, que decide o que fazer."""
        linhas: list[str] = []
        for membro in members:
            opcoes = await self._options(membro, game_class, team_count)
            if opcoes is not None:
                linhas.append(player_line(membro.nickname, opcoes))
        return tuple(linhas)

    async def _options(
        self, membro: LoadoutMember, game_class: str, team_count: int
    ) -> list[tuple[str, int | str]] | None:
        if membro.spectator:
            return [("SpectatorOnly", 1)]
        morats = await self._inventory.morats(membro.account_id)
        morat = next((m for m in morats if m.gate_index == membro.gate and m.id is not None), None)
        if morat is None:
            log.warning(
                "conta %d sem morat no gate %d: sem equipamento no LMEmu.ini",
                membro.account_id,
                membro.gate,
            )
            return None
        items = await self._inventory.items(membro.account_id)
        nest = await self._accounts.regular_nest(membro.account_id)
        return [
            *team_options(game_class, membro.slot, team_count),
            ("morats", morat.catalog_id),
            *morat_options(morat, items, self._catalog.default_set(morat.catalog_id)),
            *event_options(items),
            ("nickname", nickname_option(membro.nickname)),
            ("gender", 0),
            ("nest", nest),
            ("pc_room", 0),
            ("clan", 0),
            ("costume", 0),
        ]
