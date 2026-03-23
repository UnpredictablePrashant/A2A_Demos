import os
import sqlite3
import time

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message
from openai import AsyncOpenAI


class SigmaAgentExecutor(AgentExecutor):
    def __init__(self) -> None:
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
        api_key = os.environ.get("OPENAI_API_KEY", "")
        self.client = AsyncOpenAI(api_key=api_key) if api_key else None
        self.db_path = os.environ.get("SIGMA_DB_PATH", os.path.join(os.path.dirname(__file__), "sigma_tasks.db"))
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sigma_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    input_text TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_text TEXT,
                    error_text TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    completed_at REAL
                )
                """
            )
            conn.commit()

    def _insert_task(self, input_text: str) -> tuple[int, float]:
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO sigma_tasks (input_text, status, result_text, error_text, created_at, updated_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (input_text, "in_progress", None, None, now, now, None),
            )
            conn.commit()
            return int(cur.lastrowid), now

    def _finish_task(self, task_id: int, status: str, result_text: str | None, error_text: str | None) -> tuple[float, float]:
        now = time.time()
        completed_at = now if status in {"completed", "failed"} else None
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE sigma_tasks
                SET status = ?, result_text = ?, error_text = ?, updated_at = ?, completed_at = ?
                WHERE id = ?
                """,
                (status, result_text, error_text, now, completed_at, task_id),
            )
            conn.commit()
        return now, completed_at or now

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_text = context.get_user_input() or ""
        task_id, created_at = self._insert_task(user_text)

        status = "completed"
        error = None

        if not self.client:
            reply = "Set OPENAI_API_KEY to enable model responses."
            status = "failed"
            error = reply
        else:
            try:
                res = await self.client.responses.create(
                    model=self.model,
                    input=[
                        {"role": "system", "content": "You are Sigma Agent."},
                        {"role": "user", "content": user_text},
                    ],
                )
                reply = res.output_text or "(empty model response)"
            except Exception as exc:
                status = "failed"
                error = str(exc)
                reply = f"OpenAI call failed: {exc}"

        updated_at, completed_at = self._finish_task(
            task_id=task_id,
            status=status,
            result_text=reply if status == "completed" else None,
            error_text=error,
        )

        final = (
            f"Sigma Agent response:\n"
            f"- task_id: {task_id}\n"
            f"- status: {status}\n"
            f"- created_at: {created_at}\n"
            f"- updated_at: {updated_at}\n"
            f"- completed_at: {completed_at}\n"
            f"- output:\n{reply}"
        )
        await event_queue.enqueue_event(new_agent_text_message(final))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise RuntimeError("cancel not supported")
