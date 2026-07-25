"""video: upload assincrono para o LinkedIn (guarda so a URN + status)

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("posts", sa.Column("video_urn", sa.String(), nullable=True))
    op.add_column("posts", sa.Column("video_status", sa.String(), nullable=True))
    op.add_column("posts", sa.Column("video_title", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("posts", "video_title")
    op.drop_column("posts", "video_status")
    op.drop_column("posts", "video_urn")
