# ClinFlow — Comprehensive Implementation Plan

> **Strategy: Local First → Firebase Production**
> Every layer is built and tested locally (dev environment) before being deployed to Firebase + Supabase.

---

## Project Structure (Monorepo)

```
ClinFlow/
├── frontend/           # React JS (Vite)
├── backend/            # Python FastAPI
├── docs/               # All planning documents
├── .gitignore
└── README.md
```

---

## Layer 1: Database (PostgreSQL)

### Local Development
- Use a **local PostgreSQL** instance (via `psql` or Docker).
- Use **Alembic** (Python migration tool) to manage schema versions.

### Production
- Use **Supabase** (managed Postgres). Schema and migrations are applied the same way.

### Schema Design

#### `clinics` (Tenant isolation)
| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | Auto-generated |
| `name` | VARCHAR | Clinic name |
| `created_at` | TIMESTAMP | |

#### `users`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | Matches Supabase Auth user ID |
| `clinic_id` | UUID (FK → clinics) | Tenant linkage |
| `full_name` | VARCHAR | |
| `role` | ENUM | `owner`, `doctor`, `assistant` |
| `email` | VARCHAR | Unique |
| `created_at` | TIMESTAMP | |

#### `patients`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `clinic_id` | UUID (FK → clinics) | RLS enforcement key |
| `full_name` | VARCHAR | |
| `date_of_birth` | DATE | |
| `gender` | VARCHAR | |
| `contact_number` | VARCHAR | |
| `created_at` | TIMESTAMP | |

#### `documents` (Immutable raw sources)
| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `patient_id` | UUID (FK → patients) | |
| `clinic_id` | UUID (FK → clinics) | |
| `uploaded_by` | UUID (FK → users) | |
| `source_type` | ENUM | `image`, `pdf`, `telegram`, `manual` |
| `storage_path` | TEXT | Path in Supabase Storage / local filesystem |
| `raw_ocr_text` | TEXT | Extracted text — never modified after creation |
| `created_at` | TIMESTAMP | |

#### `structured_notes` (AI Output + Human Approval)
| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `document_id` | UUID (FK → documents) | Traceability to source |
| `patient_id` | UUID (FK → patients) | |
| `clinic_id` | UUID (FK → clinics) | |
| `status` | ENUM | `pending_review`, `approved`, `rejected` |
| `ai_output` | JSONB | Raw structured AI response |
| `approved_data` | JSONB | Doctor-edited and approved version |
| `missing_fields` | JSONB | Flagged missing information list |
| `confidence_score` | FLOAT | Overall AI confidence (0.0–1.0) |
| `reviewed_by` | UUID (FK → users) | Doctor who approved |
| `reviewed_at` | TIMESTAMP | |
| `created_at` | TIMESTAMP | |

#### `audit_logs`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `clinic_id` | UUID (FK) | |
| `user_id` | UUID (FK) | |
| `action` | VARCHAR | e.g., `upload`, `ocr_run`, `ai_structure`, `approved`, `rejected` |
| `entity_type` | VARCHAR | e.g., `document`, `structured_note` |
| `entity_id` | UUID | |
| `metadata` | JSONB | Extra context (IP, changes made, etc.) |
| `created_at` | TIMESTAMP | |

### Security (Supabase Production)
- Enable **Row-Level Security (RLS)** on every table using `clinic_id`.
- Policy: `clinic_id = auth.uid()` (via a user-clinic mapping function).

---

## Layer 2: Backend (Python FastAPI)

### Local Development Setup
```bash
cd backend/
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### `.env` (Local — never committed)
```
DATABASE_URL=postgresql://postgres:password@localhost:5432/clinflow
OPENAI_API_KEY=sk-...
SUPABASE_JWT_SECRET=your-supabase-jwt-secret
STORAGE_BACKEND=local          # Switch to "supabase" for production
LOCAL_STORAGE_PATH=./uploads
```

### Folder Structure
```
backend/
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Load .env settings
│   ├── database.py          # SQLAlchemy engine + session
│   ├── middleware/
│   │   └── auth.py          # JWT validation middleware
│   ├── models/
│   │   └── models.py        # SQLAlchemy ORM models
│   ├── schemas/
│   │   └── schemas.py       # Pydantic request/response models
│   ├── api/
│   │   ├── patients.py      # Patient CRUD endpoints
│   │   ├── documents.py     # Upload + ingestion endpoints
│   │   ├── notes.py         # Structured note + approval endpoints
│   │   └── auth.py          # Auth helpers
│   └── services/
│       ├── ocr_service.py   # OCR extraction logic
│       ├── ai_service.py    # OpenAI orchestration
│       ├── storage_service.py  # Local / Supabase storage abstraction
│       └── audit_service.py # Audit log writer
├── alembic/                 # DB migrations
├── requirements.txt
└── .env                     # Local only, never committed
```

### Key API Endpoints
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/verify` | Validate JWT, return user + clinic |
| `GET` | `/api/patients` | List all patients in clinic |
| `POST` | `/api/patients` | Create a new patient |
| `POST` | `/api/documents/upload` | Upload image/PDF/text note |
| `POST` | `/api/documents/{id}/process` | Trigger OCR + AI structuring |
| `GET` | `/api/notes/{patient_id}` | Get all structured notes for patient |
| `PATCH` | `/api/notes/{id}/approve` | Doctor approves/edits a note |
| `PATCH` | `/api/notes/{id}/reject` | Doctor rejects a note |
| `GET` | `/api/patients/{id}/timeline` | Full approved timeline for patient |
| `GET` | `/api/patients/{id}/handoff` | Safe Handoff Summary |

