from __future__ import annotations

from agent_orchestration.agents.base import BaseAgent
from agent_orchestration.mcps.servers import ComputeMCPServer, DataMCPServer, LlmMCPServer
from agent_orchestration.shared.models import AgentResult, AgentTask, ToolCall, ToolStatus


class DataAgent(BaseAgent):
    def __init__(self, agent_id, budget_usdc, wallet, bus, audit):
        super().__init__(agent_id, budget_usdc, wallet, bus, audit)
        self.server = DataMCPServer(wallet, audit)

    async def execute(self, task: AgentTask) -> AgentResult:
        symbol = "SOL" if "SOL" in task.instruction.upper() else "BTC"
        calls = [
            ToolCall(tool_name="get_price", arguments={"symbol": symbol}, trace_id=task.trace_id, session_id=task.session_id, policy_id=task.policy_id or "", delegation_token=task.delegation_token or "", allowed_domains=task.authorized_domains, max_per_call=task.max_per_call or 0.0),
            ToolCall(tool_name="get_onchain_metrics", arguments={"protocol": symbol}, trace_id=task.trace_id, session_id=task.session_id, policy_id=task.policy_id or "", delegation_token=task.delegation_token or "", allowed_domains=task.authorized_domains, max_per_call=task.max_per_call or 0.0),
        ]
        results = [await self.server.call_tool(c) for c in calls]
        for r in results:
            if r.status is ToolStatus.ERROR:
                raise RuntimeError(r.error)
        cost = round(sum(r.cost_usdc for r in results), 6)
        self.record_spend(cost)
        return AgentResult(task_id=task.task_id, agent_id=self.agent_id, success=True, output=f"Data ready for {symbol}", data={"price": results[0].data, "metrics": results[1].data}, spent_usdc=cost, attempt=task.attempt, trace_id=task.trace_id, session_id=task.session_id, policy_id=task.policy_id, tx_hashes=[r.tx_hash for r in results if r.tx_hash])


class LlmAgent(BaseAgent):
    def __init__(self, agent_id, budget_usdc, wallet, bus, audit):
        super().__init__(agent_id, budget_usdc, wallet, bus, audit)
        self.server = LlmMCPServer(wallet, audit)

    async def execute(self, task: AgentTask) -> AgentResult:
        call = ToolCall(tool_name="summarize", arguments={"topic": task.instruction}, trace_id=task.trace_id, session_id=task.session_id, policy_id=task.policy_id or "", delegation_token=task.delegation_token or "", allowed_domains=task.authorized_domains, max_per_call=task.max_per_call or 0.0)
        result = await self.server.call_tool(call)
        if result.status is ToolStatus.ERROR:
            raise RuntimeError(result.error)
        self.record_spend(result.cost_usdc)
        return AgentResult(task_id=task.task_id, agent_id=self.agent_id, success=True, output=result.data["summary"], data=result.data, spent_usdc=result.cost_usdc, attempt=task.attempt, trace_id=task.trace_id, session_id=task.session_id, policy_id=task.policy_id, tx_hashes=[result.tx_hash] if result.tx_hash else [])


class ComputeAgent(BaseAgent):
    def __init__(self, agent_id, budget_usdc, wallet, bus, audit):
        super().__init__(agent_id, budget_usdc, wallet, bus, audit)
        self.server = ComputeMCPServer(wallet, audit)

    async def execute(self, task: AgentTask) -> AgentResult:
        asset = "SOL" if "SOL" in task.instruction.upper() else "BTC"
        calls = [
            ToolCall(tool_name="backtest", arguments={"asset": asset}, trace_id=task.trace_id, session_id=task.session_id, policy_id=task.policy_id or "", delegation_token=task.delegation_token or "", allowed_domains=task.authorized_domains, max_per_call=task.max_per_call or 0.0),
            ToolCall(tool_name="score_signal", arguments={"asset": asset}, trace_id=task.trace_id, session_id=task.session_id, policy_id=task.policy_id or "", delegation_token=task.delegation_token or "", allowed_domains=task.authorized_domains, max_per_call=task.max_per_call or 0.0),
        ]
        results = [await self.server.call_tool(c) for c in calls]
        for r in results:
            if r.status is ToolStatus.ERROR:
                raise RuntimeError(r.error)
        cost = round(sum(r.cost_usdc for r in results), 6)
        self.record_spend(cost)
        return AgentResult(task_id=task.task_id, agent_id=self.agent_id, success=True, output=f"Compute ready for {asset}", data={"backtest": results[0].data, "score": results[1].data}, spent_usdc=cost, attempt=task.attempt, trace_id=task.trace_id, session_id=task.session_id, policy_id=task.policy_id, tx_hashes=[r.tx_hash for r in results if r.tx_hash])
