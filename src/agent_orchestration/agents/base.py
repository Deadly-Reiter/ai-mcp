from __future__ import annotations

from abc import ABC, abstractmethod

from agent_orchestration.bus.eventbus import EventBus
from agent_orchestration.shared.audit import AuditLogger
from agent_orchestration.shared.models import AgentResult, AgentTask, AgentType
from agent_orchestration.wallets.wallets import AgentWallet


class BudgetExhaustedError(RuntimeError):
    pass


class BaseAgent(ABC):
    def __init__(self, agent_id: str, budget_usdc: float, wallet: AgentWallet, bus: EventBus, audit: AuditLogger) -> None:
        self.agent_id = agent_id
        self.budget_max = budget_usdc
        self.wallet = wallet
        self.bus = bus
        self.audit = audit
        self.spent = 0.0

    def record_spend(self, amount: float) -> None:
        self.spent = round(self.spent + amount, 6)
        if self.spent > self.budget_max + 1e-9:
            raise BudgetExhaustedError(f"{self.agent_id} exceeded budget {self.budget_max}")

    async def run_forever(self, agent_type: AgentType) -> None:
        while True:
            task = await self.bus.subscribe(agent_type)
            result = await self.handle_task(task)
            await self.bus.publish_result(result)

    async def handle_task(self, task: AgentTask) -> AgentResult:
        self.audit.log("task_started", agent_id=self.agent_id, task_id=task.task_id, attempt=task.attempt, policy_id=task.policy_id)
        try:
            result = await self.execute(task)
            self.audit.log("task_finished", agent_id=self.agent_id, task_id=task.task_id, success=result.success, spent_usdc=result.spent_usdc)
            return result
        except Exception as exc:
            self.audit.log("task_failed", agent_id=self.agent_id, task_id=task.task_id, error=str(exc))
            return AgentResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                success=False,
                error=str(exc),
                attempt=task.attempt,
                trace_id=task.trace_id,
                session_id=task.session_id,
                policy_id=task.policy_id,
            )

    @abstractmethod
    async def execute(self, task: AgentTask) -> AgentResult:
        raise NotImplementedError
