"""Initial schema: clinics, users, patients, documents, structured_notes, audit_logs

Revision ID: 001
Revises: 
Create Date: 2026-06-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET, ARRAY
import sqlalchemy.dialects.postgresql as pg

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extensions ──────────────────────────────────────────────────────────
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # ── Trigger function ────────────────────────────────────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
          NEW.updated_at = NOW();
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)

    # ── Enum types ──────────────────────────────────────────────────────────
    user_role = pg.ENUM('owner', 'doctor', 'assistant', name='user_role')
    user_role.create(op.get_bind())

    doc_source = pg.ENUM('image', 'pdf', 'telegram', 'manual', name='document_source_type')
    doc_source.create(op.get_bind())

    note_status = pg.ENUM('pending_review', 'approved', 'rejected', name='note_status')
    note_status.create(op.get_bind())

    # ── clinics ─────────────────────────────────────────────────────────────
    op.create_table(
        'clinics',
        sa.Column('id',         UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name',       sa.String(255),  nullable=False),
        sa.Column('address',    sa.Text()),
        sa.Column('phone',      sa.String(30)),
        sa.Column('email',      sa.String(255)),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )
    op.execute("CREATE TRIGGER clinics_set_updated_at BEFORE UPDATE ON clinics FOR EACH ROW EXECUTE FUNCTION set_updated_at()")

    # ── users ───────────────────────────────────────────────────────────────
    op.create_table(
        'users',
        sa.Column('id',         UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('clinic_id',  UUID(as_uuid=True), sa.ForeignKey('clinics.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('full_name',  sa.String(255), nullable=False),
        sa.Column('email',      sa.String(255), nullable=False),
        sa.Column('role',       sa.Enum('owner', 'doctor', 'assistant', name='user_role'), nullable=False, server_default='doctor'),
        sa.Column('is_active',  sa.Boolean(), nullable=False, server_default=sa.text('TRUE')),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.UniqueConstraint('email', name='users_email_unique'),
    )
    op.execute("CREATE TRIGGER users_set_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION set_updated_at()")

    # ── patients ─────────────────────────────────────────────────────────────
    op.create_table(
        'patients',
        sa.Column('id',             UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('clinic_id',      UUID(as_uuid=True), sa.ForeignKey('clinics.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('full_name',      sa.String(255), nullable=False),
        sa.Column('date_of_birth',  sa.Date()),
        sa.Column('gender',         sa.String(30)),
        sa.Column('contact_number', sa.String(30)),
        sa.Column('email',          sa.String(255)),
        sa.Column('blood_group',    sa.String(5)),
        sa.Column('allergies',      ARRAY(sa.Text())),
        sa.Column('notes',          sa.Text()),
        sa.Column('created_by',     UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('deleted_at',     sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at',     sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at',     sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )
    op.execute("CREATE TRIGGER patients_set_updated_at BEFORE UPDATE ON patients FOR EACH ROW EXECUTE FUNCTION set_updated_at()")

    # ── documents ─────────────────────────────────────────────────────────────
    op.create_table(
        'documents',
        sa.Column('id',                UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('patient_id',        UUID(as_uuid=True), sa.ForeignKey('patients.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('clinic_id',         UUID(as_uuid=True), sa.ForeignKey('clinics.id',  ondelete='RESTRICT'), nullable=False),
        sa.Column('uploaded_by',       UUID(as_uuid=True), sa.ForeignKey('users.id',    ondelete='SET NULL'), nullable=True),
        sa.Column('source_type',       sa.Enum('image', 'pdf', 'telegram', 'manual', name='document_source_type'), nullable=False),
        sa.Column('original_filename', sa.String(500)),
        sa.Column('storage_path',      sa.Text()),
        sa.Column('file_size_bytes',   sa.Integer()),
        sa.Column('mime_type',         sa.String(100)),
        sa.Column('raw_ocr_text',      sa.Text()),
        sa.Column('ocr_processed_at',  sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at',        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )

    # ── structured_notes ──────────────────────────────────────────────────────
    op.create_table(
        'structured_notes',
        sa.Column('id',               UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('document_id',      UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('patient_id',       UUID(as_uuid=True), sa.ForeignKey('patients.id',  ondelete='RESTRICT'), nullable=False),
        sa.Column('clinic_id',        UUID(as_uuid=True), sa.ForeignKey('clinics.id',   ondelete='RESTRICT'), nullable=False),
        sa.Column('status',           sa.Enum('pending_review', 'approved', 'rejected', name='note_status'), nullable=False, server_default='pending_review'),
        sa.Column('ai_output',        JSONB()),
        sa.Column('approved_data',    JSONB()),
        sa.Column('missing_fields',   JSONB()),
        sa.Column('confidence_score', sa.Numeric(4, 3)),
        sa.Column('reviewed_by',      UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reviewed_at',      sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at',       sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at',       sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )
    op.execute("CREATE TRIGGER structured_notes_set_updated_at BEFORE UPDATE ON structured_notes FOR EACH ROW EXECUTE FUNCTION set_updated_at()")

    # ── audit_logs ────────────────────────────────────────────────────────────
    op.create_table(
        'audit_logs',
        sa.Column('id',          UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('clinic_id',   UUID(as_uuid=True), sa.ForeignKey('clinics.id', ondelete='SET NULL'), nullable=True),
        sa.Column('user_id',     UUID(as_uuid=True), sa.ForeignKey('users.id',   ondelete='SET NULL'), nullable=True),
        sa.Column('action',      sa.String(100), nullable=False),
        sa.Column('entity_type', sa.String(100)),
        sa.Column('entity_id',   UUID(as_uuid=True)),
        sa.Column('metadata',    JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('ip_address',  INET()),
        sa.Column('created_at',  sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )

    # ── Indexes ───────────────────────────────────────────────────────────────
    op.create_index('idx_users_clinic_id',   'users',   ['clinic_id'])
    op.create_index('idx_users_email',        'users',   ['email'])

    op.create_index('idx_patients_clinic_id', 'patients', ['clinic_id'])
    op.create_index('idx_patients_active',    'patients', ['clinic_id'],
                    postgresql_where=sa.text('deleted_at IS NULL'))

    op.create_index('idx_documents_patient_id', 'documents', ['patient_id'])
    op.create_index('idx_documents_clinic_id',  'documents', ['clinic_id'])

    op.create_index('idx_notes_patient_id', 'structured_notes', ['patient_id'])
    op.create_index('idx_notes_clinic_id',  'structured_notes', ['clinic_id'])
    op.create_index('idx_notes_status',     'structured_notes', ['clinic_id', 'status'])

    op.create_index('idx_notes_ai_output_gin',     'structured_notes', ['ai_output'],     postgresql_using='gin')
    op.create_index('idx_notes_approved_data_gin',  'structured_notes', ['approved_data'], postgresql_using='gin')

    op.create_index('idx_audit_clinic_id',  'audit_logs', ['clinic_id'])
    op.create_index('idx_audit_entity',     'audit_logs', ['entity_type', 'entity_id'])
    op.create_index('idx_audit_created_at', 'audit_logs', [sa.text('created_at DESC')])


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('structured_notes')
    op.drop_table('documents')
    op.drop_table('patients')
    op.drop_table('users')
    op.drop_table('clinics')

    op.execute("DROP FUNCTION IF EXISTS set_updated_at CASCADE")
    op.execute("DROP TYPE IF EXISTS note_status CASCADE")
    op.execute("DROP TYPE IF EXISTS document_source_type CASCADE")
    op.execute("DROP TYPE IF EXISTS user_role CASCADE")
