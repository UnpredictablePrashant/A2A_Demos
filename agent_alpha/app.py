import logging

import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from agent_executor import AlphaAgentExecutor


def build_agent_card() -> AgentCard:
    skill = AgentSkill(
        id="alpha_broker",
        name="Alpha Broker",
        description="Receives user input and delegates to Beta over A2A.",
        tags=["broker", "delegation", "a2a"],
        examples=["ask beta what you heard", "delegate this to beta"],
    )

    return AgentCard(
        name="Alpha Agent",
        description="Front agent that talks to Beta using A2A protocol.",
        url="http://127.0.0.1:8101/",
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
        agent_executor=AlphaAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    app = A2AStarletteApplication(agent_card=card, http_handler=request_handler)
    uvicorn.run(app.build(), host="0.0.0.0", port=8101, log_level="info")
