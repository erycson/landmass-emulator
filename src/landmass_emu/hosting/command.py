"""Linha de comando do servidor de partida e leitura da tabela UDP do Windows. Funções puras.

A ordem segue o que foi validado com o `servidor.bat`: opções do motor antes de `login_server=`;
`version=` e `login_num=` por último, sem token depois. `PORT=` vai antes de `-log`.
"""

from pathlib import Path

from landmass_emu.domain.match import MatchPlan


def match_url(plan: MatchPlan) -> str:
    """Primeiro token: mapa, listen e as opções de jogo que o cliente lê em `InitGame`."""
    return (
        f"{plan.map_file}?listen?game={plan.game_class}?MaxPlayers={plan.max_players}"
        f"?TimeLimit={plan.time_limit}?GoalScore={plan.goal_score}"
    )


def build_command(
    exe: Path,
    plan: MatchPlan,
    *,
    port: int,
    message_addr: str,
    version: int,
    login_num: str,
) -> list[str]:
    # shortcut: PORT= validado só pelo código do RE (re/game_server_host.md, seção 10.2), sem
    # teste no jogo; se a porta não abrir, conferir o log de `binding to port` antes de mexer aqui.
    return [
        str(exe),
        match_url(plan),
        "-server",
        f"PORT={port}",
        "-log",
        f"login_server={message_addr}?version={version}?login_num={login_num}",
    ]


def udp_listeners(netstat_text: str) -> set[tuple[int, int]]:
    """(porta local, PID) das linhas UDP de `netstat -ano -p UDP`. Linhas de outro formato são
    ignoradas; o cabeçalho traduzido não casa com `UDP`."""
    found: set[tuple[int, int]] = set()
    for line in netstat_text.splitlines():
        parts = line.split()
        if len(parts) < 4 or parts[0] != "UDP":
            continue
        local, pid = parts[1], parts[-1]
        port_text = local.rsplit(":", 1)[-1]
        if port_text.isdigit() and pid.isdigit():
            found.add((int(port_text), int(pid)))
    return found
