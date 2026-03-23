# A2A Agent Ecosystem (Planner + Worker + UI)

This project is a runnable Agent2Agent (A2A) ecosystem in Python.

Current default flow:
- **Alpha**: planner/orchestrator agent
- **Beta**: content/story worker agent
- **UI Orchestrator**: web app that starts configured local agents, submits user tasks, tracks sessions, and visualizes interactions.

The system supports more agents through `.env` configuration (not hardcoded to Alpha/Beta).

## 1) What This System Demonstrates

- Asynchronous A2A task lifecycle (`submit_task -> task_id -> poll status -> completed`)
- SQLite-backed task persistence with lifecycle timestamps
- Live browser visualization:
  - event timeline
  - session-based interaction graph
  - dynamic agent activity cards (detected agents only)
  - DB snapshots
- Environment-driven agent registry and optional autostart

## 2) Project Structure

```text
.
├── agent_alpha/
│   ├── app.py
│   ├── agent_executor.py
│   └── alpha_tasks.db               # created at runtime
├── agent_beta/
│   ├── app.py
│   ├── agent_executor.py
│   └── beta_tasks.db                # created at runtime
├── agent_core/
│   ├── a2a_utils.py
│   ├── json_utils.py
│   ├── openai_utils.py
│   └── task_repositories.py
├── ecosystem/
│   ├── create_agent.py              # scaffold new agents
│   ├── run_demo.py                  # optional scripted demo
│   ├── ui_server.py                 # web UI + orchestrator server
│   ├── static/
│   │   ├── index.html
│   │   ├── app.js
│   │   ├── session.html
│   │   ├── session.js
│   │   └── styles.css
│   └── output/
├── NEW_AGENT_GUIDE.md
├── requirements.txt
└── README.md
```

## 3) Requirements

- Python 3.10+
- `pip`
- Optional: OpenAI API key for LLM-powered planning/generation

Install:

```bash
python3 -m pip install -r requirements.txt
```

## 4) Environment Configuration (`.env`)

Core keys:

- `OPENAI_API_KEY`
- `OPENAI_MODEL` (default: `gpt-4.1-mini`)
- `ALPHA_POLL_INTERVAL_SECONDS`
- `ALPHA_MAX_POLL_ATTEMPTS`
- `BETA_TASK_DELAY_SECONDS`
- `ALPHA_DB_PATH`
- `BETA_DB_PATH`
- `ALPHA_AGENT_URL`
- `BETA_AGENT_URL`

### Multi-agent connection keys

You can define additional agents via either key style:

- `AGENT_<NAME>_URL=http://host:port`
- `<NAME>_AGENT_URL=http://host:port`

Optional (for local process autostart from UI server):

- `AGENT_<NAME>_PATH=agent_<name>` or absolute path
- `AGENT_<NAME>_AUTOSTART=true|false`

Equivalent alternate style also works:

- `<NAME>_AGENT_PATH=...`
- `<NAME>_AGENT_AUTOSTART=...`

Example:

```env
ALPHA_AGENT_URL="http://127.0.0.1:8101"
BETA_AGENT_URL="http://127.0.0.1:8102"

AGENT_GAMMA_URL="http://127.0.0.1:8103"
AGENT_GAMMA_PATH="agent_gamma"
AGENT_GAMMA_AUTOSTART=true
```

## 5) Running the System

### Option A: Interactive UI (recommended)

From project root:

```bash
python3 ecosystem/ui_server.py
```

Open:
- `http://127.0.0.1:8200`

What UI does:
- starts configured autostart local agents
- accepts user tasks
- submits to Alpha endpoint
- tracks run sessions
- renders dynamic interaction graph per session
- shows detected agent cards and process states
- shows DB/config snapshots

### Option B: Scripted demo run (optional)

```bash
python3 ecosystem/run_demo.py
```

Use this for scripted logs/artifacts. It is not required for normal UI usage.

## 6) APIs Exposed by `ui_server.py`

- `POST /api/tasks` submit user query
- `GET /api/tasks/{run_id}` run status
- `GET /api/sessions` list sessions
- `GET /api/sessions/{run_id}` session graph + run details
- `GET /api/agents` agent detection/process status
- `GET /api/config` effective config and source
- `GET /api/db` DB snapshots
- `WS /ws/events` live event stream
- `GET /sessions/{run_id}` detailed session page

## 7) A2A Payload Contract (Alpha <-> Beta)

### Submit

```json
{
  "action": "submit_task",
  "source_agent": "alpha",
  "user_query": "...",
  "planner_brief": "..."
}
```

### Submit response

```json
{
  "action": "submit_task_result",
  "task_id": "<uuid>",
  "status": "queued",
  "poll_after_seconds": 3.0,
  "created_at": 1710000000.12,
  "updated_at": 1710000000.12,
  "completed_at": null
}
```

### Poll

```json
{
  "action": "get_task_status",
  "task_id": "<uuid>"
}
```

### Poll response

```json
{
  "action": "task_status_result",
  "task_id": "<uuid>",
  "status": "in_progress|completed|failed|not_found|invalid_request",
  "created_at": 1710000000.12,
  "ready_at": 1710000003.12,
  "updated_at": 1710000001.2,
  "completed_at": null,
  "result": "...",
  "error": "..."
}
```

## 8) Database Lifecycle

### Alpha DB: `alpha_tasks`

Tracks orchestration side:
- `user_query`, `planner_brief`
- `beta_task_id`, `beta_status`, `beta_result`, `beta_last_payload`
- `created_at`, `updated_at`, `completed_at`

### Beta DB: `beta_tasks`

Tracks worker side:
- `task_id`, `source_agent`, `request_text`, `user_query`, `planner_brief`
- `status`, `result_text`, `error_text`
- `created_at`, `ready_at`, `updated_at`, `completed_at`

### Startup flow

For each task-tracking agent:
1. server instantiates executor
2. executor reads DB path env var
3. `_init_db()` creates/migrates tables
4. `execute()` writes/updates rows per lifecycle transitions

## 9) Create a New Agent

Fast scaffold:

```bash
python3 ecosystem/create_agent.py gamma --port 8103
```

OpenAI template:

```bash
python3 ecosystem/create_agent.py gamma --port 8103 --with-openai
```

Interactive beginner mode:

```bash
python3 ecosystem/create_agent.py
```

No DB tracking variant:

```bash
python3 ecosystem/create_agent.py gamma --port 8103 --no-task-tracking
```

See full guide:
- `NEW_AGENT_GUIDE.md`

## 10) Windows Notes

If import path issues appear when launching from `ecosystem/`, run from project root:

```powershell
cd D:\teaching\batch12\xyz
python -m ecosystem.ui_server
```

Alternative:

```powershell
cd D:\teaching\batch12\xyz\ecosystem
$env:PYTHONPATH=".."
python .\ui_server.py
```

## 11) Troubleshooting

- Agent not detected in UI:
  - check URL in `.env`
  - open `http://host:port/.well-known/agent-card.json`
- Agent shown but not running:
  - if local, ensure `AGENT_<NAME>_PATH` is correct and `AGENT_<NAME>_AUTOSTART=true`
- DB columns missing:
  - restart services to trigger repository init/migration
- No model response:
  - verify `OPENAI_API_KEY`

## 12) Important Notes

- `run_demo.py` is optional; UI path is primary.
- Some `a2a-sdk` components may have deprecation warnings (e.g., `A2AClient`), but current implementation remains functional.
- Keep payloads explicit and JSON-based for observability and easier debugging.
