"""Presença no Message Server: qual conexão autenticada está em cada conta. Em memória, sem IO.

Online é ter conexão autenticada no Message (07-progression §3). Não há aviso de entrada e saída:
o protocolo não tem opcode para isso, e o cliente consulta o estado (180, 190, 192). Acessado só
pelo loop de eventos.
"""

from landmass_emu.domain.lobby import Recipient


class MessagePresence:
    def __init__(self) -> None:
        self._sessions: dict[int, Recipient] = {}

    def bind(self, account_id: int, recipient: Recipient) -> None:
        """Conta autenticada nesta conexão. Outra conexão da mesma conta é substituída."""
        self._sessions[account_id] = recipient

    def unbind(self, recipient: Recipient) -> None:
        """Remove só as entradas desta conexão: fechar a conexão antiga não derruba a nova."""
        for account_id in [k for k, v in self._sessions.items() if v is recipient]:
            del self._sessions[account_id]

    def recipient_of(self, account_id: int) -> Recipient | None:
        return self._sessions.get(account_id)

    def is_online(self, account_id: int) -> bool:
        return account_id in self._sessions
