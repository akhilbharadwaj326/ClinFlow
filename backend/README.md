# ClinFlow Backend

FastAPI backend for the ClinFlow clinical continuity-of-care platform.

## Local Development Setup

### 1. Prerequisites
- Python 3.11+
- PostgreSQL running locally
- Tesseract OCR installed ([Download](https://github.com/UB-Mannheim/tesseract/wiki))

### 2. Clone and Install
```bash
cd backend
python -m venv venv
venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
cp .env.example .env
# Edit .env with your local values:
# - DATABASE_URL
# - OPENAI_API_KEY
# - SUPABASE_JWT_SECRET
```

### 4. Create the Database
```bash
# In psql or pgAdmin, create a database named: clinflow
createdb clinflow
```

### 5. Run Migrations
```bash
alembic upgrade head
```

### 6. Start the Server
```bash
uvicorn app.main:app --reload --port 8000
```

API is now running at: http://localhost:8000
Interactive docs: http://localhost:8000/docs

## Project Structure
```
app/
├── main.py              # FastAPI entry point
├── config.py            # Environment settings
├── database.py          # SQLAlchemy engine
├── models/models.py     # ORM table definitions
├── schemas/schemas.py   # Pydantic request/response schemas
├── middleware/auth.py   # JWT validation
├── api/
│   ├── patients.py      # Patient CRUD
│   ├── documents.py     # Upload + OCR + AI processing
│   └── notes.py         # Review, approve, reject, handoff
└── services/
    ├── ocr_service.py   # Tesseract OCR
    ├── ai_service.py    # OpenAI prompts
    ├── storage_service.py  # File storage (local/Supabase)
    └── audit_service.py # Immutable audit logging
```

## Key API Endpoints
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/patients/` | List clinic patients |
| POST | `/api/patients/` | Create patient |
| POST | `/api/documents/upload` | Upload note/image |
| POST | `/api/documents/{id}/process` | Run OCR + AI |
| GET | `/api/notes/patient/{id}` | Get all notes |
| PATCH | `/api/notes/{id}/approve` | Approve note |
| PATCH | `/api/notes/{id}/reject` | Reject note |
| GET | `/api/notes/patient/{id}/handoff` | Safe Handoff Summary |
