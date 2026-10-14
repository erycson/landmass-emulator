"""Operações da CLI sobre a loja (D191): importar do cliente, listar, habilitar, desativar e mudar
preço por nível (0 a 3). A CLI grava em `shop_items`; o canal lê a tabela a cada compra, então a
mudança vale na próxima compra, sem reiniciar o servidor.
"""

from landmass_emu.db.item_catalog import ItemCatalog
from landmass_emu.domain.shop import is_sellable, shop_prices
from landmass_emu.ports.shop import ShopItem, ShopItemRepository

TIERS = (0, 1, 2, 3)


class ShopAdmin:
    def __init__(self, items: ShopItemRepository) -> None:
        self._items = items

    async def sync(self, catalog: ItemCatalog) -> str:
        """Importa do wdb toda venda que `quote` aceitaria. Nome e preço são sobrescritos, então um
        preço ajustado com `price` volta ao do wdb; `enabled` de quem já existe não muda."""
        vendas: list[ShopItem] = []
        for catalog_id in catalog.sale_ids():
            sale = catalog.sale(catalog_id)
            if sale is None or not is_sellable(sale):
                continue
            ld, cash = shop_prices(sale)
            name = catalog.name(catalog_id) or str(catalog_id)
            vendas.append(ShopItem(catalog_id, name, True, ld, cash))
        novas, atualizadas = await self._items.sync(vendas)
        return f"loja: {len(vendas)} vendas do cliente ({novas} novas, {atualizadas} atualizadas)"

    async def list_items(self, *, disabled_only: bool) -> str:
        itens = await self._items.all_items()
        if not itens:
            return "loja vazia: rode 'landmass-emu shop sync' com o cliente instalado"
        if disabled_only:
            itens = tuple(item for item in itens if not item.enabled)
            if not itens:
                return "nenhum item desativado"
        linhas = [
            f"{'ID':<11}{'Nome':<20}{'LD (níveis 0 a 3)':<28}{'Cash (níveis 0 a 3)':<28}Status"
        ]
        for item in itens:
            status = "habilitado" if item.enabled else "desativado"
            linhas.append(
                f"{item.catalog_id:<11}{item.name:<20}{_niveis(item.ld):<28}"
                f"{_niveis(item.cash):<28}{status}"
            )
        return "\n".join(linhas)

    async def enable(self, catalog_id: int) -> str:
        return await self._toggle(catalog_id, enabled=True)

    async def disable(self, catalog_id: int) -> str:
        return await self._toggle(catalog_id, enabled=False)

    async def _toggle(self, catalog_id: int, *, enabled: bool) -> str:
        if not await self._items.set_enabled(catalog_id, enabled):
            raise ValueError(f"item {catalog_id} não está na loja; rode 'landmass-emu shop sync'")
        return f"item {catalog_id} {'habilitado' if enabled else 'desativado'} na loja"

    async def price(self, catalog_id: int, tier: int, *, ld: int | None, cash: int | None) -> str:
        """Muda o preço de um nível. Preço 0 na moeda = não vendido nela. Morat: só o nível 0 conta
        e o LD é o valor cobrado (já com o fator de 5 do D191)."""
        if tier not in TIERS:
            raise ValueError("nível deve ser de 0 a 3")
        if ld is None and cash is None:
            raise ValueError("informe --point, --cash ou os dois")
        if (ld is not None and ld < 0) or (cash is not None and cash < 0):
            raise ValueError("preço não pode ser negativo")
        item = await self._items.get(catalog_id)
        if item is None:
            raise ValueError(f"item {catalog_id} não está na loja; rode 'landmass-emu shop sync'")
        novo_ld = item.ld if ld is None else _set_tier(item.ld, tier, ld)
        novo_cash = item.cash if cash is None else _set_tier(item.cash, tier, cash)
        await self._items.set_prices(catalog_id, novo_ld, novo_cash)
        return f"item {catalog_id}, nível {tier}: LD {novo_ld[tier]}, Cash {novo_cash[tier]}"


def _set_tier(
    prices: tuple[int, int, int, int], tier: int, value: int
) -> tuple[int, int, int, int]:
    valores = list(prices)
    valores[tier] = value
    return valores[0], valores[1], valores[2], valores[3]


def _niveis(prices: tuple[int, int, int, int]) -> str:
    return "/".join(str(preco) for preco in prices)
