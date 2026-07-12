-- LinkPost AI — schema Postgres (multi-tenant desde o dia 1)
-- Railway PostgreSQL. Tokens LinkedIn sempre criptografados (Fernet) antes de persistir.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =========================
-- Usuários (tenants do SaaS)
-- =========================
CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         TEXT NOT NULL UNIQUE,
    name          TEXT,
    plan          TEXT NOT NULL DEFAULT 'free',           -- free | pro | agency
    api_key_hash  TEXT,                                    -- auth simples da API (trocar por JWT/Clerk no SaaS)
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ==========================================
-- Contas LinkedIn conectadas (OAuth 3-legged)
-- ==========================================
CREATE TABLE linkedin_accounts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    person_urn          TEXT NOT NULL,                     -- urn:li:person:{sub do OpenID userinfo}
    display_name        TEXT,
    access_token_enc    TEXT NOT NULL,                     -- Fernet(access_token) — expira em ~60 dias
    refresh_token_enc   TEXT,                              -- Fernet(refresh_token) — ~365 dias (se habilitado no app)
    access_expires_at   TIMESTAMPTZ NOT NULL,
    refresh_expires_at  TIMESTAMPTZ,
    scopes              TEXT NOT NULL DEFAULT 'openid profile w_member_social',
    status              TEXT NOT NULL DEFAULT 'active',    -- active | needs_reauth | revoked
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, person_urn)
);
CREATE INDEX idx_li_accounts_user ON linkedin_accounts(user_id);
CREATE INDEX idx_li_accounts_expiring ON linkedin_accounts(access_expires_at) WHERE status = 'active';

-- ==========================================
-- Pautas (briefs) — tema fornecido pelo usuário
-- ==========================================
CREATE TABLE content_briefs (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    linkedin_account_id UUID REFERENCES linkedin_accounts(id) ON DELETE SET NULL,
    theme          TEXT NOT NULL,                          -- ex: "tendências em Web3"
    instructions   TEXT,                                   -- tom de voz, CTA, persona, idioma
    posts_per_week SMALLINT NOT NULL DEFAULT 3 CHECK (posts_per_week BETWEEN 1 AND 7),
    use_profile    BOOLEAN NOT NULL DEFAULT TRUE,          -- aplicar Perfil de marca nesta pauta
    source_text    TEXT,                                   -- material de referência (texto extraído)
    source_filename TEXT,
    language       TEXT NOT NULL DEFAULT 'pt-BR',
    status         TEXT NOT NULL DEFAULT 'pending',        -- pending | generating | generated | failed
    error          TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_briefs_user ON content_briefs(user_id);

-- =========================
-- Posts (fila de publicação)
-- =========================
CREATE TYPE post_status AS ENUM (
    'draft',        -- gerado pela IA, aguardando revisão humana
    'approved',     -- aprovado, aguarda publish_at
    'publishing',   -- lock do worker
    'published',
    'failed',
    'cancelled'
);

CREATE TABLE posts (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id              UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    brief_id             UUID REFERENCES content_briefs(id) ON DELETE SET NULL,
    linkedin_account_id  UUID NOT NULL REFERENCES linkedin_accounts(id) ON DELETE CASCADE,
    commentary           TEXT NOT NULL,                    -- texto final do post (máx ~3000 chars no LinkedIn)
    hashtags             TEXT[] NOT NULL DEFAULT '{}',
    sources              JSONB NOT NULL DEFAULT '[]',      -- URLs usadas na pesquisa (auditoria)
    image_data           BYTEA,                            -- imagem opcional (upload do usuário)
    image_mime           TEXT,                             -- image/jpeg | image/png | image/gif
    image_filename       TEXT,
    status               post_status NOT NULL DEFAULT 'draft',
    publish_at           TIMESTAMPTZ,                      -- obrigatório quando approved
    published_at         TIMESTAMPTZ,
    linkedin_post_urn    TEXT,                             -- x-restli-id retornado pelo POST /rest/posts
    attempts             SMALLINT NOT NULL DEFAULT 0,
    last_error           TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_posts_due ON posts(publish_at) WHERE status = 'approved';
CREATE INDEX idx_posts_user ON posts(user_id, status);

-- =========================
-- Log de publicações (auditoria/billing)
-- =========================
CREATE TABLE publish_logs (
    id           BIGSERIAL PRIMARY KEY,
    post_id      UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    attempt      SMALLINT NOT NULL,
    success      BOOLEAN NOT NULL,
    http_status  INT,
    response     JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =========================
-- Perfil de marca (contexto p/ geração)
-- =========================
CREATE TABLE brand_profiles (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    entity_type  TEXT,   -- autonomo | colaborador | empresa
    role         TEXT,   -- profissão/cargo (PF) ou o que a empresa faz (PJ)
    company      TEXT,   -- empresa onde trabalha (PF) ou nome da empresa (PJ)
    industry     TEXT,   -- ramo/segmento
    audience     TEXT,   -- público-alvo dos posts
    goal         TEXT,   -- autoridade | leads | networking | recrutamento | marca_empregadora
    tone         TEXT,   -- tom de voz
    pillars      TEXT,   -- pilares/temas de conteúdo
    positioning  TEXT,   -- diferenciais, posicionamento, visão de longo prazo
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
