# A2A Two-Agent Ecosystem Demo (Alpha <-> Beta)

This project is a complete, runnable **Agent2Agent (A2A)** example using the official Python **`a2a-sdk`**.

It creates:
- `agent_alpha/`: receives a user message, resolves Beta's agent card, then calls Beta via A2A `message/send`.
- `agent_beta/`: receives Alpha's A2A request and replies.
- `ecosystem/`: starts both agents, runs a full end-to-end call, and captures complete logs and agent cards.

## Project Structure

```text
.
├── agent_alpha/
│   ├── app.py
│   └── agent_executor.py
├── agent_beta/
│   ├── app.py
│   └── agent_executor.py
├── ecosystem/
│   ├── run_demo.py
│   └── output/
│       ├── full_run.log
│       └── cards/
│           ├── alpha_agent_card.json
│           └── beta_agent_card.json
├── requirements.txt
└── README.md
```

## Prerequisites

- Python 3.10+
- Network access to install dependencies

## Install

```bash
python3 -m pip install --break-system-packages -r requirements.txt
```

Note: On this machine, `venv` creation was unavailable (`python3-venv` missing), so `--break-system-packages` was used.

## Run Full Ecosystem Demo

```bash
python3 ecosystem/run_demo.py
```

This single command will:
1. Start `Beta Agent` on `http://127.0.0.1:8102`
2. Start `Alpha Agent` on `http://127.0.0.1:8101`
3. Resolve and log both agent cards
4. Send a user request to Alpha (`message/send`)
5. Alpha calls Beta using A2A (`message/send`)
6. Capture all logs and outputs
7. Save artifacts to `ecosystem/output/`

## Agent Cards

Generated cards are saved here:
- `ecosystem/output/cards/alpha_agent_card.json`
- `ecosystem/output/cards/beta_agent_card.json`

You can also fetch manually while agents are running:

```bash
curl -s http://127.0.0.1:8101/.well-known/agent-card.json
curl -s http://127.0.0.1:8102/.well-known/agent-card.json
```

## Complete Call Logs

Full logs are saved in:
- `ecosystem/output/full_run.log`

The log includes:
- server startup and shutdown for both agents
- card discovery calls
- user -> alpha JSON-RPC request
- alpha -> beta JSON-RPC request
- beta -> alpha JSON-RPC response
- alpha -> user final response
- executor-level logs from both agents

## Example Log Highlights

From `ecosystem/output/full_run.log`:

```text
USER_TO_ALPHA_SEND_MESSAGE_REQUEST={
  "id": "...",
  "jsonrpc": "2.0",
  "method": "message/send",
  "params": {
    "message": {
      "kind": "message",
      "messageId": "...",
      "parts": [{"kind": "text", "text": "Please ask Beta what you received from me."}],
      "role": "user"
    }
  }
}
```

```text
[alpha] INFO:agent_executor:ALPHA_TO_BETA_SEND_MESSAGE_REQUEST={
  "id": "...",
  "jsonrpc": "2.0",
  "method": "message/send",
  "params": {
    "message": {
      "kind": "message",
      "parts": [{"kind": "text", "text": "Alpha forwarding: Please ask Beta what you received from me."}],
      "role": "user"
    }
  }
}
```

```text
[alpha] INFO:agent_executor:BETA_TO_ALPHA_SEND_MESSAGE_RESPONSE={
  "id": "...",
  "jsonrpc": "2.0",
  "result": {
    "kind": "message",
    "parts": [
      {
        "kind": "text",
        "text": "Beta Agent response:\\n- I received: Alpha forwarding: Please ask Beta what you received from me.\\n- I can confirm this was an A2A protocol call from Alpha."
      }
    ],
    "role": "agent"
  }
}
```

```text
ALPHA_TO_USER_SEND_MESSAGE_RESPONSE={
  "id": "...",
  "jsonrpc": "2.0",
  "result": {
    "kind": "message",
    "parts": [
      {
        "kind": "text",
        "text": "Alpha Agent response:\n- Your input: Please ask Beta what you received from me.\n- Beta replied: ..."
      }
    ],
    "role": "agent"
  }
}
```

## How It Works

- `agent_beta/agent_executor.py`
  - Accepts text input from A2A request context.
  - Returns deterministic text response via `new_agent_text_message`.

- `agent_alpha/agent_executor.py`
  - Accepts user text input.
  - Uses `A2ACardResolver` to fetch Beta card.
  - Uses `A2AClient` + `SendMessageRequest` to call Beta.
  - Logs full outbound request and inbound response JSON.
  - Sends a final composed response back to the original caller.

- `ecosystem/run_demo.py`
  - Launches both agents in separate processes.
  - Waits for `/.well-known/agent-card.json` on each.
  - Dumps cards to files.
  - Executes one complete user -> alpha -> beta -> alpha -> user run.
  - Writes all logs to `ecosystem/output/full_run.log`.

## Ports

- Alpha: `8101`
- Beta: `8102`

If you need different ports, update `agent_alpha/app.py`, `agent_beta/app.py`, and constants in `ecosystem/run_demo.py`.

## Notes

- The current SDK emits a deprecation warning for `A2AClient` in favor of `ClientFactory`.
- This demo intentionally keeps implementation simple and explicit for learning and visibility of raw protocol flow.
