"""enable bestbuy retailer

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-13
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE retailers SET is_supported = true WHERE domain = 'bestbuy.com'")


def downgrade() -> None:
    op.execute("UPDATE retailers SET is_supported = false WHERE domain = 'bestbuy.com'")
