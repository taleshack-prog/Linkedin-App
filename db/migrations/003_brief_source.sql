-- Material de referência opcional da pauta (texto extraído de PDF/DOCX/TXT).
ALTER TABLE content_briefs
  ADD COLUMN IF NOT EXISTS source_text     TEXT,
  ADD COLUMN IF NOT EXISTS source_filename TEXT;
