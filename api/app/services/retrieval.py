from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.vector import query_vectors


def rewrite_query(question: str) -> str:
    return " ".join(question.strip().lower().split())


def hybrid_retrieve(
    db: Session,
    user_id: str,
    question: str,
    document_id: str | None = None,
) -> list[dict[str, Any]]:
    normalized = rewrite_query(question)
    query_terms = [term for term in normalized.split() if len(term) >= 3][:10]

    base_query = """
        select c.id as chunk_id, c.document_id, d.filename as document_name, c.page, c.section, c.content
        from chunk c
        join document d on d.id = c.document_id
        where c.user_id = :user_id
    """
    params: dict[str, Any] = {"user_id": user_id, "limit": settings.retrieval_limit}
    if document_id:
        base_query += " and c.document_id = :document_id"
        params["document_id"] = document_id
    base_query += " order by c.created_at desc limit :limit"

    rows = db.execute(text(base_query), params).mappings().all()

    vector_scores = query_vectors(user_id=user_id, question=normalized, limit=20)
    scored: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        row_dict = dict(row)
        content = str(row_dict["content"]).lower()
        keyword_score = float(sum(1 for term in query_terms if term in content))
        vector_score = float(vector_scores.get(int(row_dict["chunk_id"]), 0.0))
        score = keyword_score + vector_score
        if score > 0:
            scored.append((score, row_dict))

    scored.sort(key=lambda item: item[0], reverse=True)
    if scored:
        return [item[1] for item in scored[: settings.rerank_top_k]]

    fallback_query = """
        select c.id as chunk_id, c.document_id, d.filename as document_name, c.page, c.section, c.content
        from chunk c
        join document d on d.id = c.document_id
        where c.user_id = :user_id and d.status = 'processed'
    """
    fallback_params: dict[str, Any] = {"user_id": user_id, "limit": settings.rerank_top_k}
    if document_id:
        fallback_query += " and c.document_id = :document_id"
        fallback_params["document_id"] = document_id
    fallback_query += " order by d.created_at desc, c.chunk_index asc limit :limit"

    fallback_rows = db.execute(text(fallback_query), fallback_params).mappings().all()
    return [dict(row) for row in fallback_rows]