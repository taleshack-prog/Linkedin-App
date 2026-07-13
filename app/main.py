from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import accounts, auth, auth_linkedin, billing, briefs, posts, profile

app = FastAPI(title="LinkPost AI", version="0.2.0")

# CORS: origens do frontend (Vercel + dev local), separadas por vírgula no .env
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().FRONTEND_ORIGINS.split(",") if o.strip()],
    allow_credentials=False,          # auth vai no header X-API-Key, sem cookies
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["X-API-Key", "Content-Type", "Authorization"],
)

app.include_router(auth.router)
app.include_router(auth_linkedin.router)
app.include_router(accounts.router)
app.include_router(briefs.router)
app.include_router(posts.router)
app.include_router(profile.router)
app.include_router(billing.router)


@app.get("/health")
def health():
    return {"status": "ok"}
