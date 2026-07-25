"""post_images: multi-imagem (unifica a imagem unica numa tabela)

Cria post_images e migra a imagem unica existente (posts.image_data) para uma
linha ordinal 0. As colunas antigas em posts ficam como rede de seguranca.

Revision ID: 0005
Revises: 0004
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        r"""
        CREATE TABLE post_images (
            id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            post_id        UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
            ordinal        SMALLINT NOT NULL DEFAULT 0,
            image_data     BYTEA NOT NULL,
            image_mime     TEXT NOT NULL,
            image_filename TEXT,
            alt_text       TEXT,
            created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_post_images_post ON post_images(post_id);

        -- migra a imagem unica existente para ordinal 0
        INSERT INTO post_images (post_id, ordinal, image_data, image_mime, image_filename)
        SELECT id, 0, image_data, image_mime, image_filename
        FROM posts
        WHERE image_mime IS NOT NULL AND image_data IS NOT NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS post_images;")
