"""OpenRouter Decisions compatibility adapter for the pinned upstream Jev agent."""

from __future__ import annotations

import os
import time
from typing import Any

import httpx
from jev_ultrafast import agent as upstream_agent
from jev_ultrafast import model as upstream_model

OPENROUTER_DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
_client = httpx.Client(http2=True, timeout=25)


def openrouter_enabled() -> bool:
    """Return whether an OpenRouter key opts this process into the Decisions adapter."""
    return bool(os.environ.get("JEV_DECISIONS_API_KEY") or os.environ.get("OPENROUTER_API_KEY"))


def install_openrouter_adapter() -> bool:
    """Route the pinned Agent's decision function through OpenRouter when configured.

    Upstream imports ``choose`` into its agent module, so patching that module-level binding keeps the
    upstream browser/action loop unchanged while swapping only its decision provider.
    """
    if not openrouter_enabled():
        return False
    openrouter_key = _api_key()
    os.environ.setdefault("TEXT_MODEL_API_KEY", openrouter_key)
    upstream_agent.choose = choose_with_openrouter
    return True


def choose_with_openrouter(state: dict[str, Any], goal: str, history: list[dict[str, Any]]) -> dict[str, Any]:
    """Make Jev's typed operation/target decision through OpenRouter's alpha endpoint."""
    elements, targets, controls = upstream_model.action_space(state["actions"])
    operation_labels = {
        "CLICK": "Click an element, button, menu option, autocomplete suggestion, or calendar day.",
        "TYPE_TEXT": "Enter or replace text in an editable field. A small LLM will supply the value from the goal.",
        "SELECT": "Select an observed dropdown value.",
    }
    operations = {name: operation_labels[name] for name in targets}
    operations.update({name: action["label"] for name, action in controls.items()})
    operations.update(DONE="Every requirement is visibly satisfied.", BLOCKED="No supported operation can progress.")

    questions: dict[str, Any] = {
        "operation": {
            "type": "choice",
            "criteria": operations,
            "instructions": {"goal": goal, "rules": upstream_model.NEXT_ACTION},
        }
    }
    for operation, candidates in targets.items():
        questions[operation.lower() + "_target"] = {
            "type": "choice",
            "criteria": {
                index: {
                    "element": f"[{index}] {action['label']}",
                    "current_value": action.get("current_value", action.get("value", "")),
                    **{key: action[key] for key in ("role", "checked", "selected", "expanded") if key in action},
                }
                for index, action in candidates.items()
            },
            "instructions": {
                "goal": goal,
                "operation": operation,
                "rules": [upstream_model.NEXT_ACTION, upstream_model.TARGET],
            },
        }

    body = {
        "model": os.environ.get("JEV_DECISIONS_MODEL", "~typesafe/jev-latest"),
        "state": {
            "page": {key: state[key] for key in ("url", "title", "text")},
            "elements": elements,
            "recent_actions": [
                {key: item.get(key) for key in ("action", "kind", "text", "page_changed")} for item in history[-10:]
            ],
        },
        "questions": questions,
    }
    started_at = time.perf_counter()
    result = _post_decision(body)
    operation_answer = upstream_model.validate_choice(result.get("answers", {}).get("operation", {}), operations)
    operation = operation_answer["choice"]
    target_answer: dict[str, Any] | None = None
    if operation in targets:
        target_answer = upstream_model.validate_choice(
            result.get("answers", {}).get(operation.lower() + "_target", {}), targets[operation]
        )
        target = target_answer["choice"]
        choice = targets[operation][target]["id"]
        probabilities = {
            action["id"]: target_answer["probabilities"][index] for index, action in targets[operation].items()
        }
    else:
        target = None
        choice = controls[operation]["id"] if operation in controls else operation
        probabilities = {choice: operation_answer["probabilities"][operation]}

    return {
        "choice": choice,
        "operation": operation,
        "target": target,
        "confidence": operation_answer["confidence"],
        "probabilities": probabilities,
        "operation_probabilities": operation_answer["probabilities"],
        "target_probabilities": target_answer["probabilities"] if target_answer else {},
        "target_confidence": target_answer["confidence"] if target_answer else None,
        "raw_answers": result["answers"],
        "model": result.get("model", body["model"]),
        "usage": result.get("usage", {}),
        "latency_ms": round((time.perf_counter() - started_at) * 1000),
        "request": body,
    }


def _api_key() -> str:
    key = os.environ.get("JEV_DECISIONS_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY or JEV_DECISIONS_API_KEY is required for OpenRouter Decisions.")
    return key


def _post_decision(body: dict[str, Any]) -> dict[str, Any]:
    url = os.environ.get("JEV_DECISIONS_BASE_URL", OPENROUTER_DECISIONS_URL)
    for attempt in range(3):
        try:
            response = _client.post(url, json=body, headers={"Authorization": f"Bearer {_api_key()}"})
        except httpx.HTTPError as exc:
            raise RuntimeError("OpenRouter Decisions connection failed; no browser action executed.") from exc
        if response.status_code in {429, 503, 529} and attempt < 2:
            time.sleep(0.5 * 2**attempt)
            continue
        if response.is_error:
            raise RuntimeError(
                f"OpenRouter Decisions returned HTTP {response.status_code}; no browser action executed."
            )
        try:
            result = response.json()
        except ValueError as exc:
            raise RuntimeError("OpenRouter Decisions returned invalid JSON; no browser action executed.") from exc
        if not isinstance(result, dict):
            raise RuntimeError("OpenRouter Decisions returned an invalid response; no browser action executed.")
        return result
    raise RuntimeError("OpenRouter Decisions is unavailable; no browser action executed.")
