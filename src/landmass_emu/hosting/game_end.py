"""Bloco `GameEnded` do log do servidor de partida: um bloco por fim de partida, um registro por
jogador (tools/re/game_server_host.md, §11.4). Função pura: texto do log -> jogadores. Os nomes dos
campos
são os do log (`XGame.u`, `Log(..., 'GameEnded')`); as chaves ausentes ficam `None`.

As linhas de constantes (`GameEnded: DM_TakePoint = 1.00`) têm a mesma etiqueta, mas ficam fora do
cabeçalho `Ended ... Exp/Money =` e da linha de fechamento `=`; só o que está entre os dois conta.

O bloco não diz quem é bot. O `LMEmu` escreve `LMEmu: bot no fim <apelido>` para cada jogador
com a flag `bBot` do PRI no fim da partida (D252), e esses saem marcados como bot.
"""

import re

from landmass_emu.domain.match_stats import GameEndedPlayer

_HEADER = re.compile(r"^GameEnded: (\S+) Ended (.+?) Exp/Money =+\s*$")
_FOOTER = re.compile(r"^GameEnded: =+\s*$")
_FIELD = re.compile(r"^GameEnded:\s+(\w+)\s*=\s?(.*?)\s*$")
_BOT = re.compile(r"^ScriptLog: LMEmu: bot no fim (.+?)\s*$")


def parse_game_ended(text: str) -> tuple[GameEndedPlayer, ...]:
    """Jogadores de todos os blocos `GameEnded` completos do texto. O LM escreve um bloco por
    jogador (`LM_DeathMatch`, cabeçalho a cada `Player`). Apelido repetido: vale o último. Vazio
    sem bloco."""
    blocks: list[list[dict[str, str]]] = []
    atual: list[dict[str, str]] | None = None
    bots: set[str] = set()
    for linha in text.splitlines():
        if (bot := _BOT.match(linha)) is not None:
            bots.add(bot.group(1))
        elif _HEADER.match(linha):
            atual = []
        elif atual is not None and _FOOTER.match(linha):
            blocks.append(atual)
            atual = None
        elif atual is not None:
            casamento = _FIELD.match(linha)
            if casamento is None:
                continue
            chave, valor = casamento.group(1), casamento.group(2)
            if chave == "Player":
                atual.append({"Player": valor})
            elif atual:
                atual[-1][chave] = valor
    por_nick = {c["Player"]: c for bloco in blocks for c in bloco if "Player" in c}
    return tuple(_jogador(campos, bots) for campos in por_nick.values())


def _jogador(campos: dict[str, str], bots: set[str]) -> GameEndedPlayer:
    return GameEndedPlayer(
        nickname=campos["Player"],
        reason=campos.get("Reason"),
        kills=_inteiro(campos.get("Kills")),
        ranking=_inteiro(campos.get("Ranking")),
        played_percent=_percentual(campos.get("Played")),
        total_exp=_inteiro(campos.get("TotalExp")),
        total_money=_inteiro(campos.get("TotalMoney")),
        winner=_booleano(campos.get("Winner")),
        mission_score=_inteiro(campos.get("MissionScore")),
        bot=campos["Player"] in bots,
    )


def _inteiro(valor: str | None) -> int | None:
    # shortcut: exp e LD saem como float no log; arredondados para inteiro como em `match_players`.
    if valor is None or valor == "":
        return None
    try:
        return round(float(valor))
    except ValueError:
        return None


def _percentual(valor: str | None) -> float | None:
    if valor is None:
        return None
    try:
        return float(valor.rstrip("%").strip())
    except ValueError:
        return None


def _booleano(valor: str | None) -> bool | None:
    if valor == "True":
        return True
    if valor == "False":
        return False
    return None
