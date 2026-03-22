import logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message


logger = logging.getLogger(__name__)


class BetaAgentExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        query = context.get_user_input() or ""
        logger.info("BETA_RECEIVED_USER_INPUT=%s", query)

        response_text = (
            "Beta Agent response:\\n"
            f"- I received: {query}\\n"
            "- I can confirm this was an A2A protocol call from Alpha."
        )
        logger.info("BETA_SENDING_RESPONSE_TEXT=%s", response_text)
        await event_queue.enqueue_event(new_agent_text_message(response_text))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise RuntimeError("cancel not supported")
