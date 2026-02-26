import logging
import time
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import http_exception_handler, unhandled_exception_handler
from app.routes.v1 import router as v1_router

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("knowstack.api")

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(v1_router, prefix="/v1", tags=["v1"])
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    request_id = str(uuid4())
    request.state.request_id = request_id
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000.0
    response.headers["X-Request-Id"] = request_id
    logger.info(
        "request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response