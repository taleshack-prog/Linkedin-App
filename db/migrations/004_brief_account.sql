-- Pauta passa a lembrar a conta LinkedIn alvo (necessário para regenerar).
ALTER TABLE content_briefs
  ADD COLUMN IF NOT EXISTS linkedin_account_id UUID REFERENCES linkedin_accounts(id) ON DELETE SET NULL;
