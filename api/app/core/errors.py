import logging
from datetime import datetime, timezone

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("knowstack.api")


def _error_payload(request: Request, code: str, message: str, status_code: int) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "status_code": status_code,
            "path": request.url.path,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": getattr(request.state, "request_id", ""),
        }
    }


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    payload = _error_payload(
        request=request,
        code="http_error",
        message=str(exc.detail),
        status_code=exc.status_code,
    )
    return JSONResponse(status_code=exc.status_code, content=payload)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s", request.url.path)
    payload = _error_payload(
        request=request,
        code="internal_error",
        message="Internal server error",
        status_code=500,
    )
    return JSONResponse(status_code=500, content=payload)
