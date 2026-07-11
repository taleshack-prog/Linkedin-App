"""Geração de imagem para posts via Google Gemini (API generateContent).

Formato verificado (03/2026):
- POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
- Header: x-goog-api-key
- Body: {"contents": [{"parts": [{"text": prompt}]}]}
- Resposta: candidates[0].content.parts[] -> parte com inlineData {mimeType, data(base64)}

A imagem gerada entra no MESMO campo do upload manual — passa pela mesma
revisão humana antes de qualquer publicação (invariante do projeto).
"""
import base64

import httpx

from app.config import get_settings

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

_COMMENTARY_EXCERPT_CHARS = 700


class ImageGenError(Exception):
    def __init__(self, status: int, body: str):
        self.status = status
        self.body = body
        super().__init__(f"Gemini {status}: {body[:300]}")


def build_image_prompt(commentary: str, instructions: str | None = None) -> str:
    """Prompt visual derivado do texto do post. Sem texto/logos na imagem —
    tipografia gerada por IA em post de LinkedIn costuma sair errada e amadora."""
    excerpt = commentary.strip()[:_COMMENTARY_EXCERPT_CHARS]
    prompt = (
        "Crie uma imagem para ilustrar um post profissional de LinkedIn.\n"
        "Estilo: ilustração moderna, limpa e profissional; cores harmoniosas; "
        "composição simples com um conceito central forte.\n"
        "Restrições: NÃO incluir nenhum texto, letras, números, logotipos ou marcas "
        "d'água na imagem. Sem rostos fotorrealistas de pessoas reais.\n"
        f"Tema do post:\n{excerpt}"
    )
    if instructions:
        prompt += f"\n\nInstruções adicionais do autor: {instructions.strip()[:500]}"
    return prompt


def parse_image_response(data: dict) -> tuple[bytes, str]:
    """Extrai (bytes, mime) da resposta do generateContent."""
    try:
        parts = data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        raise ImageGenError(502, f"Resposta sem candidates/parts: {str(data)[:300]}")
    for part in parts:
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
            return base64.b64decode(inline["data"]), mime
    raise ImageGenError(502, "Resposta do Gemini não contém imagem (inlineData)")


def generate_post_image(commentary: str, instructions: str | None = None) -> tuple[bytes, str]:
    """Gera a imagem. Retorna (bytes, mime). Levanta ImageGenError em falha."""
    s = get_settings()
    if not s.GEMINI_API_KEY:
        raise ImageGenError(503, "GEMINI_API_KEY não configurada no servidor")

    resp = httpx.post(
        GEMINI_URL.format(model=s.GEMINI_IMAGE_MODEL),
        json={"contents": [{"parts": [{"text": build_image_prompt(commentary, instructions)}]}]},
        headers={"x-goog-api-key": s.GEMINI_API_KEY, "Content-Type": "application/json"},
        timeout=120,
    )
    if resp.status_code != 200:
        raise ImageGenError(resp.status_code, resp.text)
    return parse_image_response(resp.json())
