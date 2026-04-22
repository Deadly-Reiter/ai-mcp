from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    DATA = "data-agent"
    LLM = "llm-agent"
    COMPUTE = "compute-agent"


class RunStage(str, Enum):
    PLAN = "PLAN"
    AUTHORIZE = "AUTHORIZE"
    FUND = "FUND"
    DISPATCH = "DISPATCH"
    AWAIT_RESULTS = "AWAIT_RESULTS"
    RETRY_AUTH = "RETRY_AUTH"
    RETRY_DISPATCH = "RETRY_DISPATCH"
    DEGRADED_AGGREGATE = "DEGRADED_AGGREGATE"
    FINAL_AGGREGATE = "FINAL_AGGREGATE"
    AUDIT_CLOSE = "AUDIT_CLOSE"
    REJECT = "REJECT"
    END = "END"


class ToolStatus(str, Enum):
    OK = "ok"
    ERROR = "error"


class AgentTask(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    target: AgentType
    instruction: str
    context: dict[str, Any] = Field(default_factory=dict)
    budget_usdc: float = 0.05
    deadline_s: float = 5.0
    priority: int = 5
    attempt: int = 1
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    authorized_domains: list[str] = Field(default_factory=list)
    policy_id: str | None = None
    delegation_token: str | None = None
    max_per_call: float | None = None


class AgentResult(BaseModel):
    task_id: str
    agent_id: str
    success: bool
    output: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    spent_usdc: float = 0.0
    duration_ms: int = 0
    error: str = ""
    attempt: int = 1
    trace_id: str = ""
    session_id: str = ""
    policy_id: str | None = None
    tx_hashes: list[str] = Field(default_factory=list)


class AP2Policy(BaseModel):
    policy_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    max_usdc: float
    max_per_call: float
    allowed_domains: list[str]
    expires_at: datetime
    user_signature: str = ""

    @classmethod
    def fresh(cls, agent_id: str, max_usdc: float, max_per_call: float, allowed_domains: list[str], ttl_minutes: int = 30):
        return cls(
            agent_id=agent_id,
            max_usdc=max_usdc,
            max_per_call=max_per_call,
            allowed_domains=allowed_domains,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
        )


class AuthorizationDecision(BaseModel):
    task_id: str
    target: AgentType
    approved: bool
    policy_id: str | None = None
    delegation_token: str | None = None
    reason: str = ""
    approved_budget_usdc: float = 0.0
    allowed_domains: list[str] = Field(default_factory=list)
    max_per_call: float = 0.0


class FundingPlan(BaseModel):
    allocations: dict[str, float] = Field(default_factory=dict)
    total_allocated: float = 0.0


class PaymentReceipt(BaseModel):
    receipt_id: str = Field(default_factory=lambda: str(uuid4()))
    wallet_id: str
    service: str
    resource: str
    amount_usdc: float
    tx_hash: str = Field(default_factory=lambda: f"tx-{uuid4().hex[:12]}")


class ToolCall(BaseModel):
    tool_call_id: str = Field(default_factory=lambda: str(uuid4()))
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    trace_id: str
    session_id: str
    policy_id: str
    delegation_token: str
    allowed_domains: list[str]
    max_per_call: float


class ToolResult(BaseModel):
    tool_call_id: str
    tool_name: str
    status: ToolStatus
    content: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    cost_usdc: float = 0.0
    latency_ms: int = 0
    tx_hash: str | None = None
    error: str = ""
