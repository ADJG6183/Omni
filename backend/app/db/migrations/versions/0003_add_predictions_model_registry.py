"""Add predictions and model_registry tables.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "predictions",
        sa.Column("id",                  UUID(as_uuid=False), primary_key=True),
        sa.Column("product_id",          UUID(as_uuid=False), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("model_version",       sa.String(100), nullable=False),
        sa.Column("drop_probability_7d", sa.Numeric(5, 4), nullable=True),
        sa.Column("recommendation",      sa.String(50), nullable=False),
        sa.Column("confidence",          sa.String(20), nullable=False),
        sa.Column("explanation",         JSONB, nullable=True),
        sa.Column("predicted_at",        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_predictions_product_id", "predictions", ["product_id"])
    op.create_index("ix_predictions_predicted_at", "predictions", ["predicted_at"])

    op.create_table(
        "model_registry",
        sa.Column("id",              UUID(as_uuid=False), primary_key=True),
        sa.Column("model_name",      sa.String(100), nullable=False),
        sa.Column("model_version",   sa.String(100), nullable=False, unique=True),
        sa.Column("model_type",      sa.String(50),  nullable=False),
        sa.Column("artifact_path",   sa.Text, nullable=True),
        sa.Column("feature_columns", JSONB, nullable=True),
        sa.Column("metrics",         JSONB, nullable=True),
        sa.Column("is_active",       sa.Boolean, nullable=False, default=False),
        sa.Column("created_at",      sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("predictions")
    op.drop_table("model_registry")
