from __future__ import annotations

from agent_orchestration.shared.models import AgentTask, AgentType


async def decompose_task(task_input: str) -> list[AgentTask]:
    return [
        AgentTask(target=AgentType.DATA, instruction=f"Collect market data for {task_input}", budget_usdc=0.05, priority=8),
        AgentTask(target=AgentType.LLM, instruction=f"Summarize implications for {task_input}", budget_usdc=0.02, priority=6),
        AgentTask(target=AgentType.COMPUTE, instruction=f"Backtest signal for {task_input}", budget_usdc=0.05, priority=7),
    ]
