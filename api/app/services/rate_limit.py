import time
from collections import defaultdict, deque

from fastapi import HTTPException

from app.core.config import settings

_BUCKETS: dict[str, deque[float]] = defaultdict(deque)


def enforce_rate_limit(user_id: str) -> None:
    window_seconds = 60
    now = time.time()
    bucket = _BUCKETS[user_id]
    while bucket and now - bucket[0] > window_seconds:
        bucket.popleft()
    if len(bucket) >= settings.rate_limit_per_minute:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    bucket.append(now)
