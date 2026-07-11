-- Imagem opcional por post (armazenada no Postgres; enviada ao LinkedIn na publicação)
-- Aplicar em bancos existentes. Novos bancos já vêm com as colunas via schema.sql.
ALTER TABLE posts
  ADD COLUMN IF NOT EXISTS image_data     BYTEA,
  ADD COLUMN IF NOT EXISTS image_mime     TEXT,
  ADD COLUMN IF NOT EXISTS image_filename TEXT;
