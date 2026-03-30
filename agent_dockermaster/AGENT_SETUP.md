# Dockermaster Agent

This agent was scaffolded with `ecosystem/create_agent.py`.

## Run

```bash
python3 app.py
```

## Endpoints

- Card: `http://127.0.0.1:8104/.well-known/agent-card.json`

## Optional Environment Variables

- `OPENAI_API_KEY` (needed when created with `--with-openai`)
- `OPENAI_MODEL` (default: `gpt-4.1-mini`)
- `AGENT_DOCKERMASTER_URL` (agent card base URL used by the ecosystem UI)
- `DOCKERMASTER_AGENT_URL` (alternate URL key format; either key works)
- `DOCKERMASTER_DB_PATH` (SQLite path for this agent's task DB)

## Env Resolution Order

At startup, this agent loads env files in this order:
1. `agent_dockermaster/.env` (highest file priority)
2. project root `.env` (fallback for missing keys)
3. already-exported process env vars (highest overall priority)

Use this to keep agent-specific overrides local while still inheriting shared root config.

## Skill Blueprint (What To Define Clearly)

When adding or editing skills in `app.py`, define each skill with:
- `id`: stable machine-friendly identifier (`dockermaster_...`)
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
  - recommended format: `dockermaster_<capability>`
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

1. `app.py` builds the A2A server and creates `DockermasterAgentExecutor()`.
2. In `agent_executor.py`, `__init__` sets `self.db_path` from `DOCKERMASTER_DB_PATH`.
3. `__init__` calls `_init_db()`.
4. `_init_db()` runs `CREATE TABLE IF NOT EXISTS dockermaster_tasks (...)`.
5. On each incoming request, `execute(...)`:
   - writes a new DB row (`_insert_task`) with `created_at`/`updated_at`
   - performs processing (LLM or business logic)
   - updates row status + `completed_at` (`_complete_task` or `_finish_task`)
   - returns response to caller

This means DB file/table are auto-created the first time the executor starts.

## Current Table

Default table name: `dockermaster_tasks`

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
conn = sqlite3.connect('dockermaster_tasks.db')
print(conn.execute("PRAGMA table_info(dockermaster_tasks)").fetchall())
conn.close()
PY
```

If you set `DOCKERMASTER_DB_PATH` in `.env`, check that custom path instead.

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
    "INSERT INTO dockermaster_tasks (input_text, status, payload_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
    (input_text, "in_progress", raw_json, now, now),
)
```

## Recommended Next Upgrade

If you want production-grade structure, move DB logic into:
- `agent_dockermaster/task_repository.py` (all SQL only)
- `agent_executor.py` (business logic only)

This keeps agent behavior easier to evolve and test.
