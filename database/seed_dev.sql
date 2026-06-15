-- =============================================================================
-- ClinFlow — Development Seed Data
-- Run AFTER schema.sql to populate the database with test data.
-- DO NOT run in production.
-- =============================================================================

-- ─── Clinic ───────────────────────────────────────────────────────────────────
INSERT INTO clinics (id, name, address, phone, email)
VALUES (
    'a0000000-0000-0000-0000-000000000001',
    'Sunrise Medical Clinic',
    '12 MG Road, Bengaluru, Karnataka 560001',
    '+91-80-1234-5678',
    'admin@sunriseclinic.in'
);

-- ─── Users ────────────────────────────────────────────────────────────────────
-- Note: Supabase Auth handles passwords. These UUIDs must match
-- the auth.users table in your Supabase project.
INSERT INTO users (id, clinic_id, full_name, email, role)
VALUES
    ('b0000000-0000-0000-0000-000000000001',
     'a0000000-0000-0000-0000-000000000001',
     'Dr. Priya Sharma', 'priya@sunriseclinic.in', 'owner'),

    ('b0000000-0000-0000-0000-000000000002',
     'a0000000-0000-0000-0000-000000000001',
     'Dr. Arjun Mehta', 'arjun@sunriseclinic.in', 'doctor'),

    ('b0000000-0000-0000-0000-000000000003',
     'a0000000-0000-0000-0000-000000000001',
     'Neha Kumar', 'neha@sunriseclinic.in', 'assistant');

-- ─── Patients ─────────────────────────────────────────────────────────────────
INSERT INTO patients (id, clinic_id, full_name, date_of_birth, gender, contact_number, blood_group, allergies, created_by)
VALUES
    ('c0000000-0000-0000-0000-000000000001',
     'a0000000-0000-0000-0000-000000000001',
     'Ramesh Nair', '1978-04-12', 'male', '+91-9876543210', 'B+',
     ARRAY['Penicillin', 'Dust'],
     'b0000000-0000-0000-0000-000000000002'),

    ('c0000000-0000-0000-0000-000000000002',
     'a0000000-0000-0000-0000-000000000001',
     'Sunita Patel', '1990-11-03', 'female', '+91-9123456789', 'O+',
     ARRAY[]::TEXT[],
     'b0000000-0000-0000-0000-000000000002'),

    ('c0000000-0000-0000-0000-000000000003',
     'a0000000-0000-0000-0000-000000000001',
     'Mohammed Farooq', '1965-07-22', 'male', '+91-9988776655', 'A-',
     ARRAY['Sulfa drugs'],
     'b0000000-0000-0000-0000-000000000001');

-- ─── Documents ────────────────────────────────────────────────────────────────
INSERT INTO documents (id, patient_id, clinic_id, uploaded_by, source_type, raw_ocr_text, ocr_processed_at)
VALUES
    ('d0000000-0000-0000-0000-000000000001',
     'c0000000-0000-0000-0000-000000000001',
     'a0000000-0000-0000-0000-000000000001',
     'b0000000-0000-0000-0000-000000000002',
     'manual',
     'Patient: Ramesh Nair, 45M. Complaints: chest pain on exertion for 2 weeks. BP 145/92. History of hypertension. On Amlodipine 5mg OD. Assessment: Hypertensive heart disease, rule out angina. ECG ordered. Follow-up 1 week.',
     NOW()),

    ('d0000000-0000-0000-0000-000000000002',
     'c0000000-0000-0000-0000-000000000002',
     'a0000000-0000-0000-0000-000000000001',
     'b0000000-0000-0000-0000-000000000002',
     'manual',
     'Patient: Sunita Patel, 33F. Presenting with fever 102F x 3 days, sore throat. No travel history. Throat: red, mild exudate. Tonsils enlarged. Provisional: Acute tonsillitis. Prescribed Amoxicillin 500mg TDS x 5 days, Paracetamol 500mg SOS. Review if no improvement in 3 days.',
     NOW());

