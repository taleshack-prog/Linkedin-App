"""auditoria de marca: profile_audits, analytics_snapshots, post_metrics

Suporte à auditoria alimentada por upload (PDF do perfil e export .xlsx de
analytics). Nenhuma destas tabelas depende de API do LinkedIn — os escopos
self-serve não entregam nem perfil nem métrica.

analytics_snapshots existe porque o LinkedIn só exporta janelas curtas e não
guarda histórico para o usuário: acumulando cada upload, o Posthink passa a
ter a série que a própria plataforma não mostra.

post_metrics.post_id liga a métrica ao nosso post quando o share_id casa com
o linkedin_post_urn — é o que junta desempenho e texto do mesmo post.

Revision ID: 0006
Revises: 0005
"""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        r"""
        CREATE TABLE profile_audits (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            score_total         SMALLINT,
            score_perfil        SMALLINT,
            score_conteudo      SMALLINT,
            score_consistencia  SMALLINT,
            fontes              TEXT[] NOT NULL DEFAULT '{}',
            resultado           JSONB  NOT NULL DEFAULT '{}'::jsonb,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_profile_audits_user ON profile_audits(user_id, created_at DESC);

        CREATE TABLE analytics_snapshots (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            periodo_inicio    DATE NOT NULL,
            periodo_fim       DATE NOT NULL,
            impressoes        INTEGER,
            alcance           INTEGER,
            engajamentos      INTEGER,
            seguidores_total  INTEGER,
            seguidores_novos  INTEGER,
            dados             JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_snapshot_periodo UNIQUE (user_id, periodo_inicio, periodo_fim)
        );
        CREATE INDEX idx_snapshots_user ON analytics_snapshots(user_id, periodo_fim DESC);

        CREATE TABLE post_metrics (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            post_id       UUID REFERENCES posts(id) ON DELETE SET NULL,
            share_id      TEXT NOT NULL,
            url           TEXT,
            publicado_em  DATE,
            impressoes    INTEGER,
            engajamentos  INTEGER,
            tema_url      TEXT,
            medido_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_metric_post UNIQUE (user_id, share_id)
        );
        CREATE INDEX idx_post_metrics_user ON post_metrics(user_id, impressoes DESC NULLS LAST);
        CREATE INDEX idx_post_metrics_post ON post_metrics(post_id);
        """
    )


def downgrade() -> None:
    op.execute(
        r"""
        DROP TABLE IF EXISTS post_metrics;
        DROP TABLE IF EXISTS analytics_snapshots;
        DROP TABLE IF EXISTS profile_audits;
        """
    )
