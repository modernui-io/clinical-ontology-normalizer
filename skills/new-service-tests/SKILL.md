# Skill: New Service + Tests

## When to Use
- Introduce a new backend service or major feature logic.

## Workflow
1. Create service in `backend/app/services/`.
2. If persistence is needed, add model in `backend/app/models/` and schema in `backend/app/schemas/`.
3. Add or update API handler in `backend/app/api/`.
4. Add tests in `backend/tests/` (service + API if applicable).
5. Run quality gates: `make test`, `make lint`, `make typecheck`.

## Notes
- Favor single-responsibility service modules.
- Avoid hard-coded credentials or PHI in fixtures.
