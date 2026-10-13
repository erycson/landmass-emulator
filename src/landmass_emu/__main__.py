import argparse
import asyncio
import contextlib
import logging
from pathlib import Path

from landmass_emu import sniffer


def main() -> None:
    parser = argparse.ArgumentParser(prog="landmass-emu")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sniff = sub.add_parser("sniff", help="grava os bytes enviados pelo cliente, sem responder")
    sniff.add_argument("--out", type=Path, default=Path("captures"))
    sniff.add_argument("--ports", type=int, nargs="+", default=list(sniffer.DEFAULT_PORTS))
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(sniffer.run(args.out, args.ports))


if __name__ == "__main__":
    main()
