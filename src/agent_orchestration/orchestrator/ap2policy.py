from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone

import jwt

from agent_orchestration.shared.models import AP2Policy, AgentTask, AgentType, AuthorizationDecision


class AP2PolicyManager:
    def __init__(self, user_secret: str | None = None) -> None:
        secret = user_secret or os.getenv("AP2_USER_SECRET") or secrets.token_urlsafe(32)
        if len(secret.encode("utf-8")) < 32:
            raise ValueError("AP2_USER_SECRET must be at least 32 bytes for HS256")
        self.user_secret = secret
        self.policies: dict[AgentType, AP2Policy] = {}

    def _payload(self, policy: AP2Policy) -> dict:
        payload = policy.model_dump(mode="json", exclude={"user_signature"})
        expires = payload.get("expires_at")
        if hasattr(expires, "isoformat"):
            payload["expires_at"] = expires.isoformat()
        return payload

    def _sign(self, policy: AP2Policy) -> AP2Policy:
        policy.user_signature = jwt.encode(self._payload(policy), self.user_secret, algorithm="HS256")
        return policy

    def verify(self, policy: AP2Policy) -> bool:
        if not policy.user_signature:
            return False
        try:
            decoded = jwt.decode(policy.user_signature, self.user_secret, algorithms=["HS256"])
        except jwt.PyJWTError:
            return False
        return decoded == self._payload(policy)

    def _decision(self, task: AgentTask, approved: bool, reason: str, policy: AP2Policy | None = None) -> AuthorizationDecision:
        return AuthorizationDecision(
            task_id=task.task_id,
            target=task.target,
            approved=approved,
            policy_id=policy.policy_id if policy else None,
            delegation_token=policy.user_signature if (policy and approved) else None,
            reason=reason,
            approved_budget_usdc=task.budget_usdc if approved else 0.0,
            allowed_domains=policy.allowed_domains if (policy and approved) else [],
            max_per_call=policy.max_per_call if (policy and approved) else 0.0,
        )

    def create_default_policies(self) -> None:
        defaults = {
            AgentType.DATA: AP2Policy.fresh(AgentType.DATA.value, 0.05, 0.05, ["data.x402.org"]),
            AgentType.LLM: AP2Policy.fresh(AgentType.LLM.value, 0.02, 0.02, ["llm.x402.org"]),
            AgentType.COMPUTE: AP2Policy.fresh(AgentType.COMPUTE.value, 0.05, 0.05, ["compute.x402.org"]),
        }
        self.policies = {k: self._sign(v) for k, v in defaults.items()}

    def authorize_tasks(self, tasks: list[AgentTask]) -> list[AuthorizationDecision]:
        out: list[AuthorizationDecision] = []
        for task in tasks:
            policy = self.policies.get(task.target)
            if not policy or not self.verify(policy):
                out.append(self._decision(task, False, "invalid or missing policy", policy))
                continue
            expires_at = policy.expires_at
            if isinstance(expires_at, str):
                expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            else:
                expires_dt = expires_at
            if expires_dt.tzinfo is None:
                expires_dt = expires_dt.replace(tzinfo=timezone.utc)
            if expires_dt <= datetime.now(timezone.utc):
                out.append(self._decision(task, False, "policy expired", policy))
                continue
            if task.budget_usdc > policy.max_usdc or task.budget_usdc > policy.max_per_call:
                out.append(self._decision(task, False, "policy budget exceeded", policy))
                continue
            out.append(self._decision(task, True, "approved", policy))
        return out
