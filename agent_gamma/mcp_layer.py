import json
import os
import shlex
import sys

from dataclasses import dataclass
from pathlib import Path
from typing import Any


try:
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport
except Exception:
    Client = None  # type: ignore[assignment]
    StdioTransport = None  # type: ignore[assignment]


@dataclass
class GammaMCPConfig:
    enabled: bool
    command: str
    args: list[str]
    tool_name: str
    tool_args: dict[str, Any]
    pass_user_query: bool
    cwd: str | None


class GammaMCPClient:
    def __init__(self, config: GammaMCPConfig) -> None:
        self.config = config

    @staticmethod
    def _parse_bool(raw: str | None, default: bool) -> bool:
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "y", "on"}

    @staticmethod
    def _get_env_value(env: dict[str, str], primary: str, fallback: str) -> str:
        return env.get(primary, env.get(fallback, "")).strip()

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "GammaMCPClient":
        env_map = dict(env or os.environ)
        enabled = cls._parse_bool(env_map.get("GAMMA_MCP_ENABLED", env_map.get("MCP_ENABLED", "false")), False)
        command = cls._get_env_value(env_map, "GAMMA_MCP_SERVER_COMMAND", "MCP_SERVER_COMMAND") or sys.executable

        raw_args = cls._get_env_value(env_map, "GAMMA_MCP_SERVER_ARGS", "MCP_SERVER_ARGS")
        if raw_args:
            args = shlex.split(raw_args)
        else:
            default_server = Path(__file__).resolve().with_name("mcp_server.py")
            args = [str(default_server)]

        tool_name = cls._get_env_value(env_map, "GAMMA_MCP_TOOL_NAME", "MCP_TOOL_NAME") or "reverse_string"
        raw_tool_args = cls._get_env_value(env_map, "GAMMA_MCP_TOOL_ARGS_JSON", "MCP_TOOL_ARGS_JSON")
        tool_args: dict[str, Any] = {}
        if raw_tool_args:
            try:
                parsed = json.loads(raw_tool_args)
                if isinstance(parsed, dict):
                    tool_args = parsed
            except Exception:
                tool_args = {}

        pass_user_query = cls._parse_bool(
            env_map.get("GAMMA_MCP_PASS_USER_QUERY", env_map.get("MCP_PASS_USER_QUERY", "true")),
            True,
        )

        raw_cwd = cls._get_env_value(env_map, "GAMMA_MCP_CWD", "MCP_CWD")
        cwd = raw_cwd or None

        return cls(
            GammaMCPConfig(
                enabled=enabled,
                command=command,
                args=args,
                tool_name=tool_name,
                tool_args=tool_args,
                pass_user_query=pass_user_query,
                cwd=cwd,
            )
        )

    async def fetch_context(self, user_query: str) -> str:
        if not self.config.enabled:
            return ""

        if not self.config.command:
            return "MCP is enabled but GAMMA_MCP_SERVER_COMMAND is not set."

        if Client is None or StdioTransport is None:
            return "FastMCP is not installed. Install dependency 'fastmcp' to enable MCP calls."

        transport = StdioTransport(command=self.config.command, args=self.config.args, cwd=self.config.cwd)
        client = Client(transport)

        try:
            async with client:
                tool_name = self.config.tool_name
                if not tool_name:
                    tools = await client.list_tools()
                    names = [str(getattr(tool, "name", "")) for tool in tools]
                    names = [name for name in names if name]
                    if not names:
                        return "FastMCP connected, but no tools were exposed by the server."
                    return "Available MCP tools: " + ", ".join(names)

                args = dict(self.config.tool_args)
                if self.config.pass_user_query:
                    args.setdefault("text", user_query)

                result = await client.call_tool(tool_name, args)
                text = getattr(result, "text", None)
                if isinstance(text, str) and text.strip():
                    return text.strip()
                return str(result)
        except Exception as exc:
            return f"MCP call failed: {exc}"
