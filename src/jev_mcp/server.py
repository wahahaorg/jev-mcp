"""Local stdio MCP server for fast, browsing-only Jev sessions."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .service import JevService

service = JevService()
mcp = FastMCP(
    "Jev Fast Browser",
    instructions=(
        "Use this server for read-only product research: search, filter, inspect results, "
        "and extract visible product data. "
        "It never logs in, uploads, submits orders, or makes payments. Start with jev_browse, retain its session_id, "
        "then use jev_status or jev_extract_products; always finish with jev_stop."
    ),
)


@mcp.tool()
def jev_browse(url: str, goal: str, max_steps: int = 20) -> dict:
    """Start a new browser session and advance a read-only browsing goal.

    Use this for finding, filtering, or opening products on a public website. It executes at most max_steps
    (1–30) before returning a session_id, visible page evidence, and recent actions. Do not use it for login,
    checkout, payment, uploads, or any task that enters personal or financial data.
    """
    return service.browse(url, goal, max_steps)


@mcp.tool()
def jev_status(session_id: str) -> dict:
    """Inspect a live Jev browser session without taking another browser action.

    Use it after jev_browse to reason from the current URL, visible text, supported controls, and recent actions.
    It does not load a page, click a control, scroll, or generate model requests.
    """
    return service.status(session_id)


@mcp.tool()
def jev_stop(session_id: str) -> dict:
    """Close one Jev-owned Chrome target and remove its session.

    Call this when product research is complete or after an unrecoverable block. The session_id becomes invalid
    immediately; this never affects tabs outside the Jev-owned browser target.
    """
    return service.stop(session_id)


@mcp.tool()
def jev_extract_products(session_id: str) -> dict:
    """Extract product name, price, rating, details, and link from currently visible product cards.

    Use this after jev_browse reaches a results or product page. This is best-effort read-only DOM extraction;
    it does not scroll, click, or infer fields that are not visible, so verify important price or stock data.
    """
    return service.extract_products(session_id)


def main() -> None:
    """Run the local MCP server over stdio; stdout remains reserved for MCP JSON-RPC."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
