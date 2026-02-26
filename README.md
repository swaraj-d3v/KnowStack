<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&height=220&color=0:0f172a,100:2563eb&text=KnowStack&fontAlignY=40&fontColor=ffffff&desc=Multi-tenant%20SaaS%20RAG%20Platform&descAlignY=62&animation=fadeIn" alt="KnowStack Banner" />

<p>
  <img src="https://readme-typing-svg.demolab.com?font=JetBrains+Mono&weight=600&size=18&pause=1200&center=true&vCenter=true&width=800&lines=Upload+Documents+%E2%86%92+Process+%E2%86%92+Retrieve+%E2%86%92+Grounded+Answers;FastAPI+%7C+Postgres+%7C+Redis+%7C+Qdrant+%7C+Next.js;Built+for+scalable%2C+citation-first+knowledge+chat" alt="Typing Intro" />
</p>

<p>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" />
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white" />
  <img alt="Postgres" src="https://img.shields.io/badge/Postgres-Data-4169E1?logo=postgresql&logoColor=white" />
  <img alt="Redis" src="https://img.shields.io/badge/Redis-Queue-DC382D?logo=redis&logoColor=white" />
  <img alt="Qdrant" src="https://img.shields.io/badge/Qdrant-Vector-FF4F8B" />
  <img alt="Next.js" src="https://img.shields.io/badge/Next.js-Web-000000?logo=nextdotjs&logoColor=white" />
</p>

</div>

## Overview
KnowStack is a multi-tenant RAG platform scaffold for document-grounded chat.
It provides file ingestion, extraction, chunking, retrieval, answer generation, citations, chat history, usage metrics, and async job orchestration.

## What You Get
- Multi-tenant auth model with role guards (`user`, `admin`)
- Upload + dedupe + metadata persistence
- Sync and async processing pipelines (`/process`, `/process-async`)
- TXT/PDF/DOCX parsing and chunking
- Hybrid retrieval (keyword + vector)
- LLM grounded generation with fallback strategy
- Citation persistence (`message_source`)
- Chat history list/detail/export/delete
- Usage logging + admin metrics
- Worker job polling + retry/backoff
- Structured error and request-id flow

## System Architecture
```mermaid
flowchart LR
  U[User / Client] --> W[Next.js Web]
  W --> A[FastAPI API]
  A --> P[(Postgres)]
  A --> R[(Redis)]
  A --> Q[(Qdrant)]
  A --> S[(Local/Object Storage)]
  R --> K[Worker]
  K --> P
  K --> Q
  K --> S
```

## Request Lifecycle
```mermaid
sequenceDiagram
  participant C as Client
  participant API as FastAPI
  participant DB as Postgres
  participant WRK as Worker
  participant VDB as Qdrant

  C->>API: Upload document
  API->>DB: Create document row (queued)
  API->>WRK: Enqueue process job
  WRK->>DB: Load document + update status
  WRK->>VDB: Upsert embeddings/chunks
  WRK->>DB: Mark processed
  C->>API: Ask question
  API->>VDB: Hybrid retrieve
  API->>DB: Save messages + citations
  API-->>C: Grounded answer
```

## Project Structure
```text
KnowStack/
+- api/        # FastAPI backend + services + tests
+- worker/     # Async job worker
+- web/        # Next.js frontend
+- infra/sql/  # SQL bootstrap and runtime migrations
+- docs/       # Planning and implementation notes
+- docker-compose.yml
```

## Quick Start
### 1. Configure environment
```powershell
copy .env.example .env
```

### 2. Start all services
```powershell
docker compose up --build
```

### 3. Open API docs
- Swagger: `http://localhost:8000/docs`

## Core Endpoints
### Health
- `GET /v1/health`

### Documents
- `POST /v1/documents/upload`
- `GET /v1/documents`
- `POST /v1/documents/{document_id}/process`
- `POST /v1/documents/{document_id}/process-async`

### Jobs
- `GET /v1/jobs/{job_id}`
- `POST /v1/jobs/{job_id}/run`

### Chat
- `POST /v1/chat/ask`
- `GET /v1/chats`
- `GET /v1/chats/{chat_id}`
- `DELETE /v1/chats/{chat_id}`
- `GET /v1/chats/{chat_id}/export`

### Admin
- `GET /v1/admin/metrics`

## Database Migrations
- `infra/sql/001_init.sql`
- `infra/sql/002_jobs_and_runtime.sql`

## Current Status
- Backend scaffold is feature-complete for end-to-end local RAG flow.
- Worker + async job flow is implemented.
- Basic API tests and CI are included.

## Next Improvements
- Add deeper retrieval evaluation harness
- Add streaming responses in chat endpoint
- Add full observability dashboards (latency/error/queue)
- Add stronger tenancy isolation tests
- Add production object storage integration

## Contributing
1. Create a feature branch.
2. Keep changes scoped and test-backed.
3. Open a PR with problem statement, approach, and verification notes.

## License
Private project unless explicitly licensed by repository owner.
