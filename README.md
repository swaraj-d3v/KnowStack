# KnowStack

Multi-tenant SaaS RAG platform scaffold.

## Services
- `api`: FastAPI backend (auth-ready, upload/chat endpoints scaffolded)
- `worker`: async document processing worker placeholder
- `postgres`: app relational data
- `redis`: queue/cache
- `qdrant`: vector database

## Quick Start
1. Copy env file
   - `copy .env.example .env`
2. Start infrastructure + app containers
   - `docker compose up --build`
3. Open API docs
   - `http://localhost:8000/docs`

## Implemented Backend Modules
- Dev/JWT auth dependency with role support (`user`, `admin`)
- Upload + dedupe + file storage + document metadata persistence
- Sync and async document processing (`/process`, `/process-async`, job tables)
- TXT/PDF/DOCX extraction and chunking
- Hybrid retrieval (keyword + vector score when qdrant is available)
- Gemini/OpenAI grounded generation fallback
- Citations persisted in `message_source`
- Chat history/list/export/delete endpoints
- Usage event logging and admin metrics endpoint
- Worker job polling loop for queued jobs
- Job retries with backoff (`attempts`, `max_attempts`, `next_run_at`)
- Structured request logging (`X-Request-Id`) and uniform error payloads
- Basic automated tests and GitHub Actions CI (`.github/workflows/api-ci.yml`)

## Main API Endpoints
- `POST /v1/documents/upload`
- `GET /v1/documents`
- `POST /v1/documents/{document_id}/process`
- `POST /v1/documents/{document_id}/process-async`
- `GET /v1/jobs/{job_id}`
- `POST /v1/jobs/{job_id}/run`
- `POST /v1/chat/ask`
- `GET /v1/chats`
- `GET /v1/chats/{chat_id}`
- `DELETE /v1/chats/{chat_id}`
- `GET /v1/chats/{chat_id}/export`
- `GET /v1/admin/metrics` (admin role)

## Migrations
- `infra/sql/001_init.sql`
- `infra/sql/002_jobs_and_runtime.sql`
