"""Map domain exceptions to API error payloads."""

from __future__ import annotations

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from audio_to_tab.user_errors import failure_actions, failure_kind, user_facing_message


def error_body(exc: BaseException) -> dict:
    kind = failure_kind(exc)
    message, detail = user_facing_message(exc)
    body: dict = {
        "code": kind,
        "message": message,
        "hint": detail,
        "action": (failure_actions(kind) or (None,))[0],
        "actions": list(failure_actions(kind)),
    }
    return body


def http_error(status: int, *, code: str, message: str, hint: str | None = None, action: str | None = None) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"code": code, "message": message, "hint": hint, "action": action},
    )


def json_error_response(status: int, exc: BaseException) -> JSONResponse:
    return JSONResponse(status_code=status, content=error_body(exc))
