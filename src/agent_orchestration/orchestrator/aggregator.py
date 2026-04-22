from __future__ import annotations

from agent_orchestration.shared.models import AgentResult


async def aggregate_results(results: list[AgentResult], degraded: bool) -> str:
    good = [r for r in results if r.success]
    parts = [f"{r.agent_id}: {r.output} ({r.spent_usdc:.3f} USDC)" for r in good]
    prefix = "DEGRADED" if degraded else "FULL"
    return prefix + " | " + " | ".join(parts)
