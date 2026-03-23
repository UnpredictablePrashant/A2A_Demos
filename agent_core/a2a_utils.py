import logging

from uuid import uuid4

from a2a.client import A2AClient
from a2a.types import Message, MessageSendParams, Part, Role, SendMessageRequest, TextPart


def _collect_a2a_texts(value: object, out: list[str]) -> None:
    if isinstance(value, dict):
        if value.get("kind") == "text" and isinstance(value.get("text"), str):
            out.append(value["text"])
        for item in value.values():
            _collect_a2a_texts(item, out)
        return

    if isinstance(value, list):
        for item in value:
            _collect_a2a_texts(item, out)


def extract_last_a2a_text(response: object) -> str:
    if not hasattr(response, "model_dump"):
        return ""

    payload = response.model_dump(mode="json", exclude_none=True)
    texts: list[str] = []
    _collect_a2a_texts(payload, texts)
    return texts[-1] if texts else ""


async def send_text_message(client: A2AClient, text: str, logger: logging.Logger, request_log: str, response_log: str) -> str:
    send_params = MessageSendParams(
        message=Message(
            role=Role.user,
            parts=[Part(TextPart(text=text))],
            message_id=uuid4().hex,
        )
    )
    request = SendMessageRequest(id=str(uuid4()), params=send_params)

    logger.info(request_log, request.model_dump_json(indent=2, exclude_none=True))
    response = await client.send_message(request)
    logger.info(response_log, response.model_dump_json(indent=2, exclude_none=True))

    return extract_last_a2a_text(response)
