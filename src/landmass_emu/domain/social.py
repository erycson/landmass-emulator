"""Amigos e bloqueios: validação que o cliente não faz (07-progression §5.13, R-SOC-01). Sem IO."""

from landmass_emu.domain.account import Account


class SocialRules:
    def target(self, owner: Account, found: Account | None) -> Account:
        """Conta alvo de 181 ou 186. Recusa conta inexistente e a própria conta."""
        if found is None:
            raise ValueError("conta inexistente")
        if found.id == owner.id:
            raise ValueError("a própria conta não pode ser adicionada")
        return found
