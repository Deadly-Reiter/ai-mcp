from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AgentWallet:
    wallet_id: str
    balance_usdc: float = 0.0

    def fund(self, amount_usdc: float) -> None:
        self.balance_usdc = round(self.balance_usdc + amount_usdc, 6)

    def spend(self, amount_usdc: float) -> None:
        if amount_usdc > self.balance_usdc + 1e-9:
            raise ValueError(f"wallet {self.wallet_id} insufficient funds")
        self.balance_usdc = round(self.balance_usdc - amount_usdc, 6)


class MasterWallet(AgentWallet):
    def fund_agent(self, agent_wallet: AgentWallet, amount_usdc: float) -> str:
        self.spend(amount_usdc)
        agent_wallet.fund(amount_usdc)
        return f"fund-{self.wallet_id[:4]}-{agent_wallet.wallet_id[:4]}-{int(amount_usdc*1000)}"

    def sweep_agent(self, agent_wallet: AgentWallet) -> float:
        amount = round(agent_wallet.balance_usdc, 6)
        if amount > 0:
            agent_wallet.spend(amount)
            self.fund(amount)
        return amount
