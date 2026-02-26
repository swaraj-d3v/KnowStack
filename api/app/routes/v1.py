import hashlib
import re
import time
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user, require_admin
from app.core.db import get_db
from app.core.config import settings
from app.models import (
    AdminMetricsResponse,
    ChatAskRequest,
    ChatAskResponse,
    ChatDetailResponse,
    ChatMessage,
    ChatSummary,
    Citation,
    DocumentCreateRequest,
    DocumentCreateResponse,
    DocumentProcessResponse,
    DocumentSummary,
    HealthResponse,
    JobDetailResponse,
    JobResponse,
)
from app.services.llm import generate_fallback_answer, generate_grounded_answer
from app.services.processing import enqueue_document_job, process_document_sync, run_job
from app.services.rate_limit import enforce_rate_limit
from app.services.retrieval import hybrid_retrieve
from app.services.schema import ensure_runtime_schema
from app.services.storage import save_user_file
from app.services.usage import log_usage_event

router = APIRouter()



def clean_snippet(text: str) -> str:
    snippet = text.replace("\u00a0", " ").replace("\u200b", " ")
    snippet = re.sub(r"([a-z])([A-Z])", r"\1 \2", snippet)
    snippet = re.sub(r"\s+", " ", snippet)
    snippet = re.sub(r"\s*([,.;:])\s*", r"\1 ", snippet)
    return snippet.strip()

def ensure_user_exists(db: Session, user: CurrentUser) -> None:
    email = user.email or f"{user.user_id}@local.dev"
    db.execute(
        text(
            """
            insert into app_user (id, email, role)
            values (:id, :email, :role)
            on conflict (id) do update set role = excluded.role
            """
        ),
        {"id": user.user_id, "email": email, "role": user.role},
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="api")


@router.post("/documents", response_model=DocumentCreateResponse)
def create_document(
    payload: DocumentCreateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentCreateResponse:
    ensure_runtime_schema(db)
    ensure_user_exists(db, user)
    existing = (
        db.execute(
            text(
                """
                select id, status, created_at
                from document
                where user_id = :user_id and sha256 = :sha256
                order by created_at desc
                limit 1
                """
            ),
            {"user_id": user.user_id, "sha256": payload.sha256},
        )
        .mappings()
        .first()
    )
    if existing:
        db.commit()
        return DocumentCreateResponse(
            id=str(existing["id"]),
            status=str(existing["status"]),
            created_at=existing["created_at"],
            is_duplicate=True,
        )

    document_id = str(uuid4())
    created_at = datetime.now(timezone.utc)
    db.execute(
        text(
            """
            insert into document (
                id, user_id, filename, content_type, sha256, size_bytes, status, created_at
            )
            values (
                :id, :user_id, :filename, :content_type, :sha256, :size_bytes, 'queued', :created_at
            )
            """
        ),
        {
            "id": document_id,
            "user_id": user.user_id,
            "filename": payload.filename,
            "content_type": payload.content_type,
            "sha256": payload.sha256,
            "size_bytes": payload.size_bytes,
            "created_at": created_at,
        },
    )
    db.commit()
    return DocumentCreateResponse(id=document_id, status="queued", created_at=created_at, is_duplicate=False)


@router.get("/documents", response_model=list[DocumentSummary])
def list_documents(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DocumentSummary]:
    ensure_runtime_schema(db)
    ensure_user_exists(db, user)
    offset = (page - 1) * page_size
    params = {"user_id": user.user_id, "limit": page_size, "offset": offset}
    query = """
        select id, filename, content_type, status, size_bytes, created_at
        from document
        where user_id = :user_id
    """
    if status:
        query += " and status = :status"
        params["status"] = status
    query += " order by created_at desc limit :limit offset :offset"
    rows = db.execute(text(query), params).mappings().all()
    db.commit()
    return [
        DocumentSummary(
            id=str(row["id"]),
            filename=str(row["filename"]),
            content_type=(str(row["content_type"]) if row["content_type"] is not None else None),
            status=str(row["status"]),
            size_bytes=int(row["size_bytes"]),
            created_at=row["created_at"],
        )
        for row in rows
    ]


@router.post("/documents/upload", response_model=DocumentCreateResponse)
async def upload_document(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentCreateResponse:
    ensure_runtime_schema(db)
    ensure_user_exists(db, user)
    allowed_content_types = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
    }
    if file.content_type not in allowed_content_types:
        raise HTTPException(status_code=400, detail="Only PDF, DOCX, and TXT are allowed")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.max_upload_mb} MB limit")

    sha256 = hashlib.sha256(content).hexdigest()
    existing = (
        db.execute(
            text(
                """
                select id, status, created_at
                from document
                where user_id = :user_id and sha256 = :sha256
                order by created_at desc
                limit 1
                """
            ),
            {"user_id": user.user_id, "sha256": sha256},
        )
        .mappings()
        .first()
    )
    if existing:
        db.commit()
        return DocumentCreateResponse(
            id=str(existing["id"]),
            status=str(existing["status"]),
            created_at=existing["created_at"],
            is_duplicate=True,
        )

    document_id = str(uuid4())
    created_at = datetime.now(timezone.utc)
    storage_key = save_user_file(user.user_id, document_id, file.filename or "upload.bin", content)
    db.execute(
        text(
            """
            insert into document (
                id, user_id, filename, content_type, storage_key, sha256, size_bytes, status, created_at
            )
            values (
                :id, :user_id, :filename, :content_type, :storage_key, :sha256, :size_bytes, 'queued', :created_at
            )
            """
        ),
        {
            "id": document_id,
            "user_id": user.user_id,
            "filename": file.filename or "upload.bin",
            "content_type": file.content_type or "application/octet-stream",
            "storage_key": storage_key,
            "sha256": sha256,
            "size_bytes": len(content),
            "created_at": created_at,
        },
    )
    db.commit()
    return DocumentCreateResponse(id=document_id, status="queued", created_at=created_at, is_duplicate=False)


