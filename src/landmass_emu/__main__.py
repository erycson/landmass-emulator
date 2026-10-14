import argparse
import asyncio
import contextlib
import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu import sniffer
from landmass_emu.admin import AccountAdmin, ProgressionAdmin
from landmass_emu.admin_clan import ClanAdmin
from landmass_emu.admin_inventory import InventoryAdmin, StarterKitAdmin
from landmass_emu.admin_shop import ShopAdmin
from landmass_emu.app import game_servers, open_accounts, open_database
from landmass_emu.db.accounts import SqlAccountRepository
from landmass_emu.db.catalog import WdbCatalog
from landmass_emu.db.clans import SqlClanRepository
from landmass_emu.db.inventory import SqlInventoryRepository
from landmass_emu.db.item_catalog import ItemCatalog
from landmass_emu.db.progression import SqlProgressionRepository
from landmass_emu.db.quick_slots import SqlQuickSlotRepository
from landmass_emu.db.shop import SqlShopItemRepository
from landmass_emu.domain.clan import ClanRules
from landmass_emu.domain.inventory import InventoryService
from landmass_emu.domain.progression import Grant, ProgressionService
from landmass_emu.domain.starter_kit import StarterKit
from landmass_emu.ports.accounts import AccountConflict
from landmass_emu.ports.clans import ClanConflict
from landmass_emu.ports.inventory import InventoryConflict
from landmass_emu.settings import Settings, load_settings


