"""billing (Stripe) e crédito de indicação

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("stripe_customer_id", sa.String(), nullable=True))
    op.add_column("users", sa.Column("plan_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("referral_active", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("referral_months_granted", sa.SmallInteger(), nullable=False, server_default="0"))
    op.create_unique_constraint("uq_users_stripe_customer", "users", ["stripe_customer_id"])


def downgrade() -> None:
    op.drop_constraint("uq_users_stripe_customer", "users", type_="unique")
    op.drop_column("users", "referral_months_granted")
    op.drop_column("users", "referral_active")
    op.drop_column("users", "plan_until")
    op.drop_column("users", "stripe_customer_id")
