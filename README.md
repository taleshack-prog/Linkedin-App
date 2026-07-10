# LinkPost AI

Gera posts de LinkedIn com IA (pesquisa web + redação via Anthropic API) e publica
automaticamente no horário agendado, via API oficial do LinkedIn (`POST /rest/posts`).

**Humano no loop**: nada é publicado sem aprovação explícita (`approve` + `publish_at`).

## Arquitetura

```
briefs (pauta) --Celery--> generate_from_brief --> posts em DRAFT
usuário revisa/edita --> POST /posts/{id}/approve (define publish_at futuro, UTC)
beat 60s --> scan_due_posts (FOR UPDATE SKIP LOCKED + resgate de posts presos)
         --> publish_post --> refresh token se preciso --> POST /rest/posts
beat 6h  --> refresh_expiring_tokens (renovação proativa)
```

## Estrutura

```
linkpost-ai/
├── CLAUDE.md                     # contexto p/ Claude Code (invariantes, restrições da API)
├── db/schema.sql                 # schema Postgres (multi-tenant)
├── app/
│   ├── main.py / config.py / database.py / models.py / schemas.py / security.py
│   ├── routers/    auth_linkedin.py, briefs.py, posts.py
│   ├── services/   linkedin_client.py, content_generator.py
│   └── tasks/      celery_app.py, publish_tasks.py, generation_tasks.py
├── frontend/                     # React (Vite) — mesa editorial, deploy na Vercel
├── tests/
└── docker-compose.yml / Dockerfile / requirements.txt / .env.example
```

## Setup rápido

1. **LinkedIn Developer Portal**: criar app, vincular a uma Company Page, verificar,
   ativar produtos "Sign In with LinkedIn using OpenID Connect" e "Share on LinkedIn"
   (concede `w_member_social`). Adicionar redirect URI:
   `{BASE_URL}/auth/linkedin/callback`.
2. Copiar `.env.example` -> `.env` e preencher. Gerar a `SECRET_KEY`:
   ```bash
   python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
3. `docker compose up` (aplica `db/schema.sql` no primeiro boot do Postgres).
4. Criar usuário + API key:
   ```bash
   python3 << 'PYEOF'
   import secrets
   from app.database import SessionLocal
   from app.models import User
   from app.security import hash_api_key
   key = secrets.token_urlsafe(32)
   db = SessionLocal()
   db.add(User(email="voce@exemplo.com", api_key_hash=hash_api_key(key)))
   db.commit()
   print("API key:", key)
   PYEOF
   ```
5. `GET /auth/linkedin/login` (header `X-API-Key`) -> abrir `authorize_url` -> consentir.
6. `POST /briefs` com o tema -> revisar drafts em `GET /posts?status=draft` ->
   editar via `PATCH /posts/{id}` se quiser -> `POST /posts/{id}/approve` com
   `publish_at` (futuro, UTC). O beat publica sozinho.

## Frontend (mesa editorial)

```bash
cd frontend
cp .env.example .env          # VITE_API_URL = URL da API
npm install && npm run dev    # http://localhost:5173
```

Deploy na Vercel: importar o repo, definir Root Directory = `frontend`,
adicionar a env `VITE_API_URL` (URL da API no Railway) e, no backend,
incluir a URL da Vercel em `FRONTEND_ORIGINS`.

## Testes

```bash
pip install -r requirements-dev.txt
pytest
```

## Notas de produção

- Header `LinkedIn-Version` (YYYYMM): versões antigas são descontinuadas pelo
  LinkedIn — atualizar `LINKEDIN_API_VERSION` periodicamente.
- Refresh tokens programáticos só são emitidos para apps aprovados; sem eles,
  contas expiram em ~60 dias e ficam `needs_reauth` (reautenticar via OAuth).
- Rate limit: ~100 calls/dia por membro.
- Antes do primeiro cliente pago: Alembic (migrations), JWT/Clerk (auth) e Stripe.

Ver `CLAUDE.md` para invariantes e restrições completas da API do LinkedIn.
