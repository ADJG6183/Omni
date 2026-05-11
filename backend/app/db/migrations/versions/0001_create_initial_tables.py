"""create initial tables

Revision ID: 0001
Revises:
Create Date: 2026-05-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "retailers",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False, unique=True),
        sa.Column("is_supported", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "products",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("retailer_id", UUID(as_uuid=False), sa.ForeignKey("retailers.id"), nullable=False),
        sa.Column("retailer_product_id", sa.String(255), nullable=True),
        sa.Column("canonical_url", sa.Text, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("brand", sa.String(255), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("image_url", sa.Text, nullable=True),
        sa.Column("normalized_title", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("retailer_id", "retailer_product_id", name="uq_product_retailer_id"),
    )

    op.create_index("ix_products_retailer_product_id", "products", ["retailer_product_id"])

    op.create_table(
        "price_history",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("product_id", UUID(as_uuid=False), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="USD"),
        sa.Column("availability", sa.String(50), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index("ix_price_history_product_id", "price_history", ["product_id"])
    op.create_index("ix_price_history_observed_at", "price_history", ["observed_at"])
    op.create_index(
        "ix_price_history_product_observed",
        "price_history",
        ["product_id", "observed_at"],
    )

    # Seed supported retailers
    op.execute("""
        INSERT INTO retailers (id, name, domain, is_supported)
        VALUES
            (gen_random_uuid(), 'Amazon', 'amazon.com', true),
            (gen_random_uuid(), 'Best Buy', 'bestbuy.com', false)
    """)


def downgrade() -> None:
    op.drop_table("price_history")
    op.drop_table("products")
    op.drop_table("retailers")
