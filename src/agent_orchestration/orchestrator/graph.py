from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from agent_orchestration.bus.eventbus import EventBus
from agent_orchestration.orchestrator.aggregator import aggregate_results
from agent_orchestration.orchestrator.ap2policy import AP2PolicyManager
from agent_orchestration.orchestrator.planner import decompose_task
from agent_orchestration.shared.audit import AuditLogger
from agent_orchestration.shared.models import AgentResult, AgentTask, AuthorizationDecision, FundingPlan, RunStage
from agent_orchestration.wallets.wallets import AgentWallet, MasterWallet


@dataclass
class OrchestratorState:
    task_input: str
    stage: RunStage = RunStage.PLAN
    subtasks: list[AgentTask] = field(default_factory=list)
    authorized_tasks: list[AgentTask] = field(default_factory=list)
    decisions: list[AuthorizationDecision] = field(default_factory=list)
    funding_plan: FundingPlan = field(default_factory=FundingPlan)
    results: list[AgentResult] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    retries: dict[str, int] = field(default_factory=dict)
    degraded: bool = False
    final_output: str = ""
    total_spent: float = 0.0
    authorized_budget_total: float = 0.0
    errors: str | None = None


class OrchestratorGraph:
    def __init__(self, bus: EventBus, audit: AuditLogger, ap2: AP2PolicyManager, master_wallet: MasterWallet, wallets: dict[str, AgentWallet], collect_timeout_s: float = 0.5, max_retries: int = 1) -> None:
        self.bus = bus
        self.audit = audit
        self.ap2 = ap2
        self.master_wallet = master_wallet
        self.wallets = wallets
        self.collect_timeout_s = collect_timeout_s
        self.max_retries = max_retries

    async def run(self, task_input: str) -> OrchestratorState:
        state = OrchestratorState(task_input=task_input)
        try:
            await self.node_plan(state)
            route = await self.node_authorize(state)
            if route == RunStage.REJECT:
                await self.node_reject(state)
                await self.node_audit_close(state)
                return state
            await self.node_fund(state)
            await self.node_dispatch(state)
            route = await self.node_await_results(state)
            while route in {RunStage.RETRY_AUTH, RunStage.RETRY_DISPATCH}:
                if route == RunStage.RETRY_AUTH:
                    await self.node_retry_auth(state)
                    await self.node_dispatch(state)
                else:
                    await self.node_retry_dispatch(state)
                route = await self.node_await_results(state)
            if route == RunStage.DEGRADED_AGGREGATE:
                await self.node_degraded_aggregate(state)
            elif route == RunStage.FINAL_AGGREGATE:
                await self.node_final_aggregate(state)
            else:
                state.errors = state.errors or f"unexpected route: {route.value}"
                await self.node_degraded_aggregate(state)
            await self.node_audit_close(state)
        except Exception as exc:
            state.errors = str(exc)
            state.degraded = True
            await self.node_degraded_aggregate(state)
            await self.node_audit_close(state)
        return state

    async def node_plan(self, state: OrchestratorState) -> None:
        state.stage = RunStage.PLAN
        state.subtasks = await decompose_task(state.task_input)
        self.audit.log("state_change", stage=state.stage.value, task_input=state.task_input, subtasks=len(state.subtasks))

    async def node_authorize(self, state: OrchestratorState) -> RunStage:
        state.stage = RunStage.AUTHORIZE
        state.decisions = self.ap2.authorize_tasks(state.subtasks)
        self.audit.log("state_change", stage=state.stage.value, approvals=sum(1 for d in state.decisions if d.approved), rejections=sum(1 for d in state.decisions if not d.approved))
        approved_map = {d.task_id: d for d in state.decisions if d.approved}
        if not approved_map:
            state.errors = "all subtasks rejected by AP2"
            state.degraded = True
            return RunStage.REJECT
        for task in state.subtasks:
            decision = approved_map.get(task.task_id)
            if decision:
                task.policy_id = decision.policy_id
                task.delegation_token = decision.delegation_token
                task.authorized_domains = decision.allowed_domains
                task.max_per_call = decision.max_per_call
                state.authorized_tasks.append(task)
                state.authorized_budget_total = round(state.authorized_budget_total + decision.approved_budget_usdc, 6)
            else:
                state.degraded = True
        return RunStage.FUND

    async def node_fund(self, state: OrchestratorState) -> None:
        state.stage = RunStage.FUND
        allocations: dict[str, float] = {}
        for task in state.authorized_tasks:
            wallet = self.wallets[task.target.value]
            topup = round(max(0.0, task.budget_usdc - wallet.balance_usdc), 6)
            if topup > 0:
                tx = self.master_wallet.fund_agent(wallet, topup)
                self.audit.log("wallet_funded", wallet_id=wallet.wallet_id, amount_usdc=topup, tx_hash=tx, task_id=task.task_id)
            allocations[task.target.value] = round(allocations.get(task.target.value, 0.0) + task.budget_usdc, 6)
        state.funding_plan = FundingPlan(allocations=allocations, total_allocated=round(sum(allocations.values()), 6))
        self.audit.log("state_change", stage=state.stage.value, total_allocated=state.funding_plan.total_allocated)

    async def node_dispatch(self, state: OrchestratorState) -> None:
        state.stage = RunStage.DISPATCH
        self.audit.log("state_change", stage=state.stage.value, task_count=len(state.authorized_tasks))
        for task in state.authorized_tasks:
            await self.bus.publish(task)

    async def node_await_results(self, state: OrchestratorState) -> RunStage:
        state.stage = RunStage.AWAIT_RESULTS
        completed = {r.task_id for r in state.results}
        outstanding = {t.task_id for t in state.authorized_tasks if t.task_id not in completed}
        prior_results = {r.task_id: r for r in state.results}
        try:
            async with asyncio.timeout(self.collect_timeout_s):
                async for result in self.bus.subscribe_results():
                    if result.task_id in outstanding:
                        prior_results[result.task_id] = result
                        outstanding.discard(result.task_id)
                    if not outstanding:
                        break
        except TimeoutError:
            pass
        state.results = list(prior_results.values())
        state.pending = list(outstanding)
        self.audit.log("state_change", stage=state.stage.value, received=len(state.results), pending=len(state.pending))
        auth_errors = [r for r in state.results if (not r.success and r.error and "policy" in r.error.lower())]
        if auth_errors and any(state.retries.get(r.task_id, 0) < self.max_retries for r in auth_errors):
            return RunStage.RETRY_AUTH
        if state.pending and any(state.retries.get(task_id, 0) < self.max_retries for task_id in state.pending):
            return RunStage.RETRY_DISPATCH
        if state.degraded or state.pending or any(not r.success for r in state.results) or len(state.results) < len(state.authorized_tasks):
            state.degraded = True
            return RunStage.DEGRADED_AGGREGATE
        return RunStage.FINAL_AGGREGATE

    async def node_retry_auth(self, state: OrchestratorState) -> None:
        state.stage = RunStage.RETRY_AUTH
        self.audit.log("state_change", stage=state.stage.value)
        refreshed = self.ap2.authorize_tasks(state.authorized_tasks)
        approved_map = {d.task_id: d for d in refreshed if d.approved}
        for task in state.authorized_tasks:
            if task.task_id in approved_map:
                d = approved_map[task.task_id]
                task.policy_id = d.policy_id
                task.delegation_token = d.delegation_token
                task.authorized_domains = d.allowed_domains
                task.max_per_call = d.max_per_call
                state.retries[task.task_id] = state.retries.get(task.task_id, 0) + 1

    async def node_retry_dispatch(self, state: OrchestratorState) -> None:
        state.stage = RunStage.RETRY_DISPATCH
        self.audit.log("state_change", stage=state.stage.value, pending=len(state.pending))
        for task in state.authorized_tasks:
            if task.task_id in state.pending:
                task.attempt += 1
                state.retries[task.task_id] = state.retries.get(task.task_id, 0) + 1
                await self.bus.publish(task)

    async def node_degraded_aggregate(self, state: OrchestratorState) -> None:
        state.stage = RunStage.DEGRADED_AGGREGATE
        state.degraded = True
        state.total_spent = round(sum(r.spent_usdc for r in state.results if r.success), 6)
        state.final_output = await aggregate_results(state.results, degraded=True)
        self.audit.log("state_change", stage=state.stage.value, total_spent=state.total_spent)

    async def node_final_aggregate(self, state: OrchestratorState) -> None:
        state.stage = RunStage.FINAL_AGGREGATE
        state.total_spent = round(sum(r.spent_usdc for r in state.results if r.success), 6)
        state.final_output = await aggregate_results(state.results, degraded=False)
        self.audit.log("state_change", stage=state.stage.value, total_spent=state.total_spent)

    async def node_reject(self, state: OrchestratorState) -> None:
        state.stage = RunStage.REJECT
        self.audit.log("state_change", stage=state.stage.value, error=state.errors or "policy rejection")

    async def node_audit_close(self, state: OrchestratorState) -> None:
        state.stage = RunStage.AUDIT_CLOSE
        swept = {}
        for name, wallet in self.wallets.items():
            swept[name] = self.master_wallet.sweep_agent(wallet)
        self.audit.log("state_change", stage=state.stage.value, swept=swept, master_balance=self.master_wallet.balance_usdc, total_spent=state.total_spent, degraded=state.degraded, errors=state.errors)
        state.stage = RunStage.END
