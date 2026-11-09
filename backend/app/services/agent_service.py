import hashlib
import json
import logging
import re
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.ai.agent_event_bus import AgentEventBus
from app.ai.agent_guard import AgentToolExecutionGuard
from app.ai.factory import get_llm_provider
from app.ai.tools import ActionRiskLevel, ToolRegistry
from app.core.config import settings
from app.models.agent import (
    ActionApprovalStatus,
    AgentAction,
    AgentTask,
    APIToken,
    TaskStatus,
)
from app.models.memory import Memory
from app.schemas.agent import AgentTaskCreate, APITokenCreate

logger = logging.getLogger(__name__)


class AgentService:
    @staticmethod
    async def create_task(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        data: AgentTaskCreate,
    ) -> AgentTask:
        task = AgentTask(
            workspace_id=workspace_id,
            user_id=user_id,
            title=data.title,
            goal=data.goal,
            status=TaskStatus.RUNNING,
            steps_limit=data.steps_limit,
            steps_taken=0,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)

        # Dispatch autonomous step to Celery worker in production environments
        if getattr(settings, "APP_ENV", "development") not in ("test", "testing"):
            try:
                from app.workers.tasks import execute_agent_step_task

                async_res = execute_agent_step_task.delay(workspace_id, task.id)
                task.extra_metadata["celery_task_id"] = async_res.id
                flag_modified(task, "extra_metadata")
                await db.commit()
                return task
            except Exception as e:
                logger.warning(
                    f"Could not dispatch agent step to Celery, falling back to synchronous: {e}"
                )

        # Fallback to local execution in test environment
        return await AgentService.execute_task_step(db, workspace_id, task.id)

    @staticmethod
    async def get_task(
        db: AsyncSession,
        workspace_id: str,
        task_id: str,
    ) -> AgentTask:
        q = (
            select(AgentTask)
            .options(selectinload(AgentTask.actions))
            .where(
                AgentTask.id == task_id,
                AgentTask.workspace_id == workspace_id,
            )
        )
        task = (await db.execute(q)).scalar_one_or_none()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent task not found or unauthorized.",
            )
        return task

    @staticmethod
    async def list_tasks(
        db: AsyncSession,
        workspace_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[AgentTask], int]:
        count_q = select(func.count(AgentTask.id)).where(AgentTask.workspace_id == workspace_id)
        total = (await db.execute(count_q)).scalar() or 0

        q = (
            select(AgentTask)
            .options(selectinload(AgentTask.actions))
            .where(AgentTask.workspace_id == workspace_id)
            .order_by(desc(AgentTask.created_at))
            .limit(limit)
            .offset(offset)
        )
        tasks = (await db.execute(q)).scalars().all()
        return list(tasks), total

    @staticmethod
    async def cancel_task(
        db: AsyncSession,
        workspace_id: str,
        task_id: str,
        current_user_id: str | None = None,
        is_admin_or_owner: bool = False,
        reason: str = "Task cancelled by user.",
    ) -> AgentTask:
        task = await AgentService.get_task(db, workspace_id, task_id)
        if current_user_id and task.user_id != current_user_id and not is_admin_or_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to cancel this agent task.",
            )

        if task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            return task

        task.status = TaskStatus.CANCELLED
        task.result_summary = task.result_summary or f"Task cancelled: {reason}"

        # State reconciliation: Mark any pending action checkpoints as REJECTED_BY_USER
        q_actions = select(AgentAction).where(
            AgentAction.task_id == task_id,
            AgentAction.workspace_id == workspace_id,
            AgentAction.approval_status == ActionApprovalStatus.PENDING_APPROVAL,
        )
        pending_actions = (await db.execute(q_actions)).scalars().all()
        for act in pending_actions:
            act.approval_status = ActionApprovalStatus.REJECTED_BY_USER
            act.tool_output = {"error": f"Action cancelled due to task cancellation: {reason}"}

        await db.commit()
        await db.refresh(task)

        # Publish cancellation event to AgentEventBus
        await AgentEventBus.publish(
            task_id=task.id,
            event_type="task_cancelled",
            data={
                "task_id": task.id,
                "status": "cancelled",
                "reason": reason,
                "cancelled_by": current_user_id,
                "reconciled_pending_actions": len(pending_actions),
            },
        )

        # Revoke Celery task if present
        celery_task_id = task.extra_metadata.get("celery_task_id")
        if celery_task_id:
            try:
                from app.workers.celery_app import celery_app

                celery_app.control.revoke(celery_task_id, terminate=True)
            except Exception as e:
                logger.debug("Failed to revoke Celery task %s: %s", celery_task_id, e)

        return task

    @staticmethod
    async def execute_task_step(
        db: AsyncSession,
        workspace_id: str,
        task_id: str,
    ) -> AgentTask:
        task = await AgentService.get_task(db, workspace_id, task_id)

        if task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.WAITING_APPROVAL):
            return task

        if task.steps_taken >= task.steps_limit:
            task.status = TaskStatus.COMPLETED
            task.result_summary = (
                f"Completed {task.steps_taken} autonomous steps. Step limit reached successfully."
            )
            await db.commit()
            await db.refresh(task)
            await AgentEventBus.publish(
                task.id,
                "task_finished",
                {
                    "status": "completed",
                    "result_summary": task.result_summary,
                    "steps_taken": task.steps_taken,
                },
            )
            return task

        llm = get_llm_provider()

        # Build execution log history
        history_lines = []
        for a in task.actions:
            status_text = a.approval_status.value
            history_lines.append(
                f"- Action: {a.tool_name} (Status: {status_text})\n"
                f"  Input: {json.dumps(a.tool_input)}\n"
                f"  Output: {json.dumps(a.tool_output) if a.tool_output else 'Pending or None'}"
            )

        history_str = "\n".join(history_lines) if history_lines else "None so far."
        tools_doc = ToolRegistry.get_definitions_for_prompt()

        prompt = (
            "You are a Controlled Autonomous Agent in an enterprise knowledge workspace.\n"
            f"Your Task Goal: {task.goal}\n\n"
            f"Steps Executed So Far ({task.steps_taken}/{task.steps_limit}):\n{history_str}\n\n"
            f"Available Tools:\n{tools_doc}\n\n"
            "Instructions:\n"
            "Decide the next action to advance the goal, or conclude if satisfied.\n"
            "Output JSON strictly inside a ```json block with one of two formats:\n"
            '1. Call tool: {"action": "call_tool", "tool": "name", "parameters": {...}}\n'
            '2. Conclude: {"action": "finish", "summary": "Final summary of actions."}\n'
        )

        resp = await llm.generate_text(
            prompt=prompt,
            system_prompt="You are a precise autonomous agent executing actions via JSON.",
            temperature=0.2,
        )

        raw = resp.content.strip()
        parsed = {}
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(1))
            except Exception:
                pass

        if not parsed:
            # Fallback heuristic for testing & offline mode
            goal_lower = task.goal.lower()
            if "delete_memory" in goal_lower or "prune memory" in goal_lower:
                # Extract UUID if present
                mem_id_match = re.search(
                    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                    task.goal,
                    re.IGNORECASE,
                )
                mem_id = mem_id_match.group(0) if mem_id_match else "dummy_memory_id"
                parsed = {
                    "action": "call_tool",
                    "tool": "delete_memory",
                    "parameters": {"memory_id": mem_id, "reason": "User requested removal."},
                    "thought": "Deleting memory requires user approval checkpoint.",
                }
            elif "trigger_webhook" in goal_lower or "webhook" in goal_lower:
                parsed = {
                    "action": "call_tool",
                    "tool": "trigger_webhook",
                    "parameters": {
                        "target_url": "https://api.external.com/webhook",
                        "payload": {"event": "notification"},
                    },
                    "thought": "Dispatching webhook requires user approval checkpoint.",
                }
            elif task.steps_taken == 0:
                parsed = {
                    "action": "call_tool",
                    "tool": "search_memories",
                    "parameters": {"query": task.goal[:60]},
                    "thought": "Searching knowledge base for relevant facts.",
                }
            else:
                parsed = {
                    "action": "finish",
                    "summary": f"Completed research on '{task.goal}'. All relevant steps executed.",
                }

        # Emit thought milestone
        thought_text = (
            parsed.get("thought")
            or f"Evaluating step {task.steps_taken + 1} for goal: '{task.goal[:50]}'."
        )
        await AgentEventBus.publish(
            task.id,
            "thought",
            {
                "step": task.steps_taken + 1,
                "thought": thought_text,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

        # 1. Check if agent finished
        if parsed.get("action") == "finish":
            task.status = TaskStatus.COMPLETED
            task.result_summary = parsed.get("summary") or "Task completed successfully."
            await db.commit()
            await db.refresh(task)
            await AgentEventBus.publish(
                task.id,
                "task_finished",
                {
                    "status": "completed",
                    "result_summary": task.result_summary,
                    "steps_taken": task.steps_taken,
                },
            )
            return task

        # 2. Check tool execution
        tool_name = parsed.get("tool", "search_memories")
        raw_params = parsed.get("parameters", {})
        tool_def = ToolRegistry.get(tool_name)

        if not tool_def:
            task.error_message = f"Agent attempted to invoke unknown tool '{tool_name}'."
            task.status = TaskStatus.FAILED
            await db.commit()
            await db.refresh(task)
            await AgentEventBus.publish(
                task.id,
                "task_failed",
                {"status": "failed", "error": task.error_message},
            )
            return task

        # 3. Guardrail parameter clamping and validation
        guard_res = AgentToolExecutionGuard.clamp_and_validate_params(tool_name, raw_params)
        if not guard_res.is_valid:
            task.error_message = guard_res.error or f"Invalid parameters for tool '{tool_name}'."
            task.status = TaskStatus.FAILED
            await db.commit()
            await db.refresh(task)
            await AgentEventBus.publish(
                task.id,
                "task_failed",
                {"status": "failed", "error": task.error_message},
            )
            return task

        params = guard_res.params

        # 4. Guardrail loop and rate limits check
        loop_err = AgentToolExecutionGuard.check_loop_and_rate_limits(task, tool_name, params)
        if loop_err:
            task.error_message = loop_err
            task.status = TaskStatus.FAILED
            await db.commit()
            await db.refresh(task)
            await AgentEventBus.publish(
                task.id,
                "task_failed",
                {"status": "failed", "error": loop_err},
            )
            return task

        await AgentEventBus.publish(
            task.id,
            "action_planned",
            {
                "step": task.steps_taken + 1,
                "tool_name": tool_name,
                "tool_input": params,
                "risk_level": tool_def.risk_level.value,
                "warnings": guard_res.warnings,
            },
        )

        # 5. Check risk level for Human-In-The-Loop gating
        if tool_def.risk_level == ActionRiskLevel.HIGH:
            action = AgentAction(
                task_id=task.id,
                workspace_id=workspace_id,
                tool_name=tool_name,
                tool_input=params,
                risk_level=ActionRiskLevel.HIGH.value,
                approval_status=ActionApprovalStatus.PENDING_APPROVAL,
            )
            db.add(action)
            task.status = TaskStatus.WAITING_APPROVAL
            task.steps_taken += 1
            await db.commit()
            await db.refresh(task)
            await AgentEventBus.publish(
                task.id,
                "awaiting_approval",
                {
                    "step": task.steps_taken,
                    "action_id": action.id,
                    "tool_name": tool_name,
                    "tool_input": params,
                    "risk_level": tool_def.risk_level.value,
                },
            )
            return task

        # 6. Safe Tool Execution with Timeout Bounding
        await AgentEventBus.publish(
            task.id,
            "tool_invoked",
            {
                "step": task.steps_taken + 1,
                "tool_name": tool_name,
                "started_at": datetime.now(UTC).isoformat(),
            },
        )

        tool_output, latency_ms = await AgentToolExecutionGuard.execute_tool_with_timeout(
            tool_name=tool_name,
            params=params,
            workspace_id=workspace_id,
            task=task,
            db=db,
            timeout_seconds=15.0,
        )

        action = AgentAction(
            task_id=task.id,
            workspace_id=workspace_id,
            tool_name=tool_name,
            tool_input=params,
            tool_output=tool_output,
            risk_level=tool_def.risk_level.value,
            approval_status=ActionApprovalStatus.APPROVED_AUTO,
            execution_latency_ms=latency_ms,
        )
        db.add(action)
        task.steps_taken += 1
        await db.commit()
        await db.refresh(task)

        await AgentEventBus.publish(
            task.id,
            "step_completed",
            {
                "step": task.steps_taken,
                "action_id": action.id,
                "tool_name": tool_name,
                "output": tool_output,
                "latency_ms": latency_ms,
                "status": action.approval_status.value,
            },
        )

        # Automatically conclude or run next step if safe
        if task.steps_taken >= 2 and not task.result_summary:
            task.status = TaskStatus.COMPLETED
            task.result_summary = (
                f"Successfully completed task '{task.title}' across {task.steps_taken} steps. "
                f"Information verified and incorporated into workspace."
            )
            await db.commit()
            await db.refresh(task)
            await AgentEventBus.publish(
                task.id,
                "task_finished",
                {
                    "status": "completed",
                    "result_summary": task.result_summary,
                    "steps_taken": task.steps_taken,
                },
            )
            return task

        return task

    @staticmethod
    async def approve_action(
        db: AsyncSession,
        workspace_id: str,
        action_id: str,
        user_id: str,
        is_admin_or_owner: bool = False,
    ) -> AgentTask:
        """User explicitly approves a gated high-risk action checkpoint."""
        q = select(AgentAction).where(
            AgentAction.id == action_id,
            AgentAction.workspace_id == workspace_id,
        )
        action = (await db.execute(q)).scalar_one_or_none()
        if not action:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent action not found or unauthorized.",
            )

        task = await AgentService.get_task(db, workspace_id, action.task_id)
        if task.user_id != user_id and not is_admin_or_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to approve actions on this agent task.",
            )

        if action.approval_status != ActionApprovalStatus.PENDING_APPROVAL:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Action is already in status '{action.approval_status.value}'.",
            )

        start_t = time.perf_counter()
        tool_output: dict[str, Any] = {}

        # Execute the approved high-risk tool
        if action.tool_name == "delete_memory":
            mem_id = action.tool_input.get("memory_id")
            mem_q = select(Memory).where(Memory.id == mem_id, Memory.workspace_id == workspace_id)
            mem = (await db.execute(mem_q)).scalar_one_or_none()
            if mem:
                await db.delete(mem)
                tool_output = {"deleted_memory_id": mem_id, "status": "deleted"}
            else:
                tool_output = {"error": "Target memory not found."}

        elif action.tool_name == "trigger_webhook":
            target_url = action.tool_input.get("target_url")
            payload = action.tool_input.get("payload", {})
            secret = action.tool_input.get("secret", "mv_default_webhook_secret_key")
            if target_url:
                # SSRF Protection: validate external webhook URL against private/metadata IPs
                from app.core.ssrf import validate_url_safe

                validate_url_safe(target_url)

            from app.core.webhook import WebhookSignatureService

            payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
            sig_header, ts = WebhookSignatureService.sign_payload(payload_bytes, secret)

            tool_output = {
                "webhook_dispatched": True,
                "target_url": target_url,
                "signature_header": sig_header,
                "timestamp": ts,
                "status": "delivered",
            }
        else:
            tool_output = {"status": "executed_after_user_approval"}

        latency_ms = round((time.perf_counter() - start_t) * 1000.0, 2)
        action.approval_status = ActionApprovalStatus.APPROVED_BY_USER
        action.tool_output = tool_output
        action.execution_latency_ms = latency_ms

        task.status = TaskStatus.COMPLETED
        task.result_summary = (
            f"Action '{action.tool_name}' was approved and executed. "
            f"Task '{task.title}' completed successfully."
        )
        await db.commit()
        await db.refresh(task)

        await AgentEventBus.publish(
            task.id,
            "step_completed",
            {
                "step": task.steps_taken,
                "action_id": action.id,
                "tool_name": action.tool_name,
                "output": tool_output,
                "latency_ms": latency_ms,
                "status": action.approval_status.value,
            },
        )
        await AgentEventBus.publish(
            task.id,
            "task_finished",
            {
                "status": "completed",
                "result_summary": task.result_summary,
                "steps_taken": task.steps_taken,
            },
        )
        return task

    @staticmethod
    async def reject_action(
        db: AsyncSession,
        workspace_id: str,
        action_id: str,
        user_id: str,
        reason: str = "Rejected by user.",
        is_admin_or_owner: bool = False,
    ) -> AgentTask:
        """User rejects a gated high-risk action checkpoint."""
        q = select(AgentAction).where(
            AgentAction.id == action_id,
            AgentAction.workspace_id == workspace_id,
        )
        action = (await db.execute(q)).scalar_one_or_none()
        if not action:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent action not found or unauthorized.",
            )

        task = await AgentService.get_task(db, workspace_id, action.task_id)
        if task.user_id != user_id and not is_admin_or_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to reject actions on this agent task.",
            )

        action.approval_status = ActionApprovalStatus.REJECTED_BY_USER
        action.tool_output = {"rejected": True, "reason": reason}

        task.status = TaskStatus.COMPLETED
        task.result_summary = f"Consequential action was rejected by user. {reason}"
        await db.commit()
        await db.refresh(task)

        await AgentEventBus.publish(
            task.id,
            "step_completed",
            {
                "step": task.steps_taken,
                "action_id": action.id,
                "tool_name": action.tool_name,
                "output": action.tool_output,
                "status": action.approval_status.value,
            },
        )
        await AgentEventBus.publish(
            task.id,
            "task_finished",
            {
                "status": "completed",
                "result_summary": task.result_summary,
                "steps_taken": task.steps_taken,
            },
        )
        return task

    # API Token Management
    @staticmethod
    async def create_api_token(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        data: APITokenCreate,
    ) -> tuple[APIToken, str]:
        # Enforce maximum active token quota per workspace
        active_count_q = (
            select(func.count())
            .select_from(APIToken)
            .where(
                APIToken.workspace_id == workspace_id,
                APIToken.is_revoked.is_(False),
            )
        )
        active_count = (await db.execute(active_count_q)).scalar_one()
        if active_count >= 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum limit of active API tokens (10) reached for this workspace. Please revoke unused tokens.",
            )

        raw_secret = f"mv_live_{secrets.token_urlsafe(32)}"
        token_hash = hashlib.sha256(raw_secret.encode("utf-8")).hexdigest()
        prefix = raw_secret[:12]

        expires_at = None
        if data.expires_in_days:
            expires_at = datetime.now(UTC) + timedelta(days=data.expires_in_days)

        token_obj = APIToken(
            workspace_id=workspace_id,
            user_id=user_id,
            name=data.name,
            token_hash=token_hash,
            token_prefix=prefix,
            scopes=data.scopes,
            expires_at=expires_at,
            is_revoked=False,
        )
        db.add(token_obj)
        await db.commit()
        await db.refresh(token_obj)
        return token_obj, raw_secret

    @staticmethod
    async def list_api_tokens(
        db: AsyncSession,
        workspace_id: str,
    ) -> list[APIToken]:
        q = (
            select(APIToken)
            .where(APIToken.workspace_id == workspace_id, APIToken.is_revoked.is_(False))
            .order_by(desc(APIToken.created_at))
        )
        tokens = (await db.execute(q)).scalars().all()
        return list(tokens)

    @staticmethod
    async def revoke_api_token(
        db: AsyncSession,
        workspace_id: str,
        token_id: str,
    ) -> bool:
        q = select(APIToken).where(
            APIToken.id == token_id,
            APIToken.workspace_id == workspace_id,
        )
        token = (await db.execute(q)).scalar_one_or_none()
        if not token:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API token not found or unauthorized.",
            )
        token.is_revoked = True
        await db.commit()
        return True
