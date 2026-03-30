import logging
import sys

import uvicorn

from pathlib import Path

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from agent_executor import DockermasterAgentExecutor

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agent_core.env_loader import load_env_chain


def build_skills() -> list[AgentSkill]:
    return [
        AgentSkill(
            # id: stable machine-friendly unique identifier for this capability.
            id="dockermaster_task_execution",
            # name: short human-readable label shown in cards/UIs.
            name="Dockermaster Agent Task Execution",
            # description: what this skill does, expected input shape, and output behavior.
            description=(
                "Primary execution skill for Dockermaster Agent. "
                "Accepts plain text or structured task text, validates input, runs business logic, "
                "and returns final status plus output."
            ),
            # tags: searchable keywords for discovery/routing in multi-agent ecosystems.
            tags=["dockermaster", "execute", "task", "a2a"],
            # examples: realistic prompts/messages that demonstrate intended usage.
            examples=[
                "execute dockermaster task: summarize this requirement",
                "run dockermaster on: generate implementation notes",
            ],
        ),
        AgentSkill(
            id="dockermaster_task_tracking",
            name="Docker image building",
            description=(
                "Tracks task lifecycle in SQLite when task tracking template is enabled. "
                "Persists created/updated/completed timestamps, status transitions, and result/error payloads."
            ),
            tags=["dockermaster", "sqlite", "tracking", "observability"],
            examples=[
                "show latest dockermaster task status from DB",
                "inspect dockermaster completed tasks and timestamps",
            ],
        ),
        AgentSkill(
            id="dockermaster_integration_contract",
            name="Dockermaster Agent Integration Contract",
            description=(
                "Defines how other agents should call this agent through A2A payload conventions "
                "(action names, required fields, and response contract)."
            ),
            tags=["dockermaster", "integration", "contract", "a2a"],
            examples=[
                "what payload schema should alpha send to dockermaster",
                "document response fields for dockermaster task status",
            ],
        ),
    ]


def build_agent_card() -> AgentCard:
    return AgentCard(
        name="Dockermaster Agent",
        description="Dockermaster Agent in A2A ecosystem.",
        url="http://127.0.0.1:8104/",
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
        agent_executor=DockermasterAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    app = A2AStarletteApplication(agent_card=card, http_handler=request_handler)
    uvicorn.run(app.build(), host="0.0.0.0", port=8104, log_level="info")
