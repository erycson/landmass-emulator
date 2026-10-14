"""Ficha do jogador (543): dados que o servidor tem, lidos sob demanda (07-progression §5.13, D107).

Sem IO. Os números vêm do repositório: a posição segue o empate de D18 (1, 1, 3) e as partidas
contam só quando têm resultado (D105)."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlayerProfile:
    rank: int  # posição no ranking geral: 1 + contas com exp maior
    games: int  # partidas com resultado (D105)
    wins: int
    losses: int
    kills: int
    deaths: int
    headshots: int
    total_exp: int
    nest: int  # nest regular, 0 sem nest
    clan_mark: int
    clan_name: str  # "" sem clã (o cliente mostra "Não cadastrado")
