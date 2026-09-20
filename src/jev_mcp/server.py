"""Local stdio MCP server for fast, browsing-only Jev sessions."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .decisions import relay_decide
from .service import JevService

service = JevService()
mcp = FastMCP(
    "Jev Fast Browser",
    instructions=(
        "Use this server for read-only product research: search, filter, inspect results, "
        "and extract visible product data. "
        "It never logs in, uploads, submits orders, or makes payments. Start with jev_browse, retain its session_id, "
        "then use jev_status or jev_extract_products; always finish with jev_stop. "
        "If you only want Jev as an intermediate decision relay — your own browser tooling (e.g. opencli) drives "
        "the page and Jev only judges which element to act on — use jev_decide ONLY; it never opens a browser, "
        "session, or tab."
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


@mcp.tool()
def jev_decide(
    goal: str,
    elements: list[dict],
    page_url: str = "",
    page_title: str = "",
    page_text: str = "",
    operations: list[str] | None = None,
) -> dict:
    """Pure decision relay: Jev judges which operation and target element to choose next, no browser involved.

    Use this tool ONLY when you want Jev as an intermediate judgment relay: your own browser tooling
    (e.g. opencli, computer-use) drives the page and captures its state; pass the observed elements here and
    Jev returns the next operation (CLICK/TYPE_TEXT/SELECT/DONE/BLOCKED) and target element index.
    Unlike jev_browse, this never opens a browser, session, or tab — no new pages are created.
    `elements` is a list of observed elements, e.g. [{"index": "12", "role": "button", "label": "搜索"}, ...];
    `operations` optionally restricts the choices (default: CLICK, TYPE_TEXT, SELECT).
    """
    try:
        return relay_decide(goal, elements, page_url, page_title, page_text, operations)
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:  # Keep the relay read-only even when the endpoint misbehaves.
        return {"ok": False, "error": f"Relay decision failed: {exc}"}


def main() -> None:
    """Run the local MCP server over stdio; stdout remains reserved for MCP JSON-RPC."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
