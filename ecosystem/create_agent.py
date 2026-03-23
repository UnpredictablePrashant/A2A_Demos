import argparse
from pathlib import Path


APP_TEMPLATE = '''import logging
import sys

import uvicorn

from pathlib import Path

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from agent_executor import {class_name}

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agent_core.env_loader import load_env_chain


def build_skills() -> list[AgentSkill]:
    return [
        AgentSkill(
            # id: stable machine-friendly unique identifier for this capability.
            id="{agent_id}_task_execution",
            # name: short human-readable label shown in cards/UIs.
            name="{agent_name} Task Execution",
            # description: what this skill does, expected input shape, and output behavior.
            description=(
                "Primary execution skill for {agent_name}. "
                "Accepts plain text or structured task text, validates input, runs business logic, "
                "and returns final status plus output."
            ),
            # tags: searchable keywords for discovery/routing in multi-agent ecosystems.
            tags=["{agent_id}", "execute", "task", "a2a"],
            # examples: realistic prompts/messages that demonstrate intended usage.
            examples=[
                "execute {agent_id} task: summarize this requirement",
                "run {agent_id} on: generate implementation notes",
            ],
        ),
        AgentSkill(
            id="{agent_id}_task_tracking",
            name="{agent_name} Task Tracking",
            description=(
                "Tracks task lifecycle in SQLite when task tracking template is enabled. "
                "Persists created/updated/completed timestamps, status transitions, and result/error payloads."
            ),
            tags=["{agent_id}", "sqlite", "tracking", "observability"],
            examples=[
                "show latest {agent_id} task status from DB",
                "inspect {agent_id} completed tasks and timestamps",
            ],
        ),
        AgentSkill(
            id="{agent_id}_integration_contract",
            name="{agent_name} Integration Contract",
            description=(
                "Defines how other agents should call this agent through A2A payload conventions "
                "(action names, required fields, and response contract)."
            ),
            tags=["{agent_id}", "integration", "contract", "a2a"],
            examples=[
                "what payload schema should alpha send to {agent_id}",
                "document response fields for {agent_id} task status",
            ],
        ),
    ]


def build_agent_card() -> AgentCard:
    return AgentCard(
        name="{agent_name}",
        description="{agent_name} in A2A ecosystem.",
        url="http://127.0.0.1:{port}/",
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=build_skills(),
    )


if __name__ == "__main__":
    load_env_chain(agent_dir=Path(__file__).resolve().parent, root_dir=ROOT_DIR)
    logging.basicConfig(level=logging.INFO)
    card = build_agent_card()

    request_handler = DefaultRequestHandler(
        agent_executor={class_name}(),
        task_store=InMemoryTaskStore(),
    )

    app = A2AStarletteApplication(agent_card=card, http_handler=request_handler)
    uvicorn.run(app.build(), host="0.0.0.0", port={port}, log_level="info")
'''


EXEC_TEMPLATE_BASIC = '''import os
import sqlite3
import time

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message


class {class_name}(AgentExecutor):
    def __init__(self) -> None:
        self.db_path = os.environ.get("{agent_env_db_key}", os.path.join(os.path.dirname(__file__), "{agent_id}_tasks.db"))
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS {agent_id}_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    input_text TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_text TEXT,
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
                INSERT INTO {agent_id}_tasks (input_text, status, result_text, created_at, updated_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (input_text, "in_progress", None, now, now, None),
            )
            conn.commit()
            return int(cur.lastrowid), now

    def _complete_task(self, task_id: int, result_text: str) -> tuple[float, float]:
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE {agent_id}_tasks
                SET status = ?, result_text = ?, updated_at = ?, completed_at = ?
                WHERE id = ?
                """,
                ("completed", result_text, now, now, task_id),
            )
            conn.commit()
        return now, now

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_text = context.get_user_input() or ""
        task_id, created_at = self._insert_task(user_text)

        reply_text = (
            "{agent_name} response:\\n"
            f"- task_id: {{task_id}}\\n"
            "- status: completed\\n"
            f"- input: {{user_text}}\\n"
            "- note: You can customize this behavior in agent_executor.py"
        )

        updated_at, completed_at = self._complete_task(task_id, reply_text)
        final = (
            f"{{reply_text}}\\n"
            f"- created_at: {{created_at}}\\n"
            f"- updated_at: {{updated_at}}\\n"
            f"- completed_at: {{completed_at}}"
        )
        await event_queue.enqueue_event(new_agent_text_message(final))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise RuntimeError("cancel not supported")
'''


