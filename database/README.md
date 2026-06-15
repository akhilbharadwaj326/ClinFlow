# ClinFlow — Database

This folder contains all raw SQL scripts for the ClinFlow PostgreSQL database.

## Scripts

| File | Purpose |
|---|---|
| `schema.sql` | Creates all tables, types, indexes, triggers |
| `seed_dev.sql` | Inserts sample data for local development |
| `rollback.sql` | Drops everything (dev only) |

---

## How to Run (Local Development)

### 1. Create the database
```bash
psql -U postgres -c "CREATE DATABASE clinflow;"
```

### 2. Apply the schema
```bash
psql -U postgres -d clinflow -f database/schema.sql
```

### 3. Load seed data (optional)
```bash
psql -U postgres -d clinflow -f database/seed_dev.sql
```

### 4. Verify tables were created
```bash
psql -U postgres -d clinflow -c "\dt"
```

---

## Using Alembic (Backend-driven migrations)

If you prefer to manage schema via Alembic (recommended for production):

```bash
cd backend
# Copy .env.example → .env with your DATABASE_URL
alembic upgrade head
```

This runs the migration in `backend/alembic/versions/001_initial_schema.py`.

---

## Schema Overview

```
clinics                 ← multi-tenant root
  └── users             ← clinic staff (owner/doctor/assistant)
  └── patients          ← patient records (soft-delete)
       └── documents    ← immutable raw uploads + OCR text
            └── structured_notes  ← AI output, pending/approved/rejected
audit_logs              ← append-only compliance trail
```

### Key Design Decisions

| Decision | Reason |
|---|---|
| UUID PKs | Prevent enumeration attacks; safe to expose in URLs |
| `clinic_id` on every table | Row-Level Security for multi-tenancy |
| Documents are immutable | Legal/clinical integrity of source records |
| `deleted_at` on patients | GDPR soft delete; preserves audit trail |
| JSONB for AI outputs | Flexible schema; GIN-indexed for fast queries |
| `TIMESTAMPTZ` everywhere | Timezone-aware; no ambiguity across regions |
| Append-only `audit_logs` | Compliance: actions can never be erased |
