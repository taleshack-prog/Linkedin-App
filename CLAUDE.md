# Posthink — Contexto de desenvolvimento (Claude Code)
(marca antiga: 'LinkPost AI' — trocada em 07/2026; migração/schema.sql
 mantêm o nome antigo em comentários por serem histórico aplicado)

SaaS multi-tenant que gera posts de LinkedIn com IA (pesquisa web + redação) e
publica automaticamente via API oficial do LinkedIn. Uso próprio + comercialização.

Produção: app https://posthink.com.br (Vercel) · API https://api.posthink.com.br (Railway)

## Stack (padrão dos projetos do Tales)
- Backend: FastAPI + SQLAlchemy 2.0 + Pydantic v2
- Fila: Celery (worker + beat) sobre Redis
- Banco: PostgreSQL (Railway)
- Deploy: Railway (3 serviços: api, worker, beat) | Frontend futuro: React na Vercel
- IA: Anthropic API direta (uma chamada por pauta, com tool web_search)

## Arquitetura
```
briefs (pauta) --Celery--> generate_from_brief --> posts em DRAFT
usuário revisa/edita --> POST /posts/{id}/approve (define publish_at)
beat 60s --> scan_due_posts (FOR UPDATE SKIP LOCKED) --> publish_post
publish_post --> refresh token se preciso --> POST /rest/posts --> published
beat 6h  --> refresh_expiring_tokens (renovação proativa)
```

## Invariantes — NÃO violar
1. **Humano no loop**: post só vai ao LinkedIn se status=approved com publish_at
   definido pelo usuário. Nunca publicar draft automaticamente.
2. **Tokens sempre criptografados** (Fernet, app/security.py). Nunca logar token.
3. **Multi-tenant**: toda query filtra por user_id. Nunca expor dados entre tenants.
4. **Uma chamada Anthropic por pauta** (texto completo, sem chunking).
5. Escapar commentary com `escape_commentary()` antes do POST (little text do LinkedIn).

## Restrições da API do LinkedIn (verificadas 07/2026)
- Endpoint: POST https://api.linkedin.com/rest/posts (não usar /ugcPosts — deprecado)
- Headers obrigatórios: `LinkedIn-Version: YYYYMM` (config), `X-Restli-Protocol-Version: 2.0.0`
- Escopo perfil pessoal: `w_member_social` (self-serve, produto "Share on LinkedIn")
- Sucesso = 201 + header `x-restli-id` (URN do post)
- SEM agendamento nativo (por isso o Celery beat), SEM edição de post publicado
  (corrigir = deletar e recriar), SEM @mentions/enquetes/documentos/artigos via API
- Access token ~60 dias; refresh token ~365 dias; rate ~100 calls/dia/membro
- 401/403 no publish => marcar conta needs_reauth, não fazer retry

## Convenções de trabalho
- Reescrever arquivos inteiros (`cat > arquivo << 'EOF'`), não patches incrementais
- Heredocs Python: `python3 << 'PYEOF'`, nunca Node (problema com `!`)
- Migrations: **Alembic é a fonte da verdade** (`alembic upgrade head` roda no
  pre-deploy do Railway e no boot da api local). Mudou app/models.py? ->
  `docker compose exec api alembic revision --autogenerate -m "descricao"`,
  revisar o arquivo gerado, commitar. db/schema.sql e db/migrations/ ficam
  como referência histórica — NÃO aplicar mais via psql -f
- Testes de publicação: usar conta LinkedIn de teste, nunca a conta principal

## Comandos
```bash
docker compose up             # dev local (api :8000, worker, beat, pg, redis)
uvicorn app.main:app --reload # só a API
celery -A app.tasks.celery_app.celery worker -l info
celery -A app.tasks.celery_app.celery beat -l info
```

## Formatação de texto (Unicode) — frontend/src/format.js
O feed do LinkedIn não tem rich text: negrito/itálico são caracteres Unicode que
IMITAM formatação. Custos: leitores de tela pulam, busca não indexa, ocupa mais
bytes. Usamos blocos SANS-SERIF (os serifados têm buracos, ex.: itálico sem 'h').
Acentos não têm variante — "ação" vira "𝗮çã𝗼" (por isso o aviso).
Guarda-corpos: hashtag bloqueada, aviso de acento, aviso acima de 20% do post.
Feature do plano Pro+ (`text_formatting`).