EXEC_TEMPLATE_OPENAI = '''import os
import sqlite3
import time

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message
from openai import AsyncOpenAI


class {class_name}(AgentExecutor):
    def __init__(self) -> None:
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
        api_key = os.environ.get("OPENAI_API_KEY", "")
        self.client = AsyncOpenAI(api_key=api_key) if api_key else None
        self.db_path = os.environ.get("{agent_env_db_key}", os.path.join(os.path.dirname(__file__), "{agent_id}_tasks.db"))
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS {agent_id}_tasks (
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
                INSERT INTO {agent_id}_tasks (input_text, status, result_text, error_text, created_at, updated_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (input_text, "in_progress", None, None, now, now, None),
            )
            conn.commit()
            return int(cur.lastrowid), now

    def _finish_task(self, task_id: int, status: str, result_text: str | None, error_text: str | None) -> tuple[float, float]:
        now = time.time()
        completed_at = now if status in {{"completed", "failed"}} else None
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE {agent_id}_tasks
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
                        {{"role": "system", "content": "You are {agent_name}."}},
                        {{"role": "user", "content": user_text}},
                    ],
                )
                reply = res.output_text or "(empty model response)"
            except Exception as exc:
                status = "failed"
                error = str(exc)
                reply = f"OpenAI call failed: {{exc}}"

        updated_at, completed_at = self._finish_task(
            task_id=task_id,
            status=status,
            result_text=reply if status == "completed" else None,
            error_text=error,
        )

        final = (
            f"{agent_name} response:\\n"
            f"- task_id: {{task_id}}\\n"
            f"- status: {{status}}\\n"
            f"- created_at: {{created_at}}\\n"
            f"- updated_at: {{updated_at}}\\n"
            f"- completed_at: {{completed_at}}\\n"
            f"- output:\\n{{reply}}"
        )
        await event_queue.enqueue_event(new_agent_text_message(final))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise RuntimeError("cancel not supported")
'''


EXEC_TEMPLATE_BASIC_NO_TRACK = '''from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message


class {class_name}(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_text = context.get_user_input() or ""
        reply = (
            "{agent_name} response:\\n"
            f"- I received: {{user_text}}\\n"
            "- You can customize this in agent_executor.py"
        )
        await event_queue.enqueue_event(new_agent_text_message(reply))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise RuntimeError("cancel not supported")
'''


EXEC_TEMPLATE_OPENAI_NO_TRACK = '''import os

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message
from openai import AsyncOpenAI


class {class_name}(AgentExecutor):
    def __init__(self) -> None:
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
        api_key = os.environ.get("OPENAI_API_KEY", "")
        self.client = AsyncOpenAI(api_key=api_key) if api_key else None

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_text = context.get_user_input() or ""

        if not self.client:
            reply = "Set OPENAI_API_KEY to enable model responses."
        else:
            try:
                res = await self.client.responses.create(
                    model=self.model,
                    input=[
                        {{"role": "system", "content": "You are {agent_name}."}},
                        {{"role": "user", "content": user_text}},
                    ],
                )
                reply = res.output_text or "(empty model response)"
            except Exception as exc:
                reply = f"OpenAI call failed: {{exc}}"

        await event_queue.enqueue_event(new_agent_text_message(reply))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise RuntimeError("cancel not supported")
'''


