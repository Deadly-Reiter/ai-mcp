import asyncio
from pathlib import Path

import pytest

from agent_orchestration.agents.agents import ComputeAgent, DataAgent, LlmAgent
from agent_orchestration.bus.eventbus import EventBus
from agent_orchestration.orchestrator.ap2policy import AP2PolicyManager
from agent_orchestration.orchestrator.graph import OrchestratorGraph
from agent_orchestration.shared.audit import AuditLogger
from agent_orchestration.shared.models import AgentType
from agent_orchestration.wallets.wallets import AgentWallet, MasterWallet


@pytest.mark.asyncio
async def test_retry_then_degraded(tmp_path: Path):
    audit = AuditLogger(tmp_path / "audit.jsonl")
    bus = EventBus()
    for t in AgentType:
        bus.register_agent(t)
    master = MasterWallet("master", 10.0)
    wallets = {t.value: AgentWallet(t.value, 0.0) for t in AgentType}
    ap2 = AP2PolicyManager()
    ap2.create_default_policies()

    data = DataAgent("data-agent", 0.05, wallets[AgentType.DATA.value], bus, audit)
    llm = LlmAgent("llm-agent", 0.02, wallets[AgentType.LLM.value], bus, audit)

    async def slow_compute(*_args, **_kwargs):
        await asyncio.sleep(1.0)

    workers = [
        asyncio.create_task(data.run_forever(AgentType.DATA)),
        asyncio.create_task(llm.run_forever(AgentType.LLM)),
        asyncio.create_task(slow_compute()),
    ]
    graph = OrchestratorGraph(bus, audit, ap2, master, wallets, collect_timeout_s=0.1, max_retries=1)
    try:
        state = await graph.run("Analyze SOL market")
    finally:
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

    assert state.degraded is True
    assert len(state.results) == 2
    assert state.total_spent == pytest.approx(0.035, abs=1e-6)
    assert "DEGRADED" in state.final_output
