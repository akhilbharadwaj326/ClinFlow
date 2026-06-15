-- =============================================================================
-- ClinFlow Database Schema
-- PostgreSQL 15+
--
-- DESIGN PRINCIPLES:
--   1. Multi-tenant: every row is scoped to a clinic_id
--   2. UUID primary keys: no sequential IDs to prevent enumeration attacks
--   3. Immutable source documents: once written, never modified
--   4. Append-only audit log: no deletes or updates ever
--   5. Soft deletes on patients (GDPR right-to-erasure friendly)
--   6. JSONB for AI outputs: flexible schema, GIN-indexed for fast queries
--   7. Timestamptz (with timezone) for all timestamps
--   8. Check constraints enforce business rules at the DB level
-- =============================================================================

-- ─── Extensions ───────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";   -- uuid_generate_v4()
CREATE EXTENSION IF NOT EXISTS "pgcrypto";    -- future password hashing if needed

-- ─── Shared trigger: auto-update updated_at ───────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ─── Enum Types ───────────────────────────────────────────────────────────────
CREATE TYPE user_role            AS ENUM ('owner', 'doctor', 'assistant');
CREATE TYPE document_source_type AS ENUM ('image', 'pdf', 'telegram', 'manual');
CREATE TYPE note_status          AS ENUM ('pending_review', 'approved', 'rejected');

