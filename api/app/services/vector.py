import hashlib
import math
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams

from app.core.config import settings


def embed_text(text: str, dim: int | None = None) -> list[float]:
    size = dim or settings.embedding_dim
    digest = hashlib.blake2b(text.encode("utf-8"), digest_size=size).digest()
    vector = [(byte / 127.5) - 1.0 for byte in digest]
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def _client() -> QdrantClient | None:
    if not settings.qdrant_url:
        return None
    try:
        return QdrantClient(url=settings.qdrant_url, timeout=5.0)
    except Exception:
        return None


def ensure_collection() -> bool:
    client = _client()
    if not client:
        return False
    try:
        collections = client.get_collections().collections
        names = {item.name for item in collections}
        if settings.qdrant_collection not in names:
            client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=VectorParams(size=settings.embedding_dim, distance=Distance.COSINE),
            )
        return True
    except Exception:
        return False


def upsert_chunk_vectors(rows: list[dict[str, Any]]) -> bool:
    if not rows:
        return True
    client = _client()
    if not client:
        return False
    if not ensure_collection():
        return False
    points = []
    for row in rows:
        point_id = int(row["chunk_id"])
        vector = embed_text(str(row["content"]))
        points.append(
            PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "user_id": str(row["user_id"]),
                    "document_id": str(row["document_id"]),
                },
            )
        )
    try:
        client.upsert(collection_name=settings.qdrant_collection, points=points)
        return True
    except Exception:
        return False


def query_vectors(user_id: str, question: str, limit: int = 10) -> dict[int, float]:
    client = _client()
    if not client:
        return {}
    if not ensure_collection():
        return {}
    query = embed_text(question)
    try:
        hits = client.search(
            collection_name=settings.qdrant_collection,
            query_vector=query,
            query_filter={"must": [{"key": "user_id", "match": {"value": user_id}}]},
            limit=limit,
        )
    except Exception:
        return {}
    return {int(hit.id): float(hit.score) for hit in hits}
