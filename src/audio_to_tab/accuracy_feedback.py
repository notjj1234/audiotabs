"""Local session storage for Accurate? Yes/No feedback per run."""

from __future__ import annotations

ACCURACY_KEY = "tab_accuracy_feedback"


def get_accuracy_feedback(state: dict, run_id: str) -> str | None:
    store = state.get(ACCURACY_KEY)
    if not isinstance(store, dict):
        return None
    value = store.get(str(run_id))
    return value if value in {"yes", "no"} else None


def set_accuracy_feedback(state: dict, run_id: str, value: str) -> None:
    if value not in {"yes", "no"}:
        raise ValueError(f"accuracy feedback must be 'yes' or 'no', got {value!r}")
    store = state.get(ACCURACY_KEY)
    if not isinstance(store, dict):
        store = {}
        state[ACCURACY_KEY] = store
    store[str(run_id)] = value


__all__ = ["ACCURACY_KEY", "get_accuracy_feedback", "set_accuracy_feedback"]
