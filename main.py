from __future__ import annotations

import asyncio
import os
from pathlib import Path

from agent_orchestration.agents.agents import ComputeAgent, DataAgent, LlmAgent
from agent_orchestration.bus.eventbus import EventBus
from agent_orchestration.orchestrator.ap2policy import AP2PolicyManager
from agent_orchestration.orchestrator.graph import OrchestratorGraph
from agent_orchestration.shared.audit import AuditLogger
from agent_orchestration.shared.models import AgentType
from agent_orchestration.wallets.wallets import AgentWallet, MasterWallet


async def main() -> None:
    os.environ.setdefault('AP2_USER_SECRET', '0123456789abcdef0123456789abcdef')
    audit = AuditLogger(Path('runtime-audit.jsonl'))
    bus = EventBus()
    for t in AgentType:
        bus.register_agent(t)
    master = MasterWallet('master-wallet', 10.0)
    wallets = {t.value: AgentWallet(f'{t.value}-wallet', 0.0) for t in AgentType}
    ap2 = AP2PolicyManager()
    ap2.create_default_policies()
    agents = [
        DataAgent('data-agent', 0.05, wallets[AgentType.DATA.value], bus, audit),
        LlmAgent('llm-agent', 0.02, wallets[AgentType.LLM.value], bus, audit),
        ComputeAgent('compute-agent', 0.05, wallets[AgentType.COMPUTE.value], bus, audit),
    ]
    workers = [
        asyncio.create_task(agents[0].run_forever(AgentType.DATA)),
        asyncio.create_task(agents[1].run_forever(AgentType.LLM)),
        asyncio.create_task(agents[2].run_forever(AgentType.COMPUTE)),
    ]
    graph = OrchestratorGraph(bus, audit, ap2, master, wallets, collect_timeout_s=0.5, max_retries=1)
    try:
        state = await graph.run('Analyze SOL market')
        print('stage:', state.stage.value)
        print('degraded:', state.degraded)
        print('authorized_budget_total:', state.authorized_budget_total)
        print('total_spent:', state.total_spent)
        print('final_output:', state.final_output)
        print('master_balance:', master.balance_usdc)
    finally:
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)


if __name__ == '__main__':
    asyncio.run(main())
