# Architecture Plan

## Modules Mapped to Implementation
1. Auth + SaaS tenancy: JWT middleware + role checks + user isolation filters.
2. Upload: signed upload + hashing + dedupe + version links.
3. Processing: parser/cleaner/chunker pipeline in worker.
4. Embeddings: batch embedding + qdrant upsert.
5. Retrieval: hybrid search + rerank + query rewrite.
6. Chat: grounded answer generation + streaming.
7. Citations: page/section/snippet surfacing.
8. History: chat/message/source persistence.
9. Admin: usage and reliability metrics.
10. Eval: offline benchmarks for retrieval and grounding.
11. Deployment: dockerized services and environment-based config.

## Immediate Next Code Tasks
1. Add SQLAlchemy models and migrations.
2. Add queue producer in `/v1/documents` and consumer in worker.
3. Implement PDF/TXT extraction and heading-aware chunker.
4. Add Qdrant collection bootstrap and upsert logic.
5. Implement `/v1/chat/ask` retrieval and citation grounding.
