import argparse
import asyncio
import contextlib
import logging
from pathlib import Path

from landmass_emu import sniffer
from landmass_emu.admin import AccountAdmin
from landmass_emu.app import game_servers, open_accounts
from landmass_emu.ports.accounts import AccountConflict
from landmass_emu.settings import Settings


class Cli:
    """Comandos `serve` e `account`. As settings entram no `__init__`."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def serve(self) -> None:
        async with game_servers(self._settings) as (message, channel):
            await asyncio.gather(message.serve_forever(), channel.serve_forever())

    async def account(self, args: argparse.Namespace) -> Path:
        client_dir: Path = args.client_dir or self._settings.client_dir
        async with open_accounts(self._settings) as accounts:
            admin = AccountAdmin(accounts, self._settings)
            if args.action == "create":
                return await admin.create(args.user, args.nickname, client_dir)
            return await admin.rotate_token(args.user, client_dir)


def main() -> None:
    parser = argparse.ArgumentParser(prog="landmass-emu")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sniff = sub.add_parser("sniff", help="grava os bytes enviados pelo cliente, sem responder")
    sniff.add_argument("--out", type=Path, default=Path("captures"))
    sniff.add_argument("--ports", type=int, nargs="+", default=list(sniffer.DEFAULT_PORTS))
    sub.add_parser("serve", help="sobe o Message (TCP 7313) e o Channel (TCP 7314)")
    account = sub.add_parser("account", help="contas e tokens de login")
    actions = account.add_subparsers(dest="action", required=True)
    create = actions.add_parser("create", help="cria conta, gera token e grava o .bat")
    create.add_argument("--user", required=True)
    create.add_argument("--nickname", required=True)
    create.add_argument("--client-dir", type=Path)
    token = actions.add_parser("token", help="regenera o token (invalida o anterior)")
    token.add_argument("--user", required=True)
    token.add_argument("--client-dir", type=Path)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    settings = Settings()
    cli = Cli(settings)
    with contextlib.suppress(KeyboardInterrupt):
        if args.cmd == "sniff":
            args.out.mkdir(parents=True, exist_ok=True)
            asyncio.run(sniffer.Sniffer(args.out).run(args.ports))
        elif args.cmd == "serve":
            asyncio.run(cli.serve())
        else:
            try:
                bat = asyncio.run(cli.account(args))
            except (ValueError, AccountConflict) as e:
                raise SystemExit(f"erro: {e}") from None
            print(bat)


if __name__ == "__main__":
    main()
