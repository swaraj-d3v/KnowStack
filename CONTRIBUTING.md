# Contributing to KnowStack

## Workflow
1. Create a branch from `main` using a clear name (example: `feat/retrieval-rerank`).
2. Keep PRs focused to one concern.
3. Add or update tests for behavior changes.
4. Run local checks before opening a PR.

## Local Checks
```powershell
cd api
pytest -q
```

## PR Expectations
- Clear problem statement
- Brief design/approach notes
- Verification steps and test evidence
- API or schema changes called out explicitly

## Coding Standards
- Preserve tenant isolation guarantees
- Prefer explicit errors over silent failures
- Keep docs and endpoint references up to date
- Avoid committing local secrets, build outputs, or temp files
