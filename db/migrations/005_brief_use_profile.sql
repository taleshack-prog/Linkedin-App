-- Controle por pauta: usar ou não o Perfil de marca na geração.
ALTER TABLE content_briefs
  ADD COLUMN IF NOT EXISTS use_profile BOOLEAN NOT NULL DEFAULT TRUE;