SETUP_TEMPLATE = '''# {agent_name}

This agent was scaffolded with `ecosystem/create_agent.py`.

## Run

```bash
python3 app.py
```

## Endpoints

- Card: `http://127.0.0.1:{port}/.well-known/agent-card.json`

## Optional Environment Variables

- `OPENAI_API_KEY` (needed when created with `--with-openai`)
- `OPENAI_MODEL` (default: `gpt-4.1-mini`)
- `{agent_env_url_key}` (agent card base URL used by the ecosystem UI)
- `{agent_env_url_key_alt}` (alternate URL key format; either key works)
- `{agent_env_db_key}` (SQLite path for this agent's task DB)

## Env Resolution Order

At startup, this agent loads env files in this order:
1. `agent_{agent_id}/.env` (highest file priority)
2. project root `.env` (fallback for missing keys)
3. already-exported process env vars (highest overall priority)

Use this to keep agent-specific overrides local while still inheriting shared root config.

## Skill Blueprint (What To Define Clearly)

When adding or editing skills in `app.py`, define each skill with:
- `id`: stable machine-friendly identifier (`{agent_id}_...`)
- `name`: clear operator-facing name
- `description`: task scope, expected input shape, and output contract
- `tags`: capability keywords (`a2a`, domain, execution type, storage)
- `examples`: realistic prompts/calls that match your integration flow

Recommended skill split:
1. Execution skill:
   - what the agent does end-to-end
   - required/optional input fields
   - terminal output format
2. Tracking/observability skill:
   - task states (`queued`, `in_progress`, `completed`, `failed`)
   - timestamps and DB fields exposed
3. Integration contract skill:
   - expected `action` values
   - response payload keys and error behavior

Do not keep skill descriptions generic; document exact contracts used by your executor.

## AgentSkill Parameter Reference

`AgentSkill(...)` fields used in this project:
- `id`:
  - unique stable identifier for the skill
  - should not change frequently, because clients may depend on it
  - recommended format: `{agent_id}_<capability>`
- `name`:
  - short human-readable title
  - shown in agent cards and UI lists
- `description`:
  - explain exact behavior, expected input, and output/result contract
  - write this as an operator-facing mini spec, not a generic sentence
- `tags`:
  - searchable labels for discovery/routing
  - include domain (`finance`, `story`), behavior (`execute`, `tracking`) and protocol (`a2a`) where relevant
- `examples`:
  - concrete sample requests matching real usage
  - make examples realistic so users know how to call the skill correctly

Practical rule:
- if a new engineer reads only `id/name/description/tags/examples`, they should know when and how to use the skill.

## Server -> DB Flow (How It Works)

When you run `python3 app.py`, the sequence is:

1. `app.py` builds the A2A server and creates `{class_name}()`.
2. In `agent_executor.py`, `__init__` sets `self.db_path` from `{agent_env_db_key}`.
3. `__init__` calls `_init_db()`.
4. `_init_db()` runs `CREATE TABLE IF NOT EXISTS {agent_id}_tasks (...)`.
5. On each incoming request, `execute(...)`:
   - writes a new DB row (`_insert_task`) with `created_at`/`updated_at`
   - performs processing (LLM or business logic)
   - updates row status + `completed_at` (`_complete_task` or `_finish_task`)
   - returns response to caller

This means DB file/table are auto-created the first time the executor starts.

## Current Table

Default table name: `{agent_id}_tasks`

Typical columns:
- `id` primary key
- `input_text`
- `status`
- `result_text` (and `error_text` for OpenAI template)
- `created_at`, `updated_at`, `completed_at`

## Verify DB Quickly

```bash
python3 app.py
python3 - <<'PY'
import sqlite3
conn = sqlite3.connect('{agent_id}_tasks.db')
print(conn.execute("PRAGMA table_info({agent_id}_tasks)").fetchall())
conn.close()
PY
```

If you set `{agent_env_db_key}` in `.env`, check that custom path instead.

## How To Modify Safely

1. Add new columns:
   - update `_init_db()` DDL for fresh DBs
   - for existing DBs, add a migration step (check `PRAGMA table_info`, then `ALTER TABLE`)
2. Add new statuses:
   - update status transitions in `execute(...)`
   - set `completed_at` only for terminal statuses (`completed`, `failed`)
3. Add domain payload fields:
   - store raw payload JSON in a new `payload_json` column for debugging
4. Keep writes atomic:
   - use `with sqlite3.connect(...) as conn:` around each insert/update block

## Example: Add `payload_json`

In `_init_db()`:

```sql
payload_json TEXT
```

In insert:

```python
conn.execute(
    "INSERT INTO {agent_id}_tasks (input_text, status, payload_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
    (input_text, "in_progress", raw_json, now, now),
)
```

## Recommended Next Upgrade

If you want production-grade structure, move DB logic into:
- `agent_{agent_id}/task_repository.py` (all SQL only)
- `agent_executor.py` (business logic only)

This keeps agent behavior easier to evolve and test.
'''


