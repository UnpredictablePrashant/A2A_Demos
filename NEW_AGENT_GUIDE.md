# Adding a New Agent to This A2A Infrastructure

This guide explains how to create a new agent and integrate it into the current ecosystem (runtime + UI detection).

## Fastest Way (Beginner-Friendly)

Use the scaffold script (recommended):

```bash
python3 ecosystem/create_agent.py gamma --port 8103
```

Super-easy interactive mode (prompts for values):

```bash
python3 ecosystem/create_agent.py
```

OpenAI-enabled template:

```bash
python3 ecosystem/create_agent.py gamma --port 8103 --with-openai
```

No-DB template (optional):

```bash
python3 ecosystem/create_agent.py gamma --port 8103 --no-task-tracking
```

This auto-creates:
- `agent_gamma/app.py`
- `agent_gamma/agent_executor.py`
- `agent_gamma/AGENT_SETUP.md`

Then run:

```bash
python3 agent_gamma/app.py
```

## 1) Create Agent Folder (Manual)

Create a new directory in project root using `agent_<name>` convention.

Example:

```bash
mkdir -p agent_gamma
```

Required files:
- `agent_gamma/app.py`
- `agent_gamma/agent_executor.py`

The UI scanner auto-detects folders matching `agent_*`.

## 2) Implement Executor

Your executor should implement `AgentExecutor`:

- `execute(self, context, event_queue)`
- `cancel(self, context, event_queue)`

Minimal skeleton:

```python
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

class GammaAgentExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        text = context.get_user_input() or ""
        await event_queue.enqueue_event(new_agent_text_message(f"Gamma handled: {text}"))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise RuntimeError("cancel not supported")
```

## 2.1 DB Creation + Connection (Important)

If you use task tracking, DB setup should happen in executor initialization:

```python
class GammaAgentExecutor(AgentExecutor):
    def __init__(self) -> None:
        self.db_path = os.environ.get("GAMMA_DB_PATH", os.path.join(os.path.dirname(__file__), "gamma_tasks.db"))
        self._init_db()
```

Inside `_init_db()`:
- `CREATE TABLE IF NOT EXISTS ...` for new environments
- optional migration for existing DB files (`PRAGMA table_info` + `ALTER TABLE`)

Runtime flow:
1. Server starts (`app.py`)
2. Executor is instantiated
3. DB/table are created/migrated
4. Each `execute(...)` call inserts task row
5. Processing updates status/result/timestamps
6. Final response is returned

This is why the DB process is part of agent startup, not a separate manual step.

## 3) Implement `app.py` with Agent Card + Port

Use A2A app bootstrap and expose a unique port.

Important: set explicit `port=<number>` in `uvicorn.run(...)`.
The UI detection endpoint parser reads this port from `app.py`.

Example:

```python
import logging
import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from agent_executor import GammaAgentExecutor


def build_agent_card() -> AgentCard:
    skill = AgentSkill(
        id="gamma_skill",
        name="Gamma Skill",
        description="Example additional agent",
        tags=["gamma", "a2a"],
        examples=["run gamma task"],
    )

    return AgentCard(
        name="Gamma Agent",
        description="Additional agent in ecosystem",
        url="http://127.0.0.1:8103/",
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    card = build_agent_card()

    request_handler = DefaultRequestHandler(
        agent_executor=GammaAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    app = A2AStarletteApplication(agent_card=card, http_handler=request_handler)
    uvicorn.run(app.build(), host="0.0.0.0", port=8103, log_level="info")
```

## 4) Dependency and Env

If your new agent uses OpenAI or shared utilities, keep dependency set aligned with root `requirements.txt`.

For OpenAI-based agents, set:
- `OPENAI_API_KEY`
- `OPENAI_MODEL` (optional)

## 5) Add Runtime Management (Optional but Recommended)

Current UI server (`ecosystem/ui_server.py`) auto-detects all `agent_*` folders and checks detection status by probing each agent card URL.

But it only auto-starts:
- Alpha
- Beta

If you want Gamma auto-started too, add a managed process in `Orchestrator.startup()` similar to Alpha/Beta.

## 6) Connect New Agent into Flow

If Gamma should participate in orchestration (not just standalone):

- Update Alpha executor routing logic to call Gamma (`A2AClient` call flow)
- Define payload contract (`action`, task IDs, etc.)
- Persist additional task metadata if needed in SQLite repositories

If your new agent uses task tracking DB tables, include lifecycle timestamps:
- `created_at` (when task is inserted)
- `updated_at` (last change)
- `completed_at` (when terminal status is reached)
- optional `ready_at` (if using queued/in_progress scheduling)

The scaffold generator now includes `created_at` / `updated_at` / `completed_at` by default.

## 7) Verify

### Basic card verification

```bash
python3 agent_gamma/app.py
curl -s http://127.0.0.1:8103/.well-known/agent-card.json
```

### UI verification

```bash
python3 ecosystem/ui_server.py
```

Open `http://127.0.0.1:8200` and check:
- `Agent Registry Detection` table shows `gamma`
- `detected=yes` when Gamma is running
- `detected=no` when Gamma is stopped

## 8) Common Integration Checklist

- Unique port in `uvicorn.run(...)`
- Card `url` matches actual host/port
- Folder naming is `agent_<name>`
- Agent process is running and reachable
- Payload schema documented if participating in orchestration
- DB init path is configured (`*_DB_PATH`) and table exists
- Terminal states set `completed_at`
- README/doc updates for team visibility

## Extra Easy Mode for Non-Coders

1. Run scaffold command (copy/paste):
   `python3 ecosystem/create_agent.py myagent --port 8103`
2. Start the new agent:
   `python3 agent_myagent/app.py`
3. Start UI:
   `python3 ecosystem/ui_server.py`
4. Open `http://127.0.0.1:8200`:
   - confirm your agent appears in **Agent Registry Detection**
   - click row to inspect details
