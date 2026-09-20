from __future__ import annotations

from typing import Any

from jev_mcp.service import JevService


class FakeBrowser:
    def __init__(self, extraction: dict[str, Any] | None = None) -> None:
        self.extraction = extraction or {"products": [], "extraction_note": "No visible cards."}
        self.closed = False

    def act(self, action: dict[str, Any], page: dict[str, Any], text: str | None = None) -> dict[str, str]:
        return {"executed": str(action["id"])}

    def evaluate(self, expression: str) -> dict[str, Any]:
        return self.extraction

    def close(self) -> None:
        self.closed = True


class FakeAgent:
    def __init__(self, url: str, goal: str, *, action: dict[str, Any] | None = None) -> None:
        self.browser = FakeBrowser(
            {
                "products": [
                    {"name": "Demo Headphones", "price": "$99", "rating": "4.7 out of 5", "details": "Demo", "url": url}
                ],
                "extraction_note": "Fixture.",
            }
        )
        self.action = action
        self.state: dict[str, Any] = {
            "status": "ready",
            "goal": goal,
            "elapsed_ms": 0,
            "history": [],
            "page": {
                "url": url,
                "title": "Demo shop",
                "text": "Demo Headphones $99 4.7 out of 5",
                "scroll": {"y": 0, "height": 1000},
                "actions": [],
            },
        }

    def command(self, name: str) -> dict[str, Any]:
        assert name == "tick"
        if self.action:
            self.browser.act(self.action, self.state["page"])
        self.state["history"].append({"action": "Open Demo Headphones", "kind": "click", "page_changed": True})
        self.state["status"] = "done"
        self.state["elapsed_ms"] = 42
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        return {
            **self.state,
            "elements": [{"index": "1", "role": "link", "label": "Demo Headphones", "operations": ["CLICK"]}],
        }

    def close(self) -> None:
        self.browser.close()


def test_browse_reports_a_session_and_compact_state() -> None:
    service = JevService(FakeAgent)

    result = service.browse("https://shop.example", "Find wireless headphones", max_steps=1)

    assert result["ok"] is True
    assert result["created"] is True
    assert result["status"] == "done"
    assert result["page"]["title"] == "Demo shop"
    assert result["visible_elements"][0]["label"] == "Demo Headphones"
    assert service.status(result["session_id"])["ok"] is True


def test_browse_rejects_transactional_goal_before_opening_browser() -> None:
    service = JevService(FakeAgent)

    result = service.browse("https://shop.example", "Buy now and pay for the headphones")

    assert result["ok"] is False
    assert "browsing-only" in result["error"]


def test_observed_purchase_button_is_blocked_before_clicking() -> None:
    action = {"id": "e1", "kind": "click", "label": "Add to cart"}
    service = JevService(lambda url, goal: FakeAgent(url, goal, action=action))

    result = service.browse("https://shop.example", "Find wireless headphones", max_steps=1)

    assert result["ok"] is True
    assert result["status"] == "blocked"
    assert "Blocked sensitive browser control" in result["last_error"]


def test_extract_products_is_read_only_and_structured() -> None:
    service = JevService(FakeAgent)
    session_id = service.browse("https://shop.example", "Find wireless headphones")["session_id"]

    result = service.extract_products(session_id)

    assert result["ok"] is True
    assert result["products"][0]["name"] == "Demo Headphones"
    assert result["products"][0]["price"] == "$99"


def test_stop_removes_the_session() -> None:
    service = JevService(FakeAgent)
    session_id = service.browse("https://shop.example", "Find wireless headphones")["session_id"]

    assert service.stop(session_id)["status"] == "stopped"
    assert service.status(session_id)["ok"] is False
