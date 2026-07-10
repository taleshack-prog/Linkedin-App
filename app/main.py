from fastapi import FastAPI

from app.routers import auth_linkedin, briefs, posts

app = FastAPI(title="LinkPost AI", version="0.1.0")
app.include_router(auth_linkedin.router)
app.include_router(briefs.router)
app.include_router(posts.router)


@app.get("/health")
def health():
    return {"status": "ok"}