### Production Deployment (Firebase Cloud Functions)
- Wrap the FastAPI app using `functions-framework` or `mangum`.
- Use `firebase deploy --only functions` to deploy.
- Environment variables injected via Firebase Secret Manager.

---

## Layer 3: AI Layer (OpenAI API)

### Strategy
- AI is called **only when needed** (after OCR extracts text from a document).
- AI never modifies the source document — output is saved separately as `ai_output` in JSONB.
- Clinician approves before data becomes part of the official record.

### Local Development
- Uses the same OpenAI API key from `.env`.
- No special setup needed beyond `pip install openai`.

### Core AI Tasks & Prompts

#### Task 1: Clinical Note Structuring
Parses raw OCR text into structured fields:
```
Output format (JSON):
{
  "symptoms": ["..."],
  "medical_history": ["..."],
  "clinical_observations": ["..."],
  "diagnosis_assessment": "...",
  "medications": [{"name": "...", "dose": "...", "frequency": "..."}],
  "treatment_plan": "...",
  "follow_up": "...",
  "source_references": [{"field": "symptoms", "source_text": "patient said..."}]
}
```

#### Task 2: Missing Information Detection
After structuring, a second pass identifies gaps:
```
Output format (JSON):
{
  "missing_fields": [
    {
      "field": "follow_up",
      "reason": "No follow-up plan was documented for this complaint.",
      "severity": "high"
    }
  ]
}
```

#### Task 3: Safe Handoff Summary
A human-readable paragraph for doctors seeing a patient for the first time:
```
"Patient [Name], [Age], last seen on [Date] by [Doctor]. 
Primary complaint was [X]. Assessment was [Y]. 
Currently on [medications]. 
Follow-up plan: [Z]. 
Note: [missing field] was not documented."
```

### Hallucination Prevention Rules (Enforced in All Prompts)
1. Only extract information explicitly present in the source text.
2. Never infer, guess, or complete missing medical details.
3. If a field is not found, set it to `null` — do NOT fabricate a value.
4. Every extracted claim must include a `source_references` mapping.

---

## Layer 4: Frontend (React JS + Vite)

### Local Development Setup
```bash
cd frontend/
npm install
npm run dev       # Runs at http://localhost:5173
```

### `.env.local` (Local — never committed)
```
VITE_API_BASE_URL=http://localhost:8000
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
```

### Folder Structure
```
frontend/
├── src/
│   ├── main.jsx                  # App entry
│   ├── App.jsx                   # Router
│   ├── lib/
│   │   ├── supabaseClient.js     # Supabase Auth client
│   │   └── apiClient.js          # Axios client with JWT header
│   ├── pages/
│   │   ├── LoginPage.jsx
│   │   ├── DashboardPage.jsx     # List of all patients
│   │   ├── PatientDetailPage.jsx # Patient timeline
│   │   ├── UploadPage.jsx        # Upload notes/images
│   │   ├── ReviewPage.jsx        # AI Review Workspace
│   │   └── HandoffPage.jsx       # Safe Handoff Summary
│   ├── components/
│   │   ├── PatientCard.jsx
│   │   ├── NoteTimeline.jsx
│   │   ├── DocumentUploader.jsx
│   │   ├── ReviewWorkspace.jsx   # Side-by-side original vs AI output
│   │   ├── MissingFieldAlert.jsx
│   │   └── HandoffSummary.jsx
│   └── contexts/
│       └── AuthContext.jsx       # User + clinic state
├── public/
├── .env.local                    # Local only, never committed
└── package.json
```

### Key UI Screens
| Screen | Description |
|---|---|
| **Login** | Supabase Auth email/password login |
| **Dashboard** | Searchable list of all clinic patients |
| **Patient Detail** | Full approved timeline of visits |
| **Upload** | Drag-and-drop image/PDF or paste Telegram text |
| **Review Workspace** | Original image on the left; AI structured output on the right. Doctor edits and approves. |
| **Handoff Summary** | One-page AI-generated summary of the patient for quick transitions |

### Production Deployment (Firebase Hosting)
```bash
cd frontend/
npm run build
firebase deploy --only hosting
```

---

## Local Development Workflow (End-to-End)

```
1. Start Postgres locally
2. Start FastAPI backend:   cd backend && uvicorn app.main:app --reload
3. Start React frontend:    cd frontend && npm run dev
4. Open http://localhost:5173
5. Login → Dashboard → Upload Note → Review AI Output → Approve
```

---

## Firebase Deployment Checklist (When Ready)

- [ ] Create a Firebase project and enable Hosting + Cloud Functions (Blaze plan).
- [ ] Create a Supabase project and apply DB schema + RLS policies.
- [ ] Set all secrets in **Firebase Secret Manager** (OpenAI key, DB URL, Supabase JWT secret).
- [ ] Deploy backend: `firebase deploy --only functions`
- [ ] Build and deploy frontend: `npm run build && firebase deploy --only hosting`
- [ ] Update frontend `.env` to point to the live Firebase Function URL.
- [ ] Test end-to-end flow in production with a real note upload.
