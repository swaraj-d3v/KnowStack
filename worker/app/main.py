import os
import time

import httpx
import psycopg


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:2233@localhost:5432/knowstack")
API_BASE = os.getenv("API_BASE_URL", "http://api:8000")
WORKER_USER = os.getenv("WORKER_USER_ID", "worker-service")
POLL_SECONDS = int(os.getenv("WORKER_POLL_SECONDS", "5"))


def fetch_queued_job_ids(limit: int = 5) -> list[str]:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id
                from job
                where status = 'queued'
                  and next_run_at <= now()
                order by next_run_at asc, created_at asc
                limit %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    return [row[0] for row in rows]


def run_job(job_id: str) -> None:
    headers = {"X-User-Id": WORKER_USER, "X-User-Role": "admin"}
    with httpx.Client(timeout=60.0) as client:
        response = client.post(f"{API_BASE}/v1/jobs/{job_id}/run", headers=headers)
    if response.status_code >= 400:
        print(f"job {job_id} failed to trigger: {response.status_code} {response.text}")
    else:
        print(f"job {job_id} executed")


def run() -> None:
    print("worker started")
    while True:
        try:
            job_ids = fetch_queued_job_ids()
            for job_id in job_ids:
                run_job(job_id)
        except Exception as exc:
            print(f"worker loop error: {exc}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    run()
