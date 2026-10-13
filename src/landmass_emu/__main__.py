import argparse
import asyncio
import contextlib
import logging
from pathlib import Path

from landmass_emu import sniffer
from landmass_emu.admin import create_account, rotate_token
from landmass_emu.app import game_servers, open_accounts
from landmass_emu.ports.accounts import AccountConflict
from landmass_emu.settings import Settings


async def _serve(settings: Settings) -> None:
    async with game_servers(settings) as (message, channel):
        await asyncio.gather(message.serve_forever(), channel.serve_forever())


async def _account(settings: Settings, args: argparse.Namespace) -> Path:
    client_dir: Path = args.client_dir or settings.client_dir
    async with open_accounts(settings) as accounts:
        if args.action == "create":
            return await create_account(accounts, settings, args.user, args.nickname, client_dir)
        return await rotate_token(accounts, settings, args.user, client_dir)


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
    with contextlib.suppress(KeyboardInterrupt):
        if args.cmd == "sniff":
            args.out.mkdir(parents=True, exist_ok=True)
            asyncio.run(sniffer.run(args.out, args.ports))
        elif args.cmd == "serve":
            asyncio.run(_serve(settings))
        else:
            try:
                bat = asyncio.run(_account(settings, args))
            except (ValueError, AccountConflict) as e:
                raise SystemExit(f"erro: {e}") from None
            print(bat)


if __name__ == "__main__":
    main()