-- =============================================================================
-- TABLE: clinics
-- The root multi-tenant entity. Every other table references this.
-- =============================================================================
CREATE TABLE clinics (
    id          UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(255)  NOT NULL CHECK (TRIM(name) <> ''),
    address     TEXT,
    phone       VARCHAR(30),
    email       VARCHAR(255),
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  clinics            IS 'Multi-tenant root: every record belongs to exactly one clinic.';
COMMENT ON COLUMN clinics.id         IS 'Primary key — UUID v4.';
COMMENT ON COLUMN clinics.name       IS 'Display name of the clinic.';

CREATE TRIGGER clinics_set_updated_at
  BEFORE UPDATE ON clinics
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- TABLE: users
-- Clinic staff. Authentication is handled by Supabase Auth;
-- this table stores the application-level profile and role.
-- =============================================================================
CREATE TABLE users (
    id          UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    clinic_id   UUID          NOT NULL REFERENCES clinics(id) ON DELETE RESTRICT,
    full_name   VARCHAR(255)  NOT NULL CHECK (TRIM(full_name) <> ''),
    email       VARCHAR(255)  NOT NULL,
    role        user_role     NOT NULL DEFAULT 'doctor',
    is_active   BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    CONSTRAINT users_email_unique UNIQUE (email)
);

COMMENT ON TABLE  users              IS 'Clinic staff. Auth is managed by Supabase; this table holds role and clinic membership.';
COMMENT ON COLUMN users.clinic_id    IS 'FK — which clinic this user belongs to.';
COMMENT ON COLUMN users.role         IS 'owner: full admin | doctor: clinical access | assistant: upload-only.';
COMMENT ON COLUMN users.is_active    IS 'Soft-disable a user without deleting their audit trail.';

CREATE TRIGGER users_set_updated_at
  BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- TABLE: patients
-- Core patient identity record. Soft-deleted for GDPR compliance.
-- =============================================================================
CREATE TABLE patients (
    id              UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    clinic_id       UUID          NOT NULL REFERENCES clinics(id) ON DELETE RESTRICT,
    full_name       VARCHAR(255)  NOT NULL CHECK (TRIM(full_name) <> ''),
    date_of_birth   DATE,
    gender          VARCHAR(30)   CHECK (gender IN ('male', 'female', 'other', 'prefer_not_to_say')),
    contact_number  VARCHAR(30),
    email           VARCHAR(255),
    blood_group     VARCHAR(5)    CHECK (blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
    allergies       TEXT[],                        -- array of allergy strings
    notes           TEXT,                          -- free-form general notes
    created_by      UUID          REFERENCES users(id) ON DELETE SET NULL,
    deleted_at      TIMESTAMPTZ,                   -- NULL = active, non-NULL = soft-deleted
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  patients              IS 'Core patient record. Soft-deleted via deleted_at for GDPR.';
COMMENT ON COLUMN patients.clinic_id    IS 'Tenant isolation: patients belong exclusively to one clinic.';
COMMENT ON COLUMN patients.allergies    IS 'Postgres text[] — zero or more allergy strings.';
COMMENT ON COLUMN patients.deleted_at   IS 'NULL means active. Set to a timestamp to soft-delete.';

CREATE TRIGGER patients_set_updated_at
  BEFORE UPDATE ON patients
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- TABLE: documents
-- Immutable raw source records — a snapshot of what was uploaded.
-- NEVER modified after creation. raw_ocr_text is written once after OCR.
-- =============================================================================
CREATE TABLE documents (
    id                  UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id          UUID          NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    clinic_id           UUID          NOT NULL REFERENCES clinics(id)  ON DELETE RESTRICT,
    uploaded_by         UUID          REFERENCES users(id) ON DELETE SET NULL,
    source_type         document_source_type NOT NULL,
    original_filename   VARCHAR(500),
    storage_path        TEXT,                      -- local path or Supabase Storage object key
    file_size_bytes     INTEGER       CHECK (file_size_bytes IS NULL OR file_size_bytes > 0),
    mime_type           VARCHAR(100),
    raw_ocr_text        TEXT,                      -- populated once by OCR service; never changed again
    ocr_processed_at    TIMESTAMPTZ,               -- NULL means OCR has not yet run
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW()
    -- No updated_at: documents are intentionally immutable.
);

COMMENT ON TABLE  documents                  IS 'Immutable source records. Written once on upload; OCR text added once; never modified again.';
COMMENT ON COLUMN documents.storage_path     IS 'Relative file path (dev: local disk; prod: Supabase Storage key).';
COMMENT ON COLUMN documents.raw_ocr_text     IS 'Output of OCR pass. Written once; must never be edited.';
COMMENT ON COLUMN documents.ocr_processed_at IS 'Timestamp of successful OCR run. NULL = pending.';

-- =============================================================================
-- TABLE: structured_notes
-- AI-generated structured extraction linked to a source document.
-- Status lifecycle: pending_review → approved | rejected
-- ai_output is ALWAYS preserved for traceability.
-- approved_data is the doctor-edited trusted version.
-- =============================================================================
CREATE TABLE structured_notes (
    id                UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id       UUID          NOT NULL REFERENCES documents(id) ON DELETE RESTRICT,
    patient_id        UUID          NOT NULL REFERENCES patients(id)  ON DELETE RESTRICT,
    clinic_id         UUID          NOT NULL REFERENCES clinics(id)   ON DELETE RESTRICT,
    status            note_status   NOT NULL DEFAULT 'pending_review',
    ai_output         JSONB,                     -- raw AI extraction (immutable after write)
    approved_data     JSONB,                     -- doctor-edited + approved version
    missing_fields    JSONB,                     -- AI-detected missing clinical fields
    confidence_score  NUMERIC(4,3)  CHECK (confidence_score IS NULL OR confidence_score BETWEEN 0 AND 1),
    reviewed_by       UUID          REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at       TIMESTAMPTZ,
    created_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    -- Business rule: reviewed_by and reviewed_at must be set together
    CONSTRAINT review_fields_consistent CHECK (
        (reviewed_by IS NULL AND reviewed_at IS NULL)
        OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)
    )
);

COMMENT ON TABLE  structured_notes                IS 'AI-extracted clinical note. Requires doctor approval before entering trusted record.';
COMMENT ON COLUMN structured_notes.ai_output      IS 'Raw GPT-4o JSON output. Never modified after creation.';
COMMENT ON COLUMN structured_notes.approved_data  IS 'Doctor-reviewed and edited version. The clinical source of truth.';
COMMENT ON COLUMN structured_notes.missing_fields IS 'Fields flagged as clinically important but absent from the source.';
COMMENT ON COLUMN structured_notes.confidence_score IS '0.0–1.0 completeness estimate based on source_references coverage.';

CREATE TRIGGER structured_notes_set_updated_at
  BEFORE UPDATE ON structured_notes
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- TABLE: audit_logs
-- Append-only compliance log. NEVER updated or deleted.
-- Tracks every significant action for regulatory traceability.
-- =============================================================================
CREATE TABLE audit_logs (
    id           UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    clinic_id    UUID          REFERENCES clinics(id)  ON DELETE SET NULL,
    user_id      UUID          REFERENCES users(id)    ON DELETE SET NULL,
    action       VARCHAR(100)  NOT NULL,               -- e.g. 'upload', 'approved', 'rejected'
    entity_type  VARCHAR(100),                         -- e.g. 'document', 'structured_note'
    entity_id    UUID,
    metadata     JSONB         NOT NULL DEFAULT '{}',
    ip_address   INET,
    created_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW()
    -- No updated_at: audit logs are intentionally append-only and immutable.
);

COMMENT ON TABLE  audit_logs            IS 'Append-only compliance log. No rows are ever updated or deleted.';
COMMENT ON COLUMN audit_logs.action     IS 'What happened: upload | ocr_run | ai_structure | approved | rejected | login | logout.';
COMMENT ON COLUMN audit_logs.entity_id  IS 'UUID of the affected row (document, note, patient, etc.).';
COMMENT ON COLUMN audit_logs.metadata   IS 'Arbitrary JSON context for the action (e.g. filename, IP, diff summary).';


-- =============================================================================
-- INDEXES
-- Follow: FK columns, frequently filtered columns, JSONB columns.
-- =============================================================================

-- users
CREATE INDEX idx_users_clinic_id    ON users(clinic_id);
CREATE INDEX idx_users_email        ON users(email);

-- patients
CREATE INDEX idx_patients_clinic_id     ON patients(clinic_id);
CREATE INDEX idx_patients_name_search   ON patients(clinic_id, LOWER(full_name));  -- case-insensitive name search
CREATE INDEX idx_patients_active        ON patients(clinic_id) WHERE deleted_at IS NULL;

-- documents
CREATE INDEX idx_documents_patient_id   ON documents(patient_id);
CREATE INDEX idx_documents_clinic_id    ON documents(clinic_id);
CREATE INDEX idx_documents_created_at   ON documents(patient_id, created_at DESC);

-- structured_notes
CREATE INDEX idx_notes_patient_id       ON structured_notes(patient_id);
CREATE INDEX idx_notes_clinic_id        ON structured_notes(clinic_id);
CREATE INDEX idx_notes_status           ON structured_notes(clinic_id, status);
CREATE INDEX idx_notes_reviewed_at      ON structured_notes(patient_id, reviewed_at DESC);

-- JSONB GIN indexes — allow fast key/value lookup inside JSON columns
CREATE INDEX idx_notes_ai_output_gin       ON structured_notes USING GIN(ai_output);
CREATE INDEX idx_notes_approved_data_gin   ON structured_notes USING GIN(approved_data);
CREATE INDEX idx_notes_missing_fields_gin  ON structured_notes USING GIN(missing_fields);

-- audit_logs
CREATE INDEX idx_audit_clinic_id     ON audit_logs(clinic_id);
CREATE INDEX idx_audit_user_id       ON audit_logs(user_id);
CREATE INDEX idx_audit_entity        ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_created_at    ON audit_logs(created_at DESC);
CREATE INDEX idx_audit_metadata_gin  ON audit_logs USING GIN(metadata);
