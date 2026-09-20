"""Session lifecycle and MCP-friendly result shaping for Jev."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from jev_ultrafast import Agent

from .extract import extract_visible_products
from .safety import SensitiveActionBlocked, ensure_safe_action, ensure_safe_goal

MAX_STEPS_PER_CALL = 30
MAX_TEXT_CHARS = 6_000
MAX_ACTIONS = 80


@dataclass
class Session:
    """A single Jev Agent and the state required to explain its progress."""

    agent: Any
    goal: str
    created_at: float = field(default_factory=time.time)
    last_error: str | None = None


class JevService:
    """Owns browser-agent sessions and exposes only compact, model-useful results."""

    def __init__(self, agent_factory: Callable[[str, str], Any] = Agent) -> None:
        self._agent_factory = agent_factory
        self._sessions: dict[str, Session] = {}

    def browse(self, url: str, goal: str, max_steps: int = 20) -> dict[str, Any]:
        """Start a safe browsing session and run a bounded number of agent steps."""
        try:
            ensure_safe_goal(goal)
        except SensitiveActionBlocked as exc:
            return self._error(str(exc))
        if not url.startswith(("https://", "http://")):
            return self._error("URL must start with http:// or https://.")
        steps = max(1, min(max_steps, MAX_STEPS_PER_CALL))
        try:
            agent = self._agent_factory(url, goal)
            self._install_action_guard(agent)
        except Exception as exc:  # Browser/daemon and API configuration errors should be actionable.
            return self._error(self._explain_exception(exc))
        session_id = uuid.uuid4().hex
        self._sessions[session_id] = Session(agent=agent, goal=goal)
        return self._run(session_id, steps, created=True)

    def status(self, session_id: str) -> dict[str, Any]:
        """Return page evidence and recent decisions without advancing the browser."""
        session = self._sessions.get(session_id)
        if not session:
            return self._error(f"Unknown session_id {session_id!r}. Start with jev_browse.")
        return {"ok": True, "session_id": session_id, **self._summary(session)}

    def stop(self, session_id: str) -> dict[str, Any]:
        """Close one owned Chrome target and discard its in-memory session."""
        session = self._sessions.pop(session_id, None)
        if not session:
            return self._error(f"Unknown session_id {session_id!r}; it may already be closed.")
        try:
            session.agent.close()
        except Exception as exc:
            return self._error(
                f"The session was removed, but closing its Chrome target failed: {self._explain_exception(exc)}"
            )
        return {"ok": True, "session_id": session_id, "status": "stopped"}

    def extract_products(self, session_id: str) -> dict[str, Any]:
        """Return product cards currently visible in a live session, without browser actions."""
        session = self._sessions.get(session_id)
        if not session:
            return self._error(f"Unknown session_id {session_id!r}. Start with jev_browse.")
        try:
            extracted = extract_visible_products(session.agent.browser)
            return {
                "ok": True,
                "session_id": session_id,
                "url": self._page(session).get("url"),
                **extracted,
            }
        except Exception as exc:
            return self._error(f"Product extraction failed without changing the page: {self._explain_exception(exc)}")

    def _run(self, session_id: str, max_steps: int, *, created: bool) -> dict[str, Any]:
        session = self._sessions[session_id]
        executed = 0
        try:
            while executed < max_steps and session.agent.state["status"] not in {"done", "blocked"}:
                session.agent.command("tick")
                executed += 1
        except SensitiveActionBlocked as exc:
            session.agent.state["status"] = "blocked"
            session.last_error = str(exc)
        except Exception as exc:
            session.last_error = self._explain_exception(exc)
        summary = self._summary(session)
        return {"ok": True, "session_id": session_id, "created": created, "steps_executed": executed, **summary}

    def _summary(self, session: Session) -> dict[str, Any]:
        snapshot = session.agent.snapshot()
        page = self._page(session)
        return {
            "status": snapshot.get("status"),
            "goal": session.goal,
            "elapsed_ms": snapshot.get("elapsed_ms", 0),
            "page": page,
            "visible_elements": self._elements(snapshot.get("elements", [])),
            "recent_actions": snapshot.get("history", [])[-12:],
            "last_error": session.last_error,
            "next_step": self._next_step(snapshot.get("status"), session.last_error),
        }

    @staticmethod
    def _page(session: Session) -> dict[str, Any]:
        page = session.agent.state.get("page", {})
        return {
            "url": page.get("url"),
            "title": page.get("title"),
            "visible_text": str(page.get("text", ""))[:MAX_TEXT_CHARS],
            "scroll": page.get("scroll"),
        }

    @staticmethod
    def _elements(elements: Any) -> list[dict[str, Any]]:
        if not isinstance(elements, list):
            return []
        compact: list[dict[str, Any]] = []
        for element in elements[:MAX_ACTIONS]:
            if not isinstance(element, dict):
                continue
            compact.append(
                {
                    key: element[key]
                    for key in ("index", "role", "label", "value", "operations", "options")
                    if key in element
                }
            )
        return compact

    @staticmethod
    def _next_step(status: Any, error: str | None) -> str:
        if error:
            return "Inspect the error and revise the browsing goal or site setup; no unsafe action was executed."
        if status == "done":
            return "Use jev_extract_products for structured product data, or jev_stop to close this session."
        if status == "blocked":
            return "Inspect visible_elements and recent_actions; this MVP cannot handle the required control."
        return "Call jev_status to inspect state, or start a new bounded browsing task."

    @staticmethod
    def _install_action_guard(agent: Any) -> None:
        original_act = agent.browser.act

        def guarded_act(action: dict[str, Any], page: dict[str, Any], text: str | None = None) -> Any:
            ensure_safe_action(action)
            return original_act(action, page, text=text)

        agent.browser.act = guarded_act

    @staticmethod
    def _error(message: str) -> dict[str, Any]:
        return {"ok": False, "error": message}

    @staticmethod
    def _explain_exception(exc: Exception) -> str:
        if isinstance(exc, KeyError) and str(exc).strip("'") == "TYPESAFE_API_KEY":
            return "TYPESAFE_API_KEY is missing. Put it in .env or the MCP server environment, then restart the server."
        if isinstance(exc, SensitiveActionBlocked):
            return str(exc)
        return str(exc) or exc.__class__.__name__