## Stripe — armadilhas conhecidas
- Customer é POR MODO: o criado em test não existe em live ("No such customer").
  `_ensure_customer()` valida e recria — sem isso, o 1º checkout em produção
  quebra para todo usuário que já testou. Vale também p/ customer excluído.
- API "Basil" (2025-03-31+) REMOVEU `current_period_end` da Subscription: agora
  vive em `items.data[].current_period_end`. Também moveu `invoice.subscription`
  para `invoice.parent.subscription_details.subscription`. Os helpers
  `_period_end()` e `_subscription_id_from_invoice()` leem os DOIS formatos.
- StripeObject (lib v15+) NÃO herda de dict e NÃO tem .get(): usar o acessor
  `_g(obj, campo, default)` em tudo que vem do Stripe. Testar com dict puro não
  reproduz produção — os testes usam StripeObject.construct_from().
- Sintoma quando quebra: pagamento aprovado (tela verde) mas plano não muda —
  a webhook estoura 500. Diagnóstico: Workbench > Webhooks > Tentativas + logs
  da api no Railway.

## LGPD (implementado)
- Política pública em /privacidade (rota sem login; vercel.json faz o rewrite SPA).
  URL exigida pelo LinkedIn Developer Portal.
- GET /privacy/export: portabilidade (art. 18, V) — NÃO exporta tokens.
- DELETE /privacy/account: exclusão (art. 18, VI) — cancela assinatura no Stripe,
  revoga token no LinkedIn (ambos best-effort) e apaga tudo via cascade do banco.
- ATENÇÃO: User.linkedin_accounts PRECISA de passive_deletes=True — sem isso o
  ORM tenta user_id=NULL (NOT NULL) e a exclusão falha.
- Transferência internacional (art. 33) declarada: Anthropic, OpenAI, LinkedIn,
  Stripe, Railway e Vercel (EUA).

## Frontend — rotas públicas
- `/`            -> Landing (visitante). Quem TEM sessão cai direto no app.
- `/entrar`      -> Login; `?criar=1` abre em cadastro; `?ref=` propaga a indicação.
- `/privacidade` -> Política (LGPD + exigência do LinkedIn).
- vercel.json faz o rewrite SPA — sem ele, URL direta dá 404.

## Roadmap
- [x] Pauta com material de referência (PDF/DOCX/TXT/MD/CSV -> texto extraído no prompt)
- [x] Perfil de marca (brand_profiles): contexto do autor injetado em toda geração
- [ ] MVP single-user (você): OAuth + geração + aprovação + publish
- [x] Frontend React (Vercel): calendário editorial + fila de aprovação (`frontend/`)
- [x] Posts com imagem — upload pelo usuário (Images API: initializeUpload -> PUT binário -> content.media.id)
- [x] Geração de imagem por IA (Gemini gemini-3.1-flash-image-preview; GEMINI_API_KEY opcional)
- [x] Alembic (baseline 0001; pre-deploy no Railway)
- [x] Auth real: JWT (e-mail/senha via bcrypt + Google Sign-In) com transição do X-API-Key;
      alicerces de indicação (referral_code/referred_by) — crédito de meses na fase Stripe
- [x] Billing (Stripe): 3 planos BRL (Starter 20,00 / Pro 45,70 / Agency 100,00 —
      preços em CENTAVOS no código, padrão Stripe), cobrança
      imediata com garantia de 7 dias (CDC art.49),
      Checkout + webhook (fonte da verdade) + portal; gating de features por plano
- [x] Gamificação de indicação: padrinho sobe a escada 3/10/16 -> 1/6/12 meses;
      indicado ganha +15 dias na 1a assinatura; só conta assinante pago; tudo
      idempotente (services/referrals.py)
- [x] LGPD: política publicada + exportação + exclusão de conta/dados
- [ ] w_organization_social (Company Pages) — requer review Marketing API (2-4 semanas)