-- ─── Structured Notes ─────────────────────────────────────────────────────────
INSERT INTO structured_notes (id, document_id, patient_id, clinic_id, status, ai_output, approved_data, missing_fields, confidence_score, reviewed_by, reviewed_at)
VALUES
    -- Approved note for Ramesh
    ('e0000000-0000-0000-0000-000000000001',
     'd0000000-0000-0000-0000-000000000001',
     'c0000000-0000-0000-0000-000000000001',
     'a0000000-0000-0000-0000-000000000001',
     'approved',
     '{"symptoms": ["chest pain on exertion"], "medical_history": ["hypertension"], "clinical_observations": ["BP 145/92"], "diagnosis_assessment": "Hypertensive heart disease, rule out angina", "medications": [{"name": "Amlodipine", "dose": "5mg", "frequency": "OD"}], "treatment_plan": "ECG ordered", "follow_up": "1 week", "source_references": [{"field": "symptoms", "source_text": "chest pain on exertion for 2 weeks"}, {"field": "diagnosis_assessment", "source_text": "Hypertensive heart disease, rule out angina"}]}',
     '{"symptoms": ["chest pain on exertion"], "medical_history": ["hypertension"], "clinical_observations": ["BP 145/92"], "diagnosis_assessment": "Hypertensive heart disease, rule out angina", "medications": [{"name": "Amlodipine", "dose": "5mg", "frequency": "OD"}], "treatment_plan": "ECG ordered", "follow_up": "1 week"}',
     '{"missing_fields": [{"field": "smoking_history", "reason": "Relevant for cardiac risk stratification", "severity": "medium"}, {"field": "family_history", "reason": "Relevant for coronary artery disease risk", "severity": "low"}]}',
     0.820,
     'b0000000-0000-0000-0000-000000000002',
     NOW() - INTERVAL '2 hours'),

    -- Pending note for Sunita
    ('e0000000-0000-0000-0000-000000000002',
     'd0000000-0000-0000-0000-000000000002',
     'c0000000-0000-0000-0000-000000000002',
     'a0000000-0000-0000-0000-000000000001',
     'pending_review',
     '{"symptoms": ["fever 102F for 3 days", "sore throat"], "medical_history": null, "clinical_observations": ["throat red with mild exudate", "tonsils enlarged"], "diagnosis_assessment": "Acute tonsillitis", "medications": [{"name": "Amoxicillin", "dose": "500mg", "frequency": "TDS x 5 days"}, {"name": "Paracetamol", "dose": "500mg", "frequency": "SOS"}], "treatment_plan": null, "follow_up": "Review if no improvement in 3 days", "source_references": [{"field": "symptoms", "source_text": "fever 102F x 3 days, sore throat"}, {"field": "diagnosis_assessment", "source_text": "Provisional: Acute tonsillitis"}]}',
     NULL,
     '{"missing_fields": [{"field": "medical_history", "reason": "No prior illness documented; relevant for antibiotic choice", "severity": "high"}, {"field": "treatment_plan", "reason": "No clear treatment plan beyond medications", "severity": "medium"}]}',
     0.750,
     NULL,
     NULL);

-- ─── Audit Logs ───────────────────────────────────────────────────────────────
INSERT INTO audit_logs (clinic_id, user_id, action, entity_type, entity_id, metadata)
VALUES
    ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000002', 'upload',       'document',        'd0000000-0000-0000-0000-000000000001', '{"source_type": "manual"}'),
    ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000002', 'ocr_run',      'document',        'd0000000-0000-0000-0000-000000000001', '{"chars_extracted": 248}'),
    ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000002', 'ai_structure', 'structured_note', 'e0000000-0000-0000-0000-000000000001', '{"model": "gpt-4o"}'),
    ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000002', 'approved',     'structured_note', 'e0000000-0000-0000-0000-000000000001', '{"reviewed_by_role": "doctor"}'),
    ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000002', 'upload',       'document',        'd0000000-0000-0000-0000-000000000002', '{"source_type": "manual"}'),
    ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000002', 'ai_structure', 'structured_note', 'e0000000-0000-0000-0000-000000000002', '{"model": "gpt-4o"}');
