from sqlalchemy import text
from sqlalchemy.orm import Session


def ensure_runtime_schema(db: Session) -> None:
    db.execute(
        text(
            """
            alter table document
            add column if not exists content_type text
            """
        )
    )
    db.execute(
        text(
            """
            create table if not exists chunk (
                id bigserial primary key,
                document_id text not null references document(id) on delete cascade,
                user_id text not null references app_user(id),
                chunk_index int not null,
                content text not null,
                page int not null default 1,
                section text,
                created_at timestamptz not null default now()
            )
            """
        )
    )
    db.execute(text("create index if not exists idx_chunk_user_doc on chunk(user_id, document_id, chunk_index)"))
    db.execute(
        text(
            """
            create table if not exists job (
                id text primary key,
                user_id text not null references app_user(id),
                job_type text not null,
                payload jsonb not null,
                status text not null default 'queued',
                error text,
                attempts int not null default 0,
                max_attempts int not null default 3,
                next_run_at timestamptz not null default now(),
                created_at timestamptz not null default now(),
                started_at timestamptz,
                finished_at timestamptz
            )
            """
        )
    )
    db.execute(text("alter table job add column if not exists attempts int not null default 0"))
    db.execute(text("alter table job add column if not exists max_attempts int not null default 3"))
    db.execute(text("alter table job add column if not exists next_run_at timestamptz not null default now()"))
    db.execute(text("create index if not exists idx_job_status_created on job(status, created_at asc)"))
