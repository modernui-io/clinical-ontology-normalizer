# Development Guide

Quick start guide for new developers. For architecture overview, see [README.md](README.md).

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+ (or Docker)
- Redis (optional, for job queue)

## Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone <repo-url>
cd jan-14-2026

# Backend setup
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Frontend setup
cd ../frontend
npm install
```

### 2. Environment Configuration

```bash
# Backend
cp backend/.env.example backend/.env
# Edit backend/.env with your database credentials

# Frontend (optional)
cp frontend/.env.example frontend/.env.local
```

### 3. Database Setup

```bash
cd backend

# Run migrations
alembic upgrade head

# Seed with sample data (optional)
python -m app.scripts.seed_data
```

### 4. Start Development Servers

**Option A: Using Make (recommended)**
```bash
# Terminal 1: Backend
make dev-backend

# Terminal 2: Frontend
make dev-frontend

# Terminal 3: Background worker (optional)
make dev-worker
```

**Option B: Manual**
```bash
# Backend (from backend/)
uvicorn app.main:app --reload --port 8000

# Frontend (from frontend/)
npm run dev
```

### 5. Verify Setup

- Backend API: http://localhost:8000/docs
- Frontend: http://localhost:3000
- Health check: http://localhost:8000/health

## Common Tasks

### Running Tests

```bash
# Backend tests
cd backend
pytest                     # All tests
pytest tests/test_api.py   # Specific file
pytest -k "test_patient"   # By name pattern
pytest --cov=app           # With coverage

# Frontend tests
cd frontend
npm test                   # Unit tests
npm run test:e2e           # E2E tests (Playwright)
```

### Code Quality

```bash
# Backend
cd backend
ruff check .               # Linting
ruff format .              # Formatting
mypy app                   # Type checking

# Frontend
cd frontend
npm run lint               # ESLint
npm run lint:fix           # Auto-fix
npm run typecheck          # TypeScript
```

### Database Migrations

```bash
cd backend

# Create new migration
alembic revision --autogenerate -m "Add new table"

# Apply migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1

# View migration history
alembic history
```

### Adding New API Endpoint

1. Create router in `backend/app/api/<domain>.py`
2. Create service in `backend/app/services/<domain>_service.py`
3. Add router to `backend/app/api/__init__.py`
4. Include router in `backend/app/main.py`

### Adding New Frontend Page

1. Create page in `frontend/src/app/<route>/page.tsx`
2. Add API calls to `frontend/src/lib/api.ts`
3. Create components in `frontend/src/components/`

## Debugging

### VS Code

The project includes VS Code debug configurations. Press F5 and select:
- **Backend: FastAPI** - Debug the API server
- **Backend: Current Test File** - Debug the open test file
- **Frontend: Next.js** - Debug the frontend
- **Full Stack** - Debug both simultaneously

### Common Issues

**Port already in use**
```bash
# Find and kill process on port 8000
lsof -i :8000
kill -9 <PID>
```

**Database connection failed**
- Check PostgreSQL is running
- Verify DATABASE_URL in .env
- Run `alembic upgrade head`

**Module not found**
```bash
cd backend
pip install -e ".[dev]"
```

**Frontend build errors**
```bash
cd frontend
rm -rf node_modules .next
npm install
```

## Project Structure

```
jan-14-2026/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routes
│   │   ├── core/         # Config, database, security
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic schemas
│   │   └── services/     # Business logic
│   ├── tests/            # Pytest tests
│   └── alembic/          # Database migrations
├── frontend/
│   ├── src/
│   │   ├── app/          # Next.js pages (App Router)
│   │   ├── components/   # React components
│   │   └── lib/          # Utilities and API client
│   └── __tests__/        # Jest tests
└── .vscode/              # VS Code configuration
```

## Getting Help

- Check existing issues on GitHub
- Ask in the team Slack channel
- Review the API docs at http://localhost:8000/docs
