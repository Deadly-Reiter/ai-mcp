import asyncio
from pathlib import Path

import pytest

from agent_orchestration.agents.agents import ComputeAgent, DataAgent, LlmAgent
from agent_orchestration.bus.eventbus import EventBus
from agent_orchestration.orchestrator.ap2policy import AP2PolicyManager
from agent_orchestration.orchestrator.graph import OrchestratorGraph
from agent_orchestration.shared.audit import AuditLogger
from agent_orchestration.shared.models import AgentType, AP2Policy
from agent_orchestration.wallets.wallets import AgentWallet, MasterWallet

@pytest.mark.asyncio
async def test_policy_rejection(tmp_path: Path):
    audit = AuditLogger(tmp_path / "audit.jsonl")
    bus = EventBus()
    for t in AgentType:
        bus.register_agent(t)
    master = MasterWallet("master", 10.0)
    wallets = {t.value: AgentWallet(t.value, 0.0) for t in AgentType}
    
    ap2 = AP2PolicyManager()
    ap2.create_default_policies()
    # Намеренно делаем лимит 0.0 для DataAgent, чтобы вызвать policy reject
    ap2.policies[AgentType.DATA] = AP2Policy.fresh(AgentType.DATA.value, 0.0, 0.0, ["data.x402.org"])
    ap2.policies[AgentType.DATA] = ap2._sign(ap2.policies[AgentType.DATA])
    
    # Создаем и запускаем агентов
    agents = [
        DataAgent("data-agent", 0.05, wallets[AgentType.DATA.value], bus, audit),
        LlmAgent("llm-agent", 0.02, wallets[AgentType.LLM.value], bus, audit),
        ComputeAgent("compute-agent", 0.05, wallets[AgentType.COMPUTE.value], bus, audit),
    ]
    workers = [
        asyncio.create_task(agents[0].run_forever(AgentType.DATA)),
        asyncio.create_task(agents[1].run_forever(AgentType.LLM)),
        asyncio.create_task(agents[2].run_forever(AgentType.COMPUTE)),
    ]
    
    graph = OrchestratorGraph(bus, audit, ap2, master, wallets, collect_timeout_s=0.5, max_retries=1)
    try:
        state = await graph.run("Analyze SOL market")
    finally:
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

    assert state.degraded is True
    assert len(state.authorized_tasks) == 2
    assert state.total_spent == pytest.approx(0.07, abs=1e-6)
