"""Moeda da compra. `bPoint` do 550: 1 = LD (`PointUnit`), 0 = Cash (`CashUnit`).

Fonte: docs/architecture/07-progression.md §5.1 e re/features.md §2.2.
"""

from enum import IntEnum


class Currency(IntEnum):
    CASH = 0
    LD = 1
