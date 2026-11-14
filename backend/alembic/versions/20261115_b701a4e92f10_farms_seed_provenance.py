"""Persist provenance of farm inputs and the scope of water scenarios.

Revision ID: b701a4e92f10
Revises: 1fe077a8bc2d
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b701a4e92f10"
down_revision = "1fe077a8bc2d"
branch_labels = None
depends_on = None

TABLES = ("farms", "orchards", "herds", "cash_accounts", "crop_seasons",
          "crop_variants", "cost_norms", "scenarios")


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("provenance", postgresql.JSONB(),
                                      nullable=False, server_default="{}"))
    op.add_column("scenarios", sa.Column("water_supply_months",
                                        postgresql.ARRAY(sa.Integer()), nullable=True))
    op.add_column("water_rights", sa.Column("turn_hours", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("water_rights", "turn_hours")
    op.drop_column("scenarios", "water_supply_months")
    for table in reversed(TABLES):
        op.drop_column(table, "provenance")
