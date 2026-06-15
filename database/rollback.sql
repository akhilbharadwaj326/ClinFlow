-- =============================================================================
-- ClinFlow — Rollback / Teardown Script
-- Drops everything created by schema.sql in the correct dependency order.
-- WARNING: Destroys ALL data. Only use in development.
-- =============================================================================

-- Drop triggers first
DROP TRIGGER IF EXISTS structured_notes_set_updated_at ON structured_notes;
DROP TRIGGER IF EXISTS patients_set_updated_at          ON patients;
DROP TRIGGER IF EXISTS users_set_updated_at             ON users;
DROP TRIGGER IF EXISTS clinics_set_updated_at           ON clinics;

-- Drop tables (reverse dependency order)
DROP TABLE IF EXISTS audit_logs       CASCADE;
DROP TABLE IF EXISTS structured_notes CASCADE;
DROP TABLE IF EXISTS documents        CASCADE;
DROP TABLE IF EXISTS patients         CASCADE;
DROP TABLE IF EXISTS users            CASCADE;
DROP TABLE IF EXISTS clinics          CASCADE;

-- Drop types
DROP TYPE IF EXISTS note_status          CASCADE;
DROP TYPE IF EXISTS document_source_type CASCADE;
DROP TYPE IF EXISTS user_role            CASCADE;

-- Drop function
DROP FUNCTION IF EXISTS set_updated_at CASCADE;
