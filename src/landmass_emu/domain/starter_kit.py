"""Kit inicial da conta: morats com as peças padrão do cliente. Regra pura, sem IO.

Vem do servidor antigo: `usp_insert_morats_temp` (LM_account.sql, L5408) dá 4 morats, classes 0..3,
com as peças em -1. Os ids vêm de `DefaultSet` do wdb (sets 1..4 com `Morats` 101000001,
102000001, 103000001 e 104000001). O kit não dá itens: o servidor antigo não dava, e o
`InitializeQuickSlot` (quickslot) ainda não tem tabela no emulador.
"""

from collections.abc import Collection, Sequence

from landmass_emu.domain.inventory import InventoryService, MoratUnit

# shortcut: a classe de cada morat do kit segue a ordem do DefaultSet (sets 1..4); o servidor
# antigo guardava só `class` 0..3. Revisar quando o cliente real pedir outra classe por gate.
STARTER_MORATS: tuple[int, ...] = (101000001, 102000001, 103000001, 104000001)


class StarterKit:
    """Planeja os morats do kit nos gates livres, na ordem de `morats` (gate = posição)."""

    def __init__(self, service: InventoryService, morats: Sequence[int] = STARTER_MORATS) -> None:
        # Falha aqui, antes de gravar conta: wdb de outra versão sem esses morats.
        missing = [catalog_id for catalog_id in morats if not service.is_morat(catalog_id)]
        if missing:
            raise ValueError(f"kit sem morat no catálogo do cliente: {missing}")
        self._service = service
        self._morats = morats

    def plan(self, account_id: int, used_gates: Collection[int]) -> list[MoratUnit]:
        return [
            self._service.new_morat(account_id, catalog_id, gate, used_gates)
            for gate, catalog_id in enumerate(self._morats)
            if gate not in used_gates
        ]
