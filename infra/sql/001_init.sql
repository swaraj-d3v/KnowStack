-- Base relational schema for multi-tenant RAG SaaS

create table if not exists app_user (
    id text primary key,
    email text not null unique,
    role text not null default 'user',
    created_at timestamptz not null default now()
);

create table if not exists document (
    id text primary key,
    user_id text not null references app_user(id),
    filename text not null,
    content_type text,
    storage_key text,
    sha256 text not null,
    size_bytes bigint not null,
    page_count int,
    status text not null default 'queued',
    created_at timestamptz not null default now()
);

create index if not exists idx_document_user on document(user_id);

create table if not exists chat (
    id text primary key,
    user_id text not null references app_user(id),
    title text,
    created_at timestamptz not null default now()
);

create index if not exists idx_chat_user on chat(user_id);

create table if not exists message (
    id text primary key,
    chat_id text not null references chat(id),
    user_id text not null references app_user(id),
    role text not null,
    content text not null,
    created_at timestamptz not null default now()
);

create index if not exists idx_message_chat on message(chat_id);

create table if not exists message_source (
    id bigserial primary key,
    message_id text not null references message(id),
    document_id text not null references document(id),
    page int,
    section text,
    snippet text not null
);

create table if not exists usage_event (
    id bigserial primary key,
    user_id text not null references app_user(id),
    event_type text not null,
    model text,
    prompt_tokens int,
    completion_tokens int,
    total_cost_usd numeric(10, 6),
    created_at timestamptz not null default now()
);

create index if not exists idx_usage_user_time on usage_event(user_id, created_at desc);

create table if not exists chunk (
    id bigserial primary key,
    document_id text not null references document(id) on delete cascade,
    user_id text not null references app_user(id),
    chunk_index int not null,
    content text not null,
    page int not null default 1,
    section text,
    created_at timestamptz not null default now()
);

create index if not exists idx_chunk_user_doc on chunk(user_id, document_id, chunk_index);

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
);

create index if not exists idx_job_status_created on job(status, created_at asc);
