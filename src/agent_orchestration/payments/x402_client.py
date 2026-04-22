from __future__ import annotations

from agent_orchestration.shared.audit import AuditLogger
from agent_orchestration.shared.models import PaymentReceipt
from agent_orchestration.wallets.wallets import AgentWallet


class X402Client:
    def __init__(self, wallet: AgentWallet, audit: AuditLogger):
        self.wallet = wallet
        self.audit = audit

    async def pay(self, service: str, resource: str, amount_usdc: float, trace_id: str, session_id: str) -> PaymentReceipt:
        self.wallet.spend(amount_usdc)
        receipt = PaymentReceipt(wallet_id=self.wallet.wallet_id, service=service, resource=resource, amount_usdc=amount_usdc)
        self.audit.log(
            "payment_event",
            wallet_id=self.wallet.wallet_id,
            service=service,
            resource=resource,
            amount_usdc=amount_usdc,
            tx_hash=receipt.tx_hash,
            trace_id=trace_id,
            session_id=session_id,
        )
        return receipt
