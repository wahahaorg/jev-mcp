# Jev MCP

[中文说明](README.zh-CN.md)

`jev-mcp` turns [browser-use/jev-ultrafast](https://github.com/browser-use/jev-ultrafast) into one local, session-aware MCP server for fast **read-only product research**. Jev selects an action and observed target from a DOM snapshot; this wrapper gives an MCP host the tools and lifecycle it needs to use that loop safely.

## What it is (and is not)

This is one local stdio MCP server, not a replacement browser extension and not four separate MCPs. It owns browser targets created by Jev and exposes four model-facing tools:

| Tool | Use it for | Does not do |
| --- | --- | --- |
| `jev_browse` | Start a public-site search, filtering, or product-detail task | Log in, checkout, pay, upload, or submit an order |
| `jev_status` | Read a session's URL, visible text, supported controls, and latest actions | Take another browser action |
| `jev_extract_products` | Read visible product card fields: name, price, rating, details, URL | Scroll, click, or guarantee site-specific parsing |
| `jev_stop` | Close the Jev-owned Chrome target | Affect ordinary user Chrome tabs |

The upstream Jev agent remains an isolated Git dependency pinned to commit `1231850a0bf1a0c0341fe408ef1668dbbfdfac46`; this repository contains the MCP session layer, output shaping, product extraction, and safety guardrails. This keeps upgrades reviewable and avoids carrying a modified upstream fork.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- A Chrome/Chromium installation supported by `browser-harness`
- An `OPENROUTER_API_KEY` for Jev Decisions (recommended), or a direct `TYPESAFE_API_KEY`
- `TEXT_MODEL_API_KEY` for search/filter text entry; the default example uses OpenRouter

## Setup

```bash
git clone https://github.com/wahahaorg/jev-mcp.git
cd jev-mcp
cp .env.example .env
# Put real keys in .env; never commit it. OpenRouter Decisions is the default path.
uv sync
uv run browser-harness --doctor
```

`browser-harness` may ask Chrome for remote-debugging permission. The server creates its own background Chrome target; it does not take over the currently visible tab.

Run it locally:

```bash
uv run --env-file .env jev-mcp
```

The server uses stdio: stdout is reserved for MCP JSON-RPC. It waits for an MCP host rather than opening a web page itself.

## MCP configuration

Copy the `mcpServers.jev-browser` object in [`.mcp.json`](.mcp.json) into your MCP host configuration. Replace the command's directory with this repository's absolute path if the host does not start processes from the repository root.

Example:

```json
{
  "mcpServers": {
    "jev-browser": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/jev-mcp", "--env-file", ".env", "jev-mcp"]
    }
  }
}
```

Keep credentials in the host environment or `.env`; never place keys in the configuration committed to source control. The included configuration assumes the host starts it from this repository; use the absolute-path version above otherwise.

## Typical flow

1. Call `jev_browse` with a public URL and a narrow goal, for example: “Search wireless headphones, set the price filter below $100, and stop when results are visible.”
2. Keep the returned `session_id`.
3. Call `jev_status` when you need to decide whether the page is ready or why it blocked.
4. Call `jev_extract_products` on a visible result/detail page.
5. Call `jev_stop` when finished.

When `OPENROUTER_API_KEY` is present, the wrapper sends Jev decisions to OpenRouter's alpha Decisions endpoint using `~typesafe/jev-latest`; otherwise it retains the upstream direct TypeSafe client. The agent is deliberately bounded to 30 browser actions per `jev_browse` call and upstream Jev itself has a 60-action run cap. Results are observations, not proof of stock, availability, or final checkout price.

## Safety model

The wrapper rejects transactional goals before a browser opens and blocks observed add-to-cart, purchase, checkout, payment, upload, credential, card, and verification-code controls just before execution. It also refuses password/file controls inherited from upstream's DOM snapshot safeguards. This is a browsing and extraction integration, not a purchasing bot.

Web content is treated as untrusted data. Product extraction is best-effort and returns only currently visible cards; validate important prices, variants, and shipping details on the source page.

## Development and verification

```bash
uv run ruff check .
uv run pytest
npx @modelcontextprotocol/inspector uv run --env-file .env jev-mcp
```

The test suite uses a fake browser/agent, so it does not spend API credits or require Chrome. `evals.xml` contains ten multi-tool evaluation scenarios, including error recovery and safety boundaries. Use the Inspector with real credentials to validate the MCP framing and a public browsing task.

## License

MIT. The upstream Jev dependency is also MIT-licensed; see its repository for its terms and notices.
