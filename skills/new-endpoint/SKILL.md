# Skill: New API Endpoint (FastAPI)

## When to Use
- Add a new API endpoint to the backend.

## Workflow
1. Identify target router in `backend/app/api/`.
2. Add handler with `@router.<method>(...)`.
3. Wire to service layer in `backend/app/services/`.
4. Add/extend schema in `backend/app/schemas/` as needed.
5. Add tests under `backend/tests/`.
6. Update `CODEBASE_MAP.md` only if new domain or top-level flow changes.

## Notes
- Prefer thin handlers; push logic into services.
- Keep response schemas explicit.