class Cli:
    """Comandos `serve` e `account`. As settings entram no `__init__`."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def serve(self) -> None:
        async with game_servers(self._settings) as (message, channel):
            await asyncio.gather(message.serve_forever(), channel.serve_forever())

    async def account(self, args: argparse.Namespace) -> str:
        """Ações de conta; devolve o texto a imprimir."""
        if args.action == "grant":
            return await self.grant(args)
        if args.action == "item":
            return await self.item_add(args)
        if args.action == "morat":
            return await self.morat_add(args)
        if args.action == "kit":
            return await self.kit_apply(args)
        if args.action == "create":
            return await self.create(args)
        if args.action == "ban":
            async with open_accounts(self._settings) as accounts:
                return await AccountAdmin(accounts, self._settings).ban(args.user, args.days)
        if args.action == "unban":
            async with open_accounts(self._settings) as accounts:
                return await AccountAdmin(accounts, self._settings).unban(args.user)
        client_dir: Path = args.client_dir or self._settings.client_dir
        async with open_accounts(self._settings) as accounts:
            admin = AccountAdmin(accounts, self._settings)
            return str(await admin.rotate_token(args.user, client_dir))

    async def grant(self, args: argparse.Namespace) -> str:
        # Valida antes de abrir o banco: valor negativo ou grant zerado não grava nada.
        grant = Grant(exp=args.exp, ld=args.ld, cash=args.cash)
        async with open_database(self._settings) as db:
            admin = ProgressionAdmin(
                SqlAccountRepository(db),
                SqlProgressionRepository(db),
                ProgressionService(),
                WdbCatalog(self._settings.client_dir / "landmass.wdb"),
            )
            return await admin.grant(args.user, grant)

    async def clan(self, args: argparse.Namespace) -> str:
        async with open_database(self._settings) as db:
            admin = ClanAdmin(SqlAccountRepository(db), SqlClanRepository(db), ClanRules())
            if args.action == "create":
                return await admin.create(args.name, args.master, args.mark)
            if args.action == "join":
                return await admin.join(args.username, args.clan, args.grade)
            if args.action == "leave":
                return await admin.leave(args.username)
            if args.action == "rename":
                return await admin.rename(args.clan, args.to)
            if args.action == "mark":
                return await admin.mark(args.clan, args.mark)
            return await admin.show(args.clan)

    async def shop(self, args: argparse.Namespace) -> str:
        if args.action == "sync":
            # O wdb abre antes do banco: sem o cliente, `shop sync` não migra nem grava nada.
            catalog = ItemCatalog.open(self._settings.client_dir / "landmass.wdb")
            async with open_database(self._settings) as db:
                return await ShopAdmin(SqlShopItemRepository(db)).sync(catalog)
        async with open_database(self._settings) as db:
            admin = ShopAdmin(SqlShopItemRepository(db))
            if args.action == "list":
                return await admin.list_items(disabled_only=args.disabled)
            if args.action == "enable":
                return await admin.enable(args.catalog)
            if args.action == "disable":
                return await admin.disable(args.catalog)
            return await admin.price(args.catalog, args.tier, ld=args.point, cash=args.cash)

    def _inventory_service(self) -> InventoryService:
        return InventoryService(ItemCatalog.open(self._settings.client_dir / "landmass.wdb"))

    async def create(self, args: argparse.Namespace) -> str:
        client_dir: Path = args.client_dir or self._settings.client_dir
        # Catálogo e kit são validados antes de gravar a conta: wdb ou kit inválido não deixa
        # conta pela metade.
        kit = StarterKit(self._inventory_service())
        async with open_database(self._settings) as db:
            admin = AccountAdmin(SqlAccountRepository(db), self._settings)
            bat = await admin.create(args.user, args.nickname, client_dir)
            await self._kit_admin(db, kit).apply(args.user)
        return str(bat)

    async def item_add(self, args: argparse.Namespace) -> str:
        async with open_database(self._settings) as db:
            admin = InventoryAdmin(
                SqlAccountRepository(db), SqlInventoryRepository(db), self._inventory_service()
            )
            unit = await admin.add_item(args.username, args.catalog, args.days)
        return f"item {unit.catalog_id} (índice {unit.inventory_index}) para {args.username}"

    async def morat_add(self, args: argparse.Namespace) -> str:
        async with open_database(self._settings) as db:
            admin = InventoryAdmin(
                SqlAccountRepository(db), SqlInventoryRepository(db), self._inventory_service()
            )
            unit = await admin.add_morat(args.username, args.catalog, args.gate)
        return f"morat {unit.catalog_id} no gate {unit.gate_index} para {args.username}"

    async def kit_apply(self, args: argparse.Namespace) -> str:
        kit = StarterKit(self._inventory_service())
        async with open_database(self._settings) as db:
            created = await self._kit_admin(db, kit).apply(args.username)
        return f"kit aplicado a {args.username}: {created} morat(s) novo(s)"

    @staticmethod
    def _kit_admin(db: async_sessionmaker[AsyncSession], kit: StarterKit) -> StarterKitAdmin:
        return StarterKitAdmin(
            SqlAccountRepository(db),
            SqlInventoryRepository(db),
            kit,
            SqlQuickSlotRepository(db),
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="landmass-emu")
    parser.add_argument("--config", type=Path, help="arquivo TOML (ou LANDMASS_CONFIG)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sniff = sub.add_parser("sniff", help="grava os bytes enviados pelo cliente, sem responder")
    sniff.add_argument("--out", type=Path, default=Path("captures"))
    sniff.add_argument("--ports", type=int, nargs="+", default=list(sniffer.DEFAULT_PORTS))
    serve = sub.add_parser("serve", help="sobe o Message (TCP 7313) e o Channel (TCP 7314)")
    # SUPPRESS: sem `--config` aqui, vale o do nível principal, sem sobrescrevê-lo.
    serve.add_argument("--config", type=Path, default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    account = sub.add_parser("account", help="contas e tokens de login")
    actions = account.add_subparsers(dest="action", required=True)
    create = actions.add_parser("create", help="cria conta, gera token e grava o .bat")
    create.add_argument("--user", required=True)
    create.add_argument("--nickname", required=True)
    create.add_argument("--client-dir", type=Path)
    token = actions.add_parser("token", help="regenera o token (invalida o anterior)")
    token.add_argument("--user", required=True)
    token.add_argument("--client-dir", type=Path)
    grant = actions.add_parser("grant", help="soma exp, LD e Cash à conta (sem aviso ao servidor)")
    grant.add_argument("--user", required=True)
    grant.add_argument("--exp", type=int, default=0)
    grant.add_argument("--ld", type=int, default=0)
    grant.add_argument("--cash", type=int, default=0)
    ban = actions.add_parser("ban", help="bloqueia a conta por N dias (sem aviso ao servidor)")
    ban.add_argument("--user", required=True)
    ban.add_argument("--days", type=int, required=True)
    unban = actions.add_parser("unban", help="remove o bloqueio da conta")
    unban.add_argument("--user", required=True)
    item = actions.add_parser("item", help="itens do inventário")
    item_add = item.add_subparsers(dest="op", required=True).add_parser(
        "add", help="cria um item com prazo em dias"
    )
    item_add.add_argument("username")
    item_add.add_argument("--catalog", type=int, required=True)
    item_add.add_argument("--days", type=int, required=True)
    morat = actions.add_parser("morat", help="morats do inventário")
    morat_add = morat.add_subparsers(dest="op", required=True).add_parser(
        "add", help="cria um morat em um gate (0 a 7)"
    )
    morat_add.add_argument("username")
    morat_add.add_argument("--catalog", type=int, required=True)
    morat_add.add_argument("--gate", type=int, required=True)
    kit = actions.add_parser("kit", help="kit inicial da conta (morats com peças padrão)")
    kit_apply = kit.add_subparsers(dest="op", required=True).add_parser(
        "apply", help="aplica o kit a uma conta existente (pula gates ocupados)"
    )
    kit_apply.add_argument("username")
    clan = sub.add_parser("clan", help="clãs (sem aviso ao servidor em execução)")
    clan_actions = clan.add_subparsers(dest="action", required=True)
    clan_create = clan_actions.add_parser("create", help="cria o clã com o mestre como membro")
    clan_create.add_argument("name")
    clan_create.add_argument("--master", required=True, help="usuário do mestre")
    clan_create.add_argument("--mark", type=int, default=0)
    clan_join = clan_actions.add_parser("join", help="põe a conta num clã")
    clan_join.add_argument("username")
    clan_join.add_argument("--clan", required=True)
    clan_join.add_argument("--grade", type=int, default=0)
    clan_leave = clan_actions.add_parser("leave", help="tira a conta do clã")
    clan_leave.add_argument("username")
    clan_rename = clan_actions.add_parser("rename", help="muda o nome do clã")
    clan_rename.add_argument("clan")
    clan_rename.add_argument("--to", required=True)
    clan_mark = clan_actions.add_parser("mark", help="muda a marca do clã")
    clan_mark.add_argument("clan")
    clan_mark.add_argument("--mark", type=int, required=True)
    clan_show = clan_actions.add_parser("show", help="mostra o clã e os membros")
    clan_show.add_argument("clan")
    shop = sub.add_parser("shop", help="loja: venda por id, com preço por nível (D191)")
    shop_actions = shop.add_subparsers(dest="action", required=True)
    shop_actions.add_parser(
        "sync", help="importa do cliente as vendas (preço e nome; enabled de quem existe é mantido)"
    )
    shop_list = shop_actions.add_parser("list", help="mostra ID, nome, preços e status")
    shop_list.add_argument("--disabled", action="store_true", help="só os desativados")
    shop_enable = shop_actions.add_parser("enable", help="habilita o item na loja")
    shop_enable.add_argument("catalog", type=int, help="id do catálogo")
    shop_disable = shop_actions.add_parser("disable", help="desativa o item (compra recusada)")
    shop_disable.add_argument("catalog", type=int, help="id do catálogo")
    shop_price = shop_actions.add_parser(
        "price", help="muda o preço de um nível; 0 = não vende na moeda (morat: LD já com o ×5)"
    )
    shop_price.add_argument("catalog", type=int, help="id do catálogo")
    shop_price.add_argument("tier", type=int, choices=(0, 1, 2, 3), help="nível de 0 a 3")
    shop_price.add_argument("--point", type=int, help="preço em LD")
    shop_price.add_argument("--cash", type=int, help="preço em Cash")
    return parser


def main() -> None:
    args = _parser().parse_args()
    try:
        settings = load_settings(args.config)
    except ValueError as e:  # ValidationError do pydantic também é ValueError
        raise SystemExit(f"configuração inválida: {e}") from None

    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(message)s")
    cli = Cli(settings)
    with contextlib.suppress(KeyboardInterrupt):
        if args.cmd == "sniff":
            args.out.mkdir(parents=True, exist_ok=True)
            asyncio.run(sniffer.Sniffer(args.out).run(args.ports))
        elif args.cmd == "serve":
            asyncio.run(cli.serve())
        else:
            try:
                if args.cmd == "clan":
                    saida = asyncio.run(cli.clan(args))
                elif args.cmd == "shop":
                    saida = asyncio.run(cli.shop(args))
                else:
                    saida = asyncio.run(cli.account(args))
            except (ValueError, AccountConflict, InventoryConflict, ClanConflict) as e:
                raise SystemExit(f"erro: {e}") from None
            print(saida)


if __name__ == "__main__":
    main()
