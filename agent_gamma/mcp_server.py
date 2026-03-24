from fastmcp import FastMCP


mcp = FastMCP(name="Gamma Minimal MCP")


@mcp.tool
def reverse_string(text: str) -> str:
    """Return the input text reversed."""
    return text[::-1]


if __name__ == "__main__":
    mcp.run()
