"""Registros de jogador do servidor de partida (`MORATS.upl`, pasta `system\\`), usados pelos bots
(D221). Lido na primeira partida com bots e guardado; falha de leitura é ValueError, e a próxima
consulta tenta de novo.
"""

from pathlib import Path

from landmass_emu.domain.bots import player_records


class PlayerRecordFile:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._loaded: dict[str, str] | None = None

    def records(self) -> dict[str, str]:
        if self._loaded is None:
            try:
                texto = self._path.read_text(encoding="cp1252", errors="replace")
            except OSError as e:
                raise ValueError(f"MORATS.upl não lido: {e}") from e
            self._loaded = player_records(texto)
        return self._loaded
