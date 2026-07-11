-- Perfil de marca: contexto do autor injetado em toda geração de posts.
CREATE TABLE IF NOT EXISTS brand_profiles (
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
