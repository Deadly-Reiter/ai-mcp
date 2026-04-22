from __future__ import annotations

import asyncio
from typing import AsyncGenerator

from agent_orchestration.shared.models import AgentResult, AgentTask, AgentType


class EventBus:
    def __init__(self) -> None:
        self.task_queues: dict[AgentType, asyncio.Queue[AgentTask]] = {}
        self.result_queue: asyncio.Queue[AgentResult] = asyncio.Queue()

    def register_agent(self, agent_type: AgentType) -> None:
        self.task_queues[agent_type] = asyncio.Queue()

    async def publish(self, task: AgentTask) -> None:
        await self.task_queues[task.target].put(task)

    async def subscribe(self, agent_type: AgentType) -> AgentTask:
        return await self.task_queues[agent_type].get()

    async def publish_result(self, result: AgentResult) -> None:
        await self.result_queue.put(result)

    async def subscribe_results(self) -> AsyncGenerator[AgentResult, None]:
        while True:
            yield await self.result_queue.get()
