"""Cliente LinkedIn: OAuth 3-legged, refresh de token e publicação via /rest/posts.

Referências (Microsoft Learn / LinkedIn):
- Authorization Code Flow: https://www.linkedin.com/oauth/v2/authorization + /accessToken
- Refresh: grant_type=refresh_token (refresh tokens duram ~365 dias; access ~60 dias).
  Se o app não tiver refresh programático habilitado, marcar conta como needs_reauth.
- Publicação: POST https://api.linkedin.com/rest/posts (Community Management API).
  Headers obrigatórios: LinkedIn-Version (YYYYMM), X-Restli-Protocol-Version: 2.0.0.
  Sucesso: 201 + header `x-restli-id` com o URN do post.
"""
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx

from app.config import get_settings

AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
POSTS_URL = "https://api.linkedin.com/rest/posts"
IMAGES_URL = "https://api.linkedin.com/rest/images"

# Caracteres reservados do formato "little text" do LinkedIn — precisam de escape
# no campo commentary, senão a API retorna 400 ou renderiza errado.
_RESERVED = "\\|{}@[]()<>~_*"


def escape_commentary(text: str) -> str:
    for ch in _RESERVED:
        text = text.replace(ch, "\\" + ch)
    return text


class LinkedInError(Exception):
    def __init__(self, status: int, body: str):
        self.status = status
        self.body = body
        super().__init__(f"LinkedIn API {status}: {body[:500]}")


def build_authorize_url(state: str) -> str:
    s = get_settings()
    params = {
        "response_type": "code",
        "client_id": s.LINKEDIN_CLIENT_ID,
        "redirect_uri": f"{s.BASE_URL}/auth/linkedin/callback",
        "scope": s.LINKEDIN_SCOPES,
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def exchange_code(code: str) -> dict:
    """Troca authorization code por tokens. Retorna dict com access_token,
    expires_in, e (se habilitado) refresh_token / refresh_token_expires_in."""
    s = get_settings()
    resp = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": f"{s.BASE_URL}/auth/linkedin/callback",
            "client_id": s.LINKEDIN_CLIENT_ID,
            "client_secret": s.LINKEDIN_CLIENT_SECRET,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise LinkedInError(resp.status_code, resp.text)
    return resp.json()


def refresh_access_token(refresh_token: str) -> dict:
    s = get_settings()
    resp = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": s.LINKEDIN_CLIENT_ID,
            "client_secret": s.LINKEDIN_CLIENT_SECRET,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise LinkedInError(resp.status_code, resp.text)
    return resp.json()


def get_userinfo(access_token: str) -> dict:
    """OpenID userinfo — `sub` vira o person URN: urn:li:person:{sub}."""
    resp = httpx.get(
        USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=30
    )
    if resp.status_code != 200:
        raise LinkedInError(resp.status_code, resp.text)
    return resp.json()


def _versioned_headers(access_token: str) -> dict:
    s = get_settings()
    return {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": s.LINKEDIN_API_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }


def initialize_image_upload(access_token: str, person_urn: str) -> tuple[str, str]:
    """Etapa 1 da Images API: registra o upload. Retorna (upload_url, image_urn)."""
    resp = httpx.post(
        f"{IMAGES_URL}?action=initializeUpload",
        json={"initializeUploadRequest": {"owner": person_urn}},
        headers=_versioned_headers(access_token),
        timeout=30,
    )
    if resp.status_code != 200:
        raise LinkedInError(resp.status_code, resp.text)
    value = resp.json().get("value", {})
    upload_url, image_urn = value.get("uploadUrl"), value.get("image")
    if not upload_url or not image_urn:
        raise LinkedInError(resp.status_code, f"initializeUpload sem uploadUrl/image: {resp.text[:300]}")
    return upload_url, image_urn


def upload_image_binary(upload_url: str, access_token: str, data: bytes) -> None:
    """Etapa 2: PUT do binário na uploadUrl (201 = sucesso)."""
    resp = httpx.put(
        upload_url,
        content=data,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=60,
    )
    if resp.status_code not in (200, 201):
        raise LinkedInError(resp.status_code, resp.text)


def build_post_payload(person_urn: str, commentary: str, image_urn: str | None = None) -> dict:
    """Payload do POST /rest/posts. Com imagem, referencia o URN em content.media.id."""
    payload = {
        "author": person_urn,
        "commentary": escape_commentary(commentary),
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    if image_urn:
        payload["content"] = {"media": {"id": image_urn}}
    return payload


def publish_text_post(
    access_token: str, person_urn: str, commentary: str, image_urn: str | None = None
) -> tuple[str, int, dict]:
    """Publica post (texto ou texto+imagem). Retorna (post_urn, http_status, meta p/ log)."""
    payload = build_post_payload(person_urn, commentary, image_urn)
    resp = httpx.post(
        POSTS_URL,
        json=payload,
        headers=_versioned_headers(access_token),
        timeout=30,
    )
    if resp.status_code != 201:
        raise LinkedInError(resp.status_code, resp.text)
    post_urn = resp.headers.get("x-restli-id", "")
    return post_urn, resp.status_code, {"headers": dict(resp.headers)}


def tokens_to_expiry(data: dict) -> tuple[datetime, datetime | None]:
    now = datetime.now(timezone.utc)
    access_exp = now + timedelta(seconds=int(data.get("expires_in", 0)))
    refresh_exp = None
    if data.get("refresh_token_expires_in"):
        refresh_exp = now + timedelta(seconds=int(data["refresh_token_expires_in"]))
    return access_exp, refresh_exp
