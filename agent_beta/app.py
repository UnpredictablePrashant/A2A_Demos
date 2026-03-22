import logging

import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from agent_executor import BetaAgentExecutor


def build_agent_card() -> AgentCard:
    skill = AgentSkill(
        id="beta_echo",
        name="Beta Echo",
        description="Replies with a deterministic echo confirmation.",
        tags=["echo", "demo", "a2a"],
        examples=["hello beta", "alpha asked me to ping you"],
    )

    return AgentCard(
        name="Beta Agent",
        description="Receives A2A calls from Alpha and responds.",
        url="http://127.0.0.1:8102/",
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
        agent_executor=BetaAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    app = A2AStarletteApplication(agent_card=card, http_handler=request_handler)
    uvicorn.run(app.build(), host="0.0.0.0", port=8102, log_level="info")
