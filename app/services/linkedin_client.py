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
REVOKE_URL = "https://www.linkedin.com/oauth/v2/revoke"
POSTS_URL = "https://api.linkedin.com/rest/posts"
IMAGES_URL = "https://api.linkedin.com/rest/images"
VIDEOS_URL = "https://api.linkedin.com/rest/videos"

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


def initialize_video_upload(access_token: str, person_urn: str, file_size_bytes: int) -> dict:
    """Videos API etapa 1: registra o upload. Retorna dict com video_urn, upload_token
    e instructions (lista de partes: {uploadUrl, firstByte, lastByte})."""
    resp = httpx.post(
        f"{VIDEOS_URL}?action=initializeUpload",
        json={"initializeUploadRequest": {"owner": person_urn, "fileSizeBytes": file_size_bytes}},
        headers=_versioned_headers(access_token),
        timeout=30,
    )
    if resp.status_code != 200:
        raise LinkedInError(resp.status_code, resp.text)
    value = resp.json().get("value", {})
    video_urn = value.get("video")
    instructions = value.get("uploadInstructions") or []
    if not video_urn or not instructions:
        raise LinkedInError(resp.status_code, f"initializeUpload sem video/instructions: {resp.text[:300]}")
    return {"video_urn": video_urn, "upload_token": value.get("uploadToken", ""), "instructions": instructions}


def upload_video_parts(access_token: str, file_path: str, instructions: list[dict]) -> list[str]:
    """Videos API etapa 2: PUT de cada parte (faixa de bytes) na sua uploadUrl.
    Retorna os ETags na ordem das partes (obrigatorios e ordenados no finalize)."""
    etags: list[str] = []
    with open(file_path, "rb") as f:
        for part in instructions:
            first, last = int(part["firstByte"]), int(part["lastByte"])
            f.seek(first)
            chunk = f.read(last - first + 1)
            resp = httpx.put(
                part["uploadUrl"],
                content=chunk,
                headers={"Authorization": f"Bearer {access_token}",
                         "Content-Type": "application/octet-stream"},
                timeout=120,
            )
            if resp.status_code not in (200, 201):
                raise LinkedInError(resp.status_code, resp.text)
            etag = resp.headers.get("etag") or resp.headers.get("ETag")
            if not etag:
                raise LinkedInError(resp.status_code, "parte de video sem ETag na resposta")
            etags.append(etag.strip('"'))
    return etags


def finalize_video_upload(access_token: str, video_urn: str, upload_token: str, etags: list[str]) -> None:
    """Videos API etapa 3: finaliza, ligando as partes pelos ETags. Sucesso = 200/201."""
    resp = httpx.post(
        f"{VIDEOS_URL}?action=finalizeUpload",
        json={"finalizeUploadRequest": {
            "video": video_urn, "uploadToken": upload_token, "uploadedPartIds": etags,
        }},
        headers=_versioned_headers(access_token),
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        raise LinkedInError(resp.status_code, resp.text)


def get_video_status(access_token: str, video_urn: str) -> str:
    """Videos API etapa 4: consulta status do processamento.
    Retorna o status em maiusculas (PROCESSING | AVAILABLE | PROCESSING_FAILED | WAITING_UPLOAD)."""
    from urllib.parse import quote
    resp = httpx.get(
        f"{VIDEOS_URL}/{quote(video_urn, safe='')}",
        headers=_versioned_headers(access_token),
        timeout=30,
    )
    if resp.status_code != 200:
        raise LinkedInError(resp.status_code, resp.text)
    data = resp.json()
    return (data.get("status") or data.get("value", {}).get("status") or "").upper()


def build_post_payload(person_urn: str, commentary: str, image_urn: str | None = None,
                       video_urn: str | None = None, video_title: str | None = None,
                       image_urns: list[dict] | None = None) -> dict:
    """Payload do POST /rest/posts.

    Conteúdo, em ordem de prioridade: vídeo > múltiplas imagens (2-4 -> multiImage)
    > imagem única (media). image_urns: lista de {"id": urn, "alt": texto|None}.
    """
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
    if video_urn:
        media = {"id": video_urn}
        if video_title:
            media["title"] = video_title
        payload["content"] = {"media": media}
    elif image_urns:
        imgs = []
        for it in image_urns:
            img = {"id": it["id"]}
            if it.get("alt"):
                img["altText"] = it["alt"]
            imgs.append(img)
        payload["content"] = {"media": imgs[0]} if len(imgs) == 1 else {"multiImage": {"images": imgs}}
    elif image_urn:
        payload["content"] = {"media": {"id": image_urn}}
    return payload


def publish_text_post(
    access_token: str, person_urn: str, commentary: str, image_urn: str | None = None,
    video_urn: str | None = None, video_title: str | None = None
) -> tuple[str, int, dict]:
    """Publica post (texto ou texto+imagem). Retorna (post_urn, http_status, meta p/ log)."""
    payload = build_post_payload(person_urn, commentary, image_urn, video_urn, video_title)
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


def revoke_token(token: str) -> bool:
    """Revoga o token no LinkedIn (usado na exclusão de conta — LGPD).
    Best-effort: falha aqui não pode impedir o usuário de excluir os dados."""
    s = get_settings()
    try:
        resp = httpx.post(
            REVOKE_URL,
            data={
                "token": token,
                "client_id": s.LINKEDIN_CLIENT_ID,
                "client_secret": s.LINKEDIN_CLIENT_SECRET,
            },
            timeout=15,
        )
        return resp.status_code == 200
    except Exception:  # noqa: BLE001
        return False