def _prompt_if_missing(value: str | None, label: str, default: str) -> str:
    if value:
        return value
    raw = input(f"{label} [{default}]: ").strip()
    return raw or default


def _prompt_bool_if_none(value: bool | None, label: str, default: bool) -> bool:
    if value is not None:
        return value
    hint = "Y/n" if default else "y/N"
    raw = input(f"{label} ({hint}): ").strip().lower()
    if not raw:
        return default
    return raw in {"y", "yes"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a new A2A agent scaffold.")
    parser.add_argument("name", nargs="?", help="Agent name, e.g. gamma")
    parser.add_argument("--port", type=int, help="Port for the agent app (default: 8103)")
    parser.add_argument(
        "--with-openai",
        action="store_true",
        help="Create executor template that calls OpenAI",
    )
    parser.add_argument(
        "--no-task-tracking",
        action="store_true",
        help="Disable SQLite task tracking template",
    )
    args = parser.parse_args()

    name = _prompt_if_missing(args.name, "Agent name", "gamma")
    port_text = _prompt_if_missing(str(args.port) if args.port is not None else None, "Port", "8103")
    try:
        port = int(port_text)
    except ValueError as exc:
        raise SystemExit(f"Invalid port: {port_text}") from exc

    with_openai = args.with_openai
    if not args.with_openai and args.name is None:
        with_openai = _prompt_bool_if_none(None, "Use OpenAI template", False)

    task_tracking = not args.no_task_tracking

    agent_id = name.strip().lower().replace(" ", "_")
    folder = Path(f"agent_{agent_id}")
    if folder.exists():
        raise SystemExit(f"Folder already exists: {folder}")

    class_name = "".join(part.capitalize() for part in agent_id.split("_")) + "AgentExecutor"
    agent_name = " ".join(part.capitalize() for part in agent_id.split("_")) + " Agent"
    agent_env_db_key = f"{agent_id.upper()}_DB_PATH"
    agent_env_url_key = f"AGENT_{agent_id.upper()}_URL"
    agent_env_url_key_alt = f"{agent_id.upper()}_AGENT_URL"

    folder.mkdir(parents=True, exist_ok=False)

    app_py = APP_TEMPLATE.format(
        class_name=class_name,
        agent_id=agent_id,
        agent_name=agent_name,
        port=port,
    )

    if task_tracking and with_openai:
        exec_template = EXEC_TEMPLATE_OPENAI
    elif task_tracking and not with_openai:
        exec_template = EXEC_TEMPLATE_BASIC
    elif not task_tracking and with_openai:
        exec_template = EXEC_TEMPLATE_OPENAI_NO_TRACK
    else:
        exec_template = EXEC_TEMPLATE_BASIC_NO_TRACK

    exec_py = exec_template.format(
        class_name=class_name,
        agent_name=agent_name,
        agent_id=agent_id,
        agent_env_db_key=agent_env_db_key,
    )

    setup_md = SETUP_TEMPLATE.format(
        agent_name=agent_name,
        port=port,
        agent_env_db_key=agent_env_db_key,
        agent_env_url_key=agent_env_url_key,
        agent_env_url_key_alt=agent_env_url_key_alt,
        class_name=class_name,
        agent_id=agent_id,
    )

    (folder / "app.py").write_text(app_py, encoding="utf-8")
    (folder / "agent_executor.py").write_text(exec_py, encoding="utf-8")
    (folder / "AGENT_SETUP.md").write_text(setup_md, encoding="utf-8")

    print(f"Created {folder}/app.py")
    print(f"Created {folder}/agent_executor.py")
    print(f"Created {folder}/AGENT_SETUP.md")
    print("\nNext steps:")
    print(f"1) Run: python3 {folder}/app.py")
    print(f"2) Check card: curl -s http://127.0.0.1:{port}/.well-known/agent-card.json")
    print("3) Run UI: python3 ecosystem/ui_server.py")
    print("4) Open http://127.0.0.1:8200 and verify Agent Registry Detection")
    print("5) Add agent URL in .env (either key works):")
    print(f"   - {agent_env_url_key}=http://127.0.0.1:{port}")
    print(f"   - {agent_env_url_key_alt}=http://127.0.0.1:{port}")
    if task_tracking:
        print(f"6) Optional: set {agent_env_db_key}=<path> in .env")


if __name__ == "__main__":
    main()