@router.post("/documents/{document_id}/process", response_model=DocumentProcessResponse)
def process_document(
    document_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentProcessResponse:
    ensure_runtime_schema(db)
    ensure_user_exists(db, user)
    try:
        chunk_count = process_document_sync(db, user_id=user.user_id, document_id=document_id)
    except Exception as exc:
        db.execute(text("update document set status = 'failed' where id = :id"), {"id": document_id})
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DocumentProcessResponse(document_id=document_id, status="processed", chunk_count=chunk_count)


@router.post("/documents/{document_id}/process-async", response_model=JobResponse)
def process_document_async(
    document_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobResponse:
    ensure_runtime_schema(db)
    ensure_user_exists(db, user)
    row = (
        db.execute(
            text("select id from document where id = :id and user_id = :user_id"),
            {"id": document_id, "user_id": user.user_id},
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    job_id, created_at = enqueue_document_job(db, user_id=user.user_id, document_id=document_id)
    return JobResponse(job_id=job_id, status="queued", created_at=created_at)


@router.get("/jobs/{job_id}", response_model=JobDetailResponse)
def get_job(
    job_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobDetailResponse:
    ensure_runtime_schema(db)
    row = (
        db.execute(
            text(
                """
                select id, job_type, status, error, attempts, max_attempts, next_run_at, created_at, started_at, finished_at
                from job
                where id = :id and user_id = :user_id
                """
            ),
            {"id": job_id, "user_id": user.user_id},
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobDetailResponse(
        job_id=str(row["id"]),
        job_type=str(row["job_type"]),
        status=str(row["status"]),
        error=(str(row["error"]) if row["error"] else None),
        attempts=int(row["attempts"] or 0),
        max_attempts=int(row["max_attempts"] or 0),
        next_run_at=row["next_run_at"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )


@router.post("/jobs/{job_id}/run", response_model=JobDetailResponse)
def run_job_now(
    job_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobDetailResponse:
    ensure_runtime_schema(db)
    row = (
        db.execute(text("select user_id from job where id = :id"), {"id": job_id}).mappings().first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    if row["user_id"] != user.user_id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Not allowed")
    status = run_job(db, job_id)
    detail = (
        db.execute(
            text(
                """
                select id, job_type, status, error, attempts, max_attempts, next_run_at, created_at, started_at, finished_at
                from job where id = :id
                """
            ),
            {"id": job_id},
        )
        .mappings()
        .first()
    )
    return JobDetailResponse(
        job_id=str(detail["id"]),
        job_type=str(detail["job_type"]),
        status=status,
        error=(str(detail["error"]) if detail["error"] else None),
        attempts=int(detail["attempts"] or 0),
        max_attempts=int(detail["max_attempts"] or 0),
        next_run_at=detail["next_run_at"],
        created_at=detail["created_at"],
        started_at=detail["started_at"],
        finished_at=detail["finished_at"],
    )


@router.post("/chat/ask", response_model=ChatAskResponse)
def ask_chat(
    payload: ChatAskRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatAskResponse:
    ensure_runtime_schema(db)
    ensure_user_exists(db, user)
    enforce_rate_limit(user.user_id)
    start_ts = time.perf_counter()

    if payload.chat_id:
        existing_chat = (
            db.execute(
                text("select id from chat where id = :chat_id and user_id = :user_id"),
                {"chat_id": payload.chat_id, "user_id": user.user_id},
            )
            .mappings()
            .first()
        )
        if not existing_chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        chat_id = payload.chat_id
    else:
        chat_id = str(uuid4())
        db.execute(
            text("insert into chat (id, user_id, title, created_at) values (:id, :user_id, :title, :created_at)"),
            {
                "id": chat_id,
                "user_id": user.user_id,
                "title": payload.question[:80],
                "created_at": datetime.now(timezone.utc),
            },
        )

    user_message_id = str(uuid4())
    db.execute(
        text(
            """
            insert into message (id, chat_id, user_id, role, content, created_at)
            values (:id, :chat_id, :user_id, 'user', :content, :created_at)
            """
        ),
        {
            "id": user_message_id,
            "chat_id": chat_id,
            "user_id": user.user_id,
            "content": payload.question,
            "created_at": datetime.now(timezone.utc),
        },
    )

    recent_conversation = _load_recent_conversation(db, chat_id, user.user_id, user_message_id)
    conversation_context = _conversation_context_for_llm(recent_conversation)
    effective_question = _build_effective_question(payload.question, recent_conversation)

    rows = hybrid_retrieve(db, user_id=user.user_id, question=effective_question, document_id=payload.document_id)
    citations: list[Citation] = []
    context_snippets: list[str] = []
    for row in rows:
        snippet = clean_snippet(str(row["content"]))[:320]
        context_snippets.append(snippet)
        citations.append(
            Citation(
                document_id=str(row["document_id"]),
                document_name=str(row["document_name"]),
                page=int(row["page"] or 1),
                section=str(row["section"] or "Body"),
                snippet=snippet,
            )
        )

    if context_snippets:
        llm_answer, model_used = generate_grounded_answer(
            payload.question,
            context_snippets,
            conversation_context=conversation_context,
        )
        answer = llm_answer or generate_fallback_answer(
            payload.question,
            context_snippets,
            conversation_context=conversation_context,
        )
        model_name = model_used or "fallback"
    else:
        answer = "I could not find enough processed content in your documents yet. Please upload and process a document first.\n\nWhat would you like to do next?"
        model_name = "none"

    assistant_message_id = str(uuid4())
    db.execute(
        text(
            """
            insert into message (id, chat_id, user_id, role, content, created_at)
            values (:id, :chat_id, :user_id, 'assistant', :content, :created_at)
            """
        ),
        {
            "id": assistant_message_id,
            "chat_id": chat_id,
            "user_id": user.user_id,
            "content": answer,
            "created_at": datetime.now(timezone.utc),
        },
    )
    for citation in citations:
        db.execute(
            text(
                """
                insert into message_source (message_id, document_id, page, section, snippet)
                values (:message_id, :document_id, :page, :section, :snippet)
                """
            ),
            {
                "message_id": assistant_message_id,
                "document_id": citation.document_id,
                "page": citation.page,
                "section": citation.section,
                "snippet": citation.snippet,
            },
        )

    elapsed = time.perf_counter() - start_ts
    log_usage_event(
        db=db,
        user_id=user.user_id,
        event_type="chat_ask",
        model=model_name,
        prompt_tokens=max(1, len(effective_question) // 4),
        completion_tokens=max(1, len(answer) // 4),
        total_cost_usd=round(elapsed * 0.0001, 6),
    )
    db.commit()
    return ChatAskResponse(chat_id=chat_id, answer=answer, citations=citations)


@router.get("/chats", response_model=list[ChatSummary])
def list_chats(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatSummary]:
    offset = (page - 1) * page_size
    rows = (
        db.execute(
            text(
                """
                select c.id, c.title, c.created_at, count(m.id) as message_count
                from chat c
                left join message m on m.chat_id = c.id
                where c.user_id = :user_id
                group by c.id
                order by c.created_at desc
                limit :limit offset :offset
                """
            ),
            {"user_id": user.user_id, "limit": page_size, "offset": offset},
        )
        .mappings()
        .all()
    )
    return [
        ChatSummary(
            chat_id=str(row["id"]),
            title=(str(row["title"]) if row["title"] else None),
            created_at=row["created_at"],
            message_count=int(row["message_count"] or 0),
        )
        for row in rows
    ]


@router.get("/chats/{chat_id}", response_model=ChatDetailResponse)
def get_chat(
    chat_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatDetailResponse:
    chat = (
        db.execute(
            text("select id, title, created_at from chat where id = :chat_id and user_id = :user_id"),
            {"chat_id": chat_id, "user_id": user.user_id},
        )
        .mappings()
        .first()
    )
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    rows = (
        db.execute(
            text(
                """
                select id, role, content, created_at
                from message
                where chat_id = :chat_id and user_id = :user_id
                order by created_at asc
                """
            ),
            {"chat_id": chat_id, "user_id": user.user_id},
        )
        .mappings()
        .all()
    )
    return ChatDetailResponse(
        chat_id=str(chat["id"]),
        title=(str(chat["title"]) if chat["title"] else None),
        created_at=chat["created_at"],
        messages=[
            ChatMessage(
                id=str(row["id"]),
                role=str(row["role"]),
                content=str(row["content"]),
                created_at=row["created_at"],
            )
            for row in rows
        ],
    )


@router.delete("/chats/{chat_id}")
def delete_chat(
    chat_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    row = (
        db.execute(
            text("select id from chat where id = :chat_id and user_id = :user_id"),
            {"chat_id": chat_id, "user_id": user.user_id},
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Chat not found")
    db.execute(
        text(
            """
            delete from message_source
            where message_id in (select id from message where chat_id = :chat_id)
            """
        ),
        {"chat_id": chat_id},
    )
    db.execute(text("delete from message where chat_id = :chat_id"), {"chat_id": chat_id})
    db.execute(text("delete from chat where id = :chat_id"), {"chat_id": chat_id})
    db.commit()
    return {"status": "deleted"}


@router.get("/chats/{chat_id}/export")
def export_chat(
    chat_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    detail = get_chat(chat_id=chat_id, user=user, db=db)
    lines = [f"# Chat {detail.chat_id}", ""]
    for message in detail.messages:
        lines.append(f"{message.role.upper()}: {message.content}")
    return {"chat_id": detail.chat_id, "markdown": "\n".join(lines)}


@router.get("/admin/metrics", response_model=AdminMetricsResponse)
def admin_metrics(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminMetricsResponse:
    require_admin(user)
    ensure_runtime_schema(db)
    total_users = int(db.execute(text("select count(*) from app_user")).scalar_one())
    total_documents = int(db.execute(text("select count(*) from document")).scalar_one())
    queries_last_24h = int(
        db.execute(
            text(
                """
                select count(*)
                from usage_event
                where event_type = 'chat_ask' and created_at >= now() - interval '24 hours'
                """
            )
        ).scalar_one()
    )
    jobs_failed_last_24h = int(
        db.execute(
            text(
                """
                select count(*)
                from job
                where status = 'failed' and created_at >= now() - interval '24 hours'
                """
            )
        ).scalar_one()
    )
    return AdminMetricsResponse(
        total_users=total_users,
        total_documents=total_documents,
        queries_last_24h=queries_last_24h,
        jobs_failed_last_24h=jobs_failed_last_24h,
    )




