"""Phase 1 foundation: users, refresh tokens, blobs, documents, versions, jobs, audit.

Immutability is also enforced in the database: blob rows can never be updated or deleted,
and a version's source file can never be changed.

Revision ID: fd155bc2e5f5
Revises:
Create Date: 2026-11-07 07:16:27.701785
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "fd155bc2e5f5"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


IMMUTABILITY_SQL = [
    """CREATE FUNCTION akshara_reject_change() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'AKSHARA: % on % is not allowed (immutable record)', TG_OP, TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql""",
    """CREATE TRIGGER blobs_immutable BEFORE UPDATE OR DELETE ON blobs
  FOR EACH ROW EXECUTE FUNCTION akshara_reject_change()""",
    """CREATE TRIGGER document_versions_source_immutable
  BEFORE UPDATE OF source_blob, document_id, number ON document_versions
  FOR EACH ROW EXECUTE FUNCTION akshara_reject_change()""",
]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("subject_type", sa.String(length=32), nullable=True),
        sa.Column("subject_id", sa.Uuid(), nullable=True),
        sa.Column(
            "metadata", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index(
        "ix_audit_owner_created", "audit_events", ["owner_id", "created_at"], unique=False
    )
    op.create_table(
        "blobs",
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("sha256", name=op.f("pk_blobs")),
    )
    op.create_table(
        "users",
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_admin", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("allow_external_llm", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("preferred_unit", sa.String(length=4), server_default="pt", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "documents",
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("original_filename", sa.String(length=300), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("current_version_id", sa.Uuid(), nullable=True),
        sa.Column(
            "safety_warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("kind IN ('docx','pdf','pptx')", name=op.f("ck_documents_kind")),
        sa.CheckConstraint("origin IN ('uploaded','generated')", name=op.f("ck_documents_origin")),
        sa.CheckConstraint(
            "status IN ('uploading','processing','ready','failed')",
            name=op.f("ck_documents_status"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_documents_owner_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
    )
    op.create_index(
        "ix_documents_owner_updated", "documents", ["owner_id", "updated_at"], unique=False
    )
    op.create_table(
        "jobs",
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("progress", sa.Float(), server_default="0", nullable=False),
        sa.Column("subject_type", sa.String(length=32), nullable=True),
        sa.Column("subject_id", sa.Uuid(), nullable=True),
        sa.Column(
            "params", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled')",
            name=op.f("ck_jobs_status"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_jobs_owner_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
    )
    op.create_index("ix_jobs_owner_created", "jobs", ["owner_id", "created_at"], unique=False)
    op.create_table(
        "refresh_tokens",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_refresh_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
    )
    op.create_index(
        op.f("ix_refresh_tokens_family_id"), "refresh_tokens", ["family_id"], unique=False
    )
    op.create_index(op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"], unique=False)
    op.create_table(
        "document_versions",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("parent_version_id", sa.Uuid(), nullable=True),
        sa.Column("source_blob", sa.String(length=64), nullable=False),
        sa.Column("adm_blob", sa.String(length=64), nullable=True),
        sa.Column("adm_schema_version", sa.String(length=16), nullable=True),
        sa.Column("created_by", sa.String(length=16), nullable=False),
        sa.Column(
            "summary", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "created_by IN ('upload','changeset','generation','rebuild','revert')",
            name=op.f("ck_document_versions_created_by"),
        ),
        sa.ForeignKeyConstraint(
            ["adm_blob"],
            ["blobs.sha256"],
            name=op.f("fk_document_versions_adm_blob_blobs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_document_versions_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_version_id"],
            ["document_versions.id"],
            name=op.f("fk_document_versions_parent_version_id_document_versions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_blob"],
            ["blobs.sha256"],
            name=op.f("fk_document_versions_source_blob_blobs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_versions")),
        sa.UniqueConstraint("document_id", "number", name="uq_document_versions_doc_number"),
    )
    op.create_index(
        op.f("ix_document_versions_document_id"), "document_versions", ["document_id"], unique=False
    )
    op.create_foreign_key(
        op.f("fk_documents_current_version_id_document_versions"),
        "documents",
        "document_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    for statement in IMMUTABILITY_SQL:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS document_versions_source_immutable ON document_versions")
    op.execute("DROP TRIGGER IF EXISTS blobs_immutable ON blobs")
    op.execute("DROP FUNCTION IF EXISTS akshara_reject_change()")
    op.drop_constraint(
        op.f("fk_documents_current_version_id_document_versions"), "documents", type_="foreignkey"
    )
    op.drop_index(op.f("ix_document_versions_document_id"), table_name="document_versions")
    op.drop_table("document_versions")
    op.drop_index(op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_family_id"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index("ix_jobs_owner_created", table_name="jobs")
    op.drop_table("jobs")
    op.drop_index("ix_documents_owner_updated", table_name="documents")
    op.drop_table("documents")
    op.drop_table("users")
    op.drop_table("blobs")
    op.drop_index("ix_audit_owner_created", table_name="audit_events")
    op.drop_table("audit_events")
