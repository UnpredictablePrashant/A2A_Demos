import logging
import os
import sqlite3
import sys
import time

from pathlib import Path
from uuid import uuid4

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message
from openai import AsyncOpenAI

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agent_core.json_utils import parse_json_or_none, to_pretty_json


logger = logging.getLogger(__name__)


class GammaAgentExecutor(AgentExecutor):
    def __init__(self) -> None:
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
        api_key = os.environ.get("OPENAI_API_KEY", "")
        self.client = AsyncOpenAI(api_key=api_key) if api_key else None
        self.task_delay_seconds = float(os.environ.get("GAMMA_TASK_DELAY_SECONDS", "3"))
        self.db_path = os.environ.get("GAMMA_DB_PATH", os.path.join(os.path.dirname(__file__), "gamma_tasks.db"))
        self._init_db()

    def _init_db(self) -> None:
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS gamma_tasks (
                    task_id TEXT PRIMARY KEY,
                    source_agent TEXT NOT NULL,
                    request_text TEXT NOT NULL,
                    user_query TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_text TEXT,
                    error_text TEXT,
                    created_at REAL NOT NULL,
                    ready_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    completed_at REAL
                )
                """
            )
            self._ensure_column(conn, "gamma_tasks", "task_id", "TEXT")
            self._ensure_column(conn, "gamma_tasks", "source_agent", "TEXT")
            self._ensure_column(conn, "gamma_tasks", "request_text", "TEXT")
            self._ensure_column(conn, "gamma_tasks", "user_query", "TEXT")
            self._ensure_column(conn, "gamma_tasks", "ready_at", "REAL")
            self._ensure_column(conn, "gamma_tasks", "completed_at", "REAL")
            conn.commit()

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, column_type: str) -> None:
        cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
        col_names = {str(col[1]) for col in cols}
        if column in col_names:
            return
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")

    def _insert_task(self, source_agent: str, request_text: str, user_query: str) -> tuple[str, str]:
        task_id = uuid4().hex
        status = "queued"
        now = time.time()
        ready_at = now + self.task_delay_seconds
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO gamma_tasks (
                    task_id, source_agent, request_text, user_query, status,
                    result_text, error_text, created_at, ready_at, updated_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    source_agent,
                    request_text,
                    user_query,
                    status,
                    None,
                    None,
                    now,
                    ready_at,
                    now,
                    None,
                ),
            )
            conn.commit()
        return task_id, status

    def _get_task(self, task_id: str) -> dict[str, object] | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT task_id, source_agent, request_text, user_query, status,
                       result_text, error_text, created_at, ready_at, updated_at, completed_at
                FROM gamma_tasks
                WHERE task_id = ?
                """,
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    def _update_task_status(
        self,
        task_id: str,
        status: str,
        result_text: str | None = None,
        error_text: str | None = None,
    ) -> None:
        now = time.time()
        completed_at = now if status in {"completed", "failed"} else None
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE gamma_tasks
                SET status = ?,
                    result_text = COALESCE(?, result_text),
                    error_text = COALESCE(?, error_text),
                    updated_at = ?,
                    completed_at = COALESCE(?, completed_at)
                WHERE task_id = ?
                """,
                (status, result_text, error_text, now, completed_at, task_id),
            )
            conn.commit()

    async def _generate_text(self, user_query: str) -> str:
        if not self.client:
            return "Set OPENAI_API_KEY to enable model responses."
        res = await self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": "You are Gamma Agent."},
                {"role": "user", "content": user_query},
            ],
        )
        return res.output_text or "(empty model response)"

    async def _refresh_and_get_task(self, task_id: str) -> dict[str, object] | None:
        task = self._get_task(task_id)
        if task is None:
            return None

        status = str(task.get("status", "unknown"))
        now = time.time()
        if status in {"completed", "failed"}:
            return task

        if now < float(task.get("ready_at", now)):
            if status == "queued":
                self._update_task_status(task_id, "in_progress")
            return self._get_task(task_id)

        user_query = str(task.get("user_query", ""))
        try:
            result = await self._generate_text(user_query)
            if not self.client:
                self._update_task_status(task_id, "failed", error_text=result)
            else:
                self._update_task_status(task_id, "completed", result_text=result)
        except Exception as exc:
            logger.exception("GAMMA_TASK_COMPLETION_FAILED task_id=%s", task_id)
            self._update_task_status(task_id, "failed", error_text=str(exc))
        return self._get_task(task_id)

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        request_text = context.get_user_input() or ""
        logger.info("GAMMA_RECEIVED_USER_INPUT=%s", request_text)
        logger.info("GAMMA_OPENAI_MODEL=%s", self.model)

        payload = parse_json_or_none(request_text)
        action = (payload or {}).get("action")

        if action == "submit_task":
            user_query = str(payload.get("user_query", ""))
            source_agent = str(payload.get("source_agent", "alpha"))
            task_id, status = self._insert_task(
                source_agent=source_agent,
                request_text=request_text,
                user_query=user_query,
            )
            task = self._get_task(task_id) or {}
            response_payload = {
                "action": "submit_task_result",
                "task_id": task_id,
                "status": status,
                "poll_after_seconds": self.task_delay_seconds,
                "created_at": task.get("created_at"),
                "updated_at": task.get("updated_at"),
                "completed_at": task.get("completed_at"),
            }
        elif action == "get_task_status":
            task_id = str(payload.get("task_id", ""))
            if not task_id:
                response_payload = {
                    "action": "task_status_result",
                    "task_id": "",
                    "status": "invalid_request",
                    "error": "task_id is required",
                }
            else:
                task = await self._refresh_and_get_task(task_id)
                if task is None:
                    response_payload = {
                        "action": "task_status_result",
                        "task_id": task_id,
                        "status": "not_found",
                    }
                else:
                    response_payload = {
                        "action": "task_status_result",
                        "task_id": task_id,
                        "status": task["status"],
                        "created_at": task.get("created_at"),
                        "ready_at": task.get("ready_at"),
                        "updated_at": task.get("updated_at"),
                        "completed_at": task.get("completed_at"),
                    }
                    if task["status"] == "completed":
                        response_payload["result"] = task.get("result_text") or ""
                    if task["status"] == "failed":
                        response_payload["error"] = task.get("error_text") or "Task failed"
        else:
            task_id, status = self._insert_task(
                source_agent="alpha",
                request_text=request_text,
                user_query=request_text,
            )
            task = self._get_task(task_id) or {}
            response_payload = {
                "action": "submit_task_result",
                "task_id": task_id,
                "status": status,
                "poll_after_seconds": self.task_delay_seconds,
                "created_at": task.get("created_at"),
                "updated_at": task.get("updated_at"),
                "completed_at": task.get("completed_at"),
                "note": "Input was treated as a task submission because action was missing.",
            }

        response_text = to_pretty_json(response_payload)
        logger.info("GAMMA_SENDING_RESPONSE_TEXT=%s", response_text)
        await event_queue.enqueue_event(new_agent_text_message(response_text))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise RuntimeError("cancel not supported")
