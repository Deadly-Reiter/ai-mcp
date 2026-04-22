from __future__ import annotations

import json

from agent_orchestration.payments.x402_client import X402Client
from agent_orchestration.servers.resource_server import ResourceServer
from agent_orchestration.shared.models import ToolCall, ToolResult, ToolStatus
from agent_orchestration.wallets.wallets import AgentWallet
from agent_orchestration.shared.audit import AuditLogger


class MCPServerBase:
    def __init__(self, wallet: AgentWallet, audit: AuditLogger, service: ResourceServer):
        self.wallet = wallet
        self.audit = audit
        self.service = service
        self.client = X402Client(wallet=wallet, audit=audit)

    async def call_tool(self, call: ToolCall) -> ToolResult:
        try:
            price = self.service.quote(call.tool_name)
            receipt = await self.client.pay(self.service.service_name, call.tool_name, price, call.trace_id, call.session_id)
            payload = await self.service.fetch(call)
            return ToolResult(
                tool_call_id=call.tool_call_id,
                tool_name=call.tool_name,
                status=ToolStatus.OK,
                content=json.dumps(payload, ensure_ascii=False),
                data=payload,
                cost_usdc=price,
                latency_ms=20,
                tx_hash=receipt.tx_hash,
            )
        except Exception as exc:
            return ToolResult(tool_call_id=call.tool_call_id, tool_name=call.tool_name, status=ToolStatus.ERROR, error=str(exc))


class DataMCPServer(MCPServerBase):
    def __init__(self, wallet: AgentWallet, audit: AuditLogger):
        super().__init__(wallet, audit, ResourceServer("data-service", "data.x402.org", {"get_price": 0.01, "get_onchain_metrics": 0.005}))


class LlmMCPServer(MCPServerBase):
    def __init__(self, wallet: AgentWallet, audit: AuditLogger):
        super().__init__(wallet, audit, ResourceServer("llm-service", "llm.x402.org", {"summarize": 0.02}))


class ComputeMCPServer(MCPServerBase):
    def __init__(self, wallet: AgentWallet, audit: AuditLogger):
        super().__init__(wallet, audit, ResourceServer("compute.x402.org", "compute.x402.org", {"backtest": 0.03, "score_signal": 0.02}))
