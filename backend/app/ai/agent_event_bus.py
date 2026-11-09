import asyncio
import json
import logging
from collections import defaultdict
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

from app.models.agent import ActionApprovalStatus, AgentTask, TaskStatus

logger = logging.getLogger(__name__)

TERMINAL_EVENTS = {"task_finished", "task_cancelled", "task_failed"}


class AgentEventBus:
    """Real-time pub-sub event bus for autonomous agent step progression,

    milestones, and live Server-Sent Events (SSE) streaming.
    """

    _subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
    _history: dict[str, list[dict[str, Any]]] = defaultdict(list)
    _lock: asyncio.Lock = asyncio.Lock()
    MAX_HISTORY_PER_TASK = 50

    @classmethod
    async def publish(
        cls,
        task_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """Publish a milestone event to all active subscribers for the task

        and record it in event history.
        """
        payload = {
            "event": event_type,
            "data": data,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        async with cls._lock:
            # Store in ring history
            history = cls._history[task_id]
            history.append(payload)
            if len(history) > cls.MAX_HISTORY_PER_TASK:
                cls._history[task_id] = history[-cls.MAX_HISTORY_PER_TASK :]

            # Broadcast to active queues
            queues = list(cls._subscribers.get(task_id, set()))

        for q in queues:
            try:
                q.put_nowait(payload)
            except Exception as e:
                logger.debug("Failed to put event into subscriber queue: %s", e)

    @classmethod
    def get_history(cls, task_id: str) -> list[dict[str, Any]]:
        """Return recorded event history for a task."""
        return list(cls._history.get(task_id, []))

    @classmethod
    def format_sse(cls, event_type: str, data: dict[str, Any]) -> str:
        """Format an event and data payload into standard SSE wire format."""
        return f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"

    @classmethod
    async def subscribe(
        cls,
        task_id: str,
        replay_history: bool = True,
        heartbeat_interval: float = 15.0,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Subscribe to live agent milestone events for a task.

        Yields event dictionaries with `event`, `data`, and `timestamp`.
        """
        q: asyncio.Queue = asyncio.Queue()

        async with cls._lock:
            cls._subscribers[task_id].add(q)
            history_snapshot = list(cls._history.get(task_id, []))

        # Replay recorded history first if requested
        if replay_history:
            for item in history_snapshot:
                yield item
                if item.get("event") in TERMINAL_EVENTS:
                    # History already ended with a terminal event
                    async with cls._lock:
                        cls._subscribers[task_id].discard(q)
                    return

        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=heartbeat_interval)
                    yield event
                    if event.get("event") in TERMINAL_EVENTS:
                        break
                except TimeoutError:
                    # Emit heartbeat keep-alive
                    yield {
                        "event": "ping",
                        "data": {"timestamp": datetime.now(UTC).isoformat()},
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
        finally:
            async with cls._lock:
                cls._subscribers[task_id].discard(q)
                if not cls._subscribers[task_id]:
                    cls._subscribers.pop(task_id, None)

    @classmethod
    async def subscribe_sse(
        cls,
        task_id: str,
        task: AgentTask | None = None,
        heartbeat_interval: float = 15.0,
    ) -> AsyncGenerator[str, None]:
        """Subscribe to agent events and yield SSE-formatted string chunks.

        If task metadata is provided and history is empty, synthesizes
        historical milestones from persisted database actions.
        """
        # If no history in memory yet but task has recorded state, populate history
        if task and not cls._history.get(task_id):
            if task.status == TaskStatus.CANCELLED and not task.actions:
                await cls.publish(
                    task_id,
                    "task_cancelled",
                    {
                        "task_id": task_id,
                        "status": "cancelled",
                        "reason": task.result_summary or "Cancelled",
                    },
                )
            else:
                for idx, a in enumerate(task.actions, 1):
                    await cls.publish(
                        task_id,
                        "action_planned",
                        {
                            "step": idx,
                            "tool_name": a.tool_name,
                            "tool_input": a.tool_input,
                            "risk_level": a.risk_level,
                        },
                    )
                    if a.approval_status == ActionApprovalStatus.PENDING_APPROVAL:
                        await cls.publish(
                            task_id,
                            "awaiting_approval",
                            {
                                "step": idx,
                                "action_id": a.id,
                                "tool_name": a.tool_name,
                                "risk_level": a.risk_level,
                            },
                        )
                    else:
                        await cls.publish(
                            task_id,
                            "step_completed",
                            {
                                "step": idx,
                                "action_id": a.id,
                                "tool_name": a.tool_name,
                                "output": a.tool_output,
                                "latency_ms": a.execution_latency_ms,
                                "status": a.approval_status.value,
                            },
                        )

                if task.status == TaskStatus.COMPLETED:
                    await cls.publish(
                        task_id,
                        "task_finished",
                        {
                            "status": "completed",
                            "result_summary": task.result_summary,
                            "steps_taken": task.steps_taken,
                        },
                    )
                elif task.status == TaskStatus.CANCELLED:
                    await cls.publish(
                        task_id,
                        "task_cancelled",
                        {
                            "task_id": task_id,
                            "status": "cancelled",
                            "reason": task.result_summary or "Task cancelled",
                        },
                    )
                elif task.status == TaskStatus.FAILED:
                    await cls.publish(
                        task_id,
                        "task_failed",
                        {
                            "status": "failed",
                            "error": task.error_message or "Task failed",
                        },
                    )

        async for item in cls.subscribe(
            task_id=task_id,
            replay_history=True,
            heartbeat_interval=heartbeat_interval,
        ):
            yield cls.format_sse(item["event"], item["data"])

    @classmethod
    def clear(cls, task_id: str | None = None) -> None:
        """Clear subscribers and history for a specific task or all tasks (testing helper)."""
        if task_id:
            cls._subscribers.pop(task_id, None)
            cls._history.pop(task_id, None)
        else:
            cls._subscribers.clear()
            cls._history.clear()
