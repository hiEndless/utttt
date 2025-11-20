import uuid
from typing import Optional

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import (
    Message,
    Part,
    Role,
    TextPart,
    Task,
    TaskStatus,
    TaskState,
)


class ExpertAgentExecutor(AgentExecutor):
    def __init__(self, expert_agent, name: str):
        self.expert = expert_agent
        self.name = name

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_text = context.get_user_input()
        reply = await self.expert.run(user_text)
        message = Message(
            role=Role.agent,
            parts=[Part(root=TextPart(text=reply))],
            message_id=str(uuid.uuid4()),
            task_id=context.task_id,
            context_id=context.context_id,
        )
        task = Task(
            id=context.task_id or str(uuid.uuid4()),
            context_id=context.context_id or str(uuid.uuid4()),
            status=TaskStatus(state=TaskState.completed, message=message),
            artifacts=[],
            history=[message],
        )
        await event_queue.enqueue_event(task)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = Task(
            id=context.task_id or str(uuid.uuid4()),
            context_id=context.context_id or str(uuid.uuid4()),
            status=TaskStatus(state=TaskState.canceled),
            artifacts=[],
            history=[],
        )
        await event_queue.enqueue_event(task)