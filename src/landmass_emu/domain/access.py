"""Nível de acesso (`ucAccess` do cliente, D193). Regras puras, sem IO.

O cliente só mostra os comandos de GM a quem tem o nível (XInterface L21263): `/ALLNOTIFY`,
`/NOTIFY`, `/EXPEL` e outros, com `>= 9`. Aqui a regra é a mesma, mas aplicada no servidor: quem
pede precisa do nível, qualquer que seja o cliente.
"""

GM_LEVEL = 9  # /ALLNOTIFY, /NOTIFY e /EXPEL (XInterface L21263-21290)
ADMIN_LEVEL = 10  # GMSay com cor, WatchPlayer e SwitchSpecMode (XInterface L17751, L23423)
MAX_ACCESS_LEVEL = 255  # `u8` no registro de jogador (R+0x1a em 151, 317 e 549)


def check_access_level(level: int) -> None:
    if not 0 <= level <= MAX_ACCESS_LEVEL:
        raise ValueError(f"nível de acesso: de 0 a {MAX_ACCESS_LEVEL}")


def may_notify(level: int) -> bool:
    """Pode mandar aviso (250) e expulsar (700): nível de GM ou acima."""
    return level >= GM_LEVEL


def may_expel(requester: int, target: int) -> bool:
    """Expulsão só de quem tem nível menor que o do GM. Entre pares, ninguém tira o outro.

    Regra escolhida (inferida): o cliente não mostra hierarquia de expulsão; a restrição evita que
    um GM tire outro GM ou a si mesmo.
    """
    return may_notify(requester) and requester > target
