"""Clã: regras que o servidor aplica e o cliente não aplica (07-progression §4.8, R-CLAN-01..03).
Criação, entrada, saída, nome e marca são feitas pela CLI: o cliente não tem pedido para elas
(R-CLAN-01). Sem IO."""

MAX_CLAN_NAME = 16  # `clans.name` é `String(16)` (legado: `tbl_clan.clan_name varchar(16)`)
MAX_CLAN_MARK = 2**31 - 1  # `clan_mark` vai como i32 em 172 e 195
_ENCODING = "cp1252"  # encoding dos textos no fio (protocol/message.py)


class ClanError(ValueError):
    """Pedido de clã recusado. A mensagem vai à CLI."""


class ClanRules:
    def check_name(self, name: str) -> str:
        if not 1 <= len(name) <= MAX_CLAN_NAME:
            raise ClanError(f"nome do clã deve ter de 1 a {MAX_CLAN_NAME} caracteres")
        if "\0" in name:
            raise ClanError("nome do clã não pode ter NUL")
        try:
            name.encode(_ENCODING)
        except UnicodeEncodeError:
            raise ClanError("nome do clã deve caber em cp1252") from None
        return name

    def check_mark(self, mark: int) -> int:
        if not 0 <= mark <= MAX_CLAN_MARK:
            raise ClanError(f"marca do clã fora de 0 a {MAX_CLAN_MARK}")
        return mark

    def check_leave(self, *, is_master: bool, member_count: int) -> None:
        """Mestre não sai enquanto houver outros membros (shortcut: sem troca de mestre; o legado
        não tem regra para isso, D59). Clã sem membros é apagado pelo chamador."""
        if is_master and member_count > 1:
            raise ClanError("o mestre não pode sair com outros membros no clã")
