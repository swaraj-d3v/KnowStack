import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.ingestion import extract_text, split_into_chunks
from app.services.schema import ensure_runtime_schema
from app.services.vector import upsert_chunk_vectors


def process_document_sync(db: Session, user_id: str, document_id: str) -> int:
    ensure_runtime_schema(db)
    doc = (
        db.execute(
            text(
                """
                select id, content_type, storage_key
                from document
                where id = :document_id and user_id = :user_id
                """
            ),
            {"document_id": document_id, "user_id": user_id},
        )
        .mappings()
        .first()
    )
    if not doc:
        raise ValueError("Document not found for user")
    if not doc["storage_key"]:
        raise ValueError("Document has no storage key")

    text_content = extract_text(str(doc["storage_key"]), str(doc["content_type"] or ""))
    chunks = split_into_chunks(text_content)

    db.execute(text("delete from chunk where document_id = :document_id"), {"document_id": document_id})
    inserted_rows = []
    for idx, chunk in enumerate(chunks):
        row = (
            db.execute(
                text(
                    """
                    insert into chunk (document_id, user_id, chunk_index, content, page, section)
                    values (:document_id, :user_id, :chunk_index, :content, 1, 'Body')
                    returning id
                    """
                ),
                {
                    "document_id": document_id,
                    "user_id": user_id,
                    "chunk_index": idx,
                    "content": chunk,
                },
            )
            .mappings()
            .first()
        )
        if row:
            inserted_rows.append(
                {
                    "chunk_id": int(row["id"]),
                    "content": chunk,
                    "user_id": user_id,
                    "document_id": document_id,
                }
            )

    upsert_chunk_vectors(inserted_rows)
    db.execute(text("update document set status = 'processed' where id = :id"), {"id": document_id})
    db.commit()
    return len(chunks)


def enqueue_document_job(db: Session, user_id: str, document_id: str) -> tuple[str, datetime]:
    ensure_runtime_schema(db)
    job_id = str(uuid4())
    created_at = datetime.now(timezone.utc)
    db.execute(
        text(
            """
            insert into job (id, user_id, job_type, payload, status, attempts, max_attempts, next_run_at, created_at)
            values (
                :id, :user_id, 'document_process', cast(:payload as jsonb), 'queued',
                0, :max_attempts, :next_run_at, :created_at
            )
            """
        ),
        {
            "id": job_id,
            "user_id": user_id,
            "payload": json.dumps({"document_id": document_id}),
            "max_attempts": settings.job_max_attempts,
            "next_run_at": created_at,
            "created_at": created_at,
        },
    )
    db.commit()
    return job_id, created_at


def run_job(db: Session, job_id: str) -> str:
    ensure_runtime_schema(db)
    job = (
        db.execute(
            text(
                """
                select id, user_id, job_type, payload, attempts, max_attempts
                from job
                where id = :id
                """
            ),
            {"id": job_id},
        )
        .mappings()
        .first()
    )
    if not job:
        raise ValueError("Job not found")

    db.execute(
        text(
            """
            update job
            set status = 'processing',
                started_at = :started_at,
                attempts = coalesce(attempts, 0) + 1
            where id = :id
            """
        ),
        {"id": job_id, "started_at": datetime.now(timezone.utc)},
    )
    db.commit()

    try:
        if str(job["job_type"]) == "document_process":
            payload = job["payload"] or {}
            document_id = str(payload.get("document_id") if isinstance(payload, dict) else "")
            if not document_id:
                raise ValueError("Job payload missing document_id")
            process_document_sync(db, str(job["user_id"]), document_id)
        else:
            raise ValueError(f"Unsupported job type: {job['job_type']}")
    except Exception as exc:
        attempts = int(job.get("attempts") or 0) + 1
        max_attempts = int(job.get("max_attempts") or settings.job_max_attempts)
        if attempts < max_attempts:
            retry_seconds = settings.job_retry_base_seconds * (2 ** (attempts - 1))
            db.execute(
                text(
                    """
                    update job
                    set status = 'queued',
                        error = :error,
                        next_run_at = :next_run_at,
                        finished_at = null
                    where id = :id
                    """
                ),
                {
                    "id": job_id,
                    "error": str(exc),
                    "next_run_at": datetime.now(timezone.utc) + timedelta(seconds=retry_seconds),
                },
            )
            db.commit()
            return "queued"
        db.execute(
            text(
                """
                update job
                set status = 'failed', error = :error, finished_at = :finished_at
                where id = :id
                """
            ),
            {"id": job_id, "error": str(exc), "finished_at": datetime.now(timezone.utc)},
        )
        db.commit()
        return "failed"

    db.execute(
        text("update job set status = 'completed', finished_at = :finished_at where id = :id"),
        {"id": job_id, "finished_at": datetime.now(timezone.utc)},
    )
    db.commit()
    return "completed"
