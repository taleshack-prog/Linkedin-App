"""auth JWT (senha + Google) e alicerces de indicação

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(), nullable=True))
    op.add_column("users", sa.Column("google_sub", sa.String(), nullable=True))
    op.add_column("users", sa.Column("referral_code", sa.String(), nullable=True))
    op.add_column(
        "users",
        sa.Column("referred_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_unique_constraint("uq_users_google_sub", "users", ["google_sub"])
    op.create_unique_constraint("uq_users_referral_code", "users", ["referral_code"])
    op.create_foreign_key(
        "fk_users_referred_by", "users", "users", ["referred_by"], ["id"], ondelete="SET NULL"
    )
    # Backfill: todo usuário existente ganha código de indicação (pgcrypto já habilitado)
    op.execute(
        "UPDATE users SET referral_code = substr(encode(gen_random_bytes(8), 'hex'), 1, 10) "
        "WHERE referral_code IS NULL"
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_referred_by", "users", type_="foreignkey")
    op.drop_constraint("uq_users_referral_code", "users", type_="unique")
    op.drop_constraint("uq_users_google_sub", "users", type_="unique")
    op.drop_column("users", "referred_by")
    op.drop_column("users", "referral_code")
    op.drop_column("users", "google_sub")
    op.drop_column("users", "password_hash")
