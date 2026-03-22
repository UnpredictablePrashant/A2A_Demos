import json
import logging
import os

from uuid import uuid4

import httpx

from a2a.client import A2ACardResolver, A2AClient
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import Message, MessageSendParams, Part, Role, SendMessageRequest, TextPart
from a2a.utils import new_agent_text_message


logger = logging.getLogger(__name__)


def _collect_texts(value: object, out: list[str]) -> None:
    if isinstance(value, dict):
        if value.get("kind") == "text" and isinstance(value.get("text"), str):
            out.append(value["text"])
        for item in value.values():
            _collect_texts(item, out)
        return

    if isinstance(value, list):
        for item in value:
            _collect_texts(item, out)


def _extract_last_text(response: object) -> str:
    if not hasattr(response, "model_dump"):
        return ""

    payload = response.model_dump(mode="json", exclude_none=True)
    texts: list[str] = []
    _collect_texts(payload, texts)
    return texts[-1] if texts else ""


class AlphaAgentExecutor(AgentExecutor):
    def __init__(self) -> None:
        self.beta_url = os.environ.get("BETA_AGENT_URL", "http://127.0.0.1:8102")

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_query = context.get_user_input() or ""
        logger.info("ALPHA_RECEIVED_USER_INPUT=%s", user_query)

        async with httpx.AsyncClient(timeout=30.0) as httpx_client:
            resolver = A2ACardResolver(httpx_client=httpx_client, base_url=self.beta_url)
            beta_card = await resolver.get_agent_card()
            logger.info(
                "ALPHA_RESOLVED_BETA_AGENT_CARD=%s",
                beta_card.model_dump_json(indent=2, exclude_none=True),
            )

            client = A2AClient(httpx_client=httpx_client, agent_card=beta_card)
            send_params = MessageSendParams(
                message=Message(
                    role=Role.user,
                    parts=[Part(TextPart(text=f"Alpha forwarding: {user_query}"))],
                    message_id=uuid4().hex,
                )
            )
            request = SendMessageRequest(id=str(uuid4()), params=send_params)

            logger.info(
                "ALPHA_TO_BETA_SEND_MESSAGE_REQUEST=%s",
                request.model_dump_json(indent=2, exclude_none=True),
            )

            beta_response = await client.send_message(request)
            logger.info(
                "BETA_TO_ALPHA_SEND_MESSAGE_RESPONSE=%s",
                beta_response.model_dump_json(indent=2, exclude_none=True),
            )

            beta_text = _extract_last_text(beta_response)
            if not beta_text:
                beta_text = json.dumps(
                    beta_response.model_dump(mode="json", exclude_none=True), indent=2
                )

        final_text = (
            "Alpha Agent response:\n"
            f"- Your input: {user_query}\n"
            f"- Beta replied: {beta_text}"
        )
        logger.info("ALPHA_FINAL_RESPONSE_TEXT=%s", final_text)
        await event_queue.enqueue_event(new_agent_text_message(final_text))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise RuntimeError("cancel not supported")
