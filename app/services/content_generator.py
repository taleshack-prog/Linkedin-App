"""Geração de conteúdo: pesquisa web + redação dos posts via Anthropic API.

Padrão do projeto: UMA chamada por pauta (não fragmentar), com a tool de
web_search habilitada para trazer informação atual sobre o tema.
Saída: JSON estrito, parseado e validado antes de virar registros `posts`.
"""
import json

import anthropic

from app.config import get_settings

SYSTEM_PROMPT = """Você é um ghostwriter sênior de LinkedIn.
Pesquise o tema na web para trazer dados e acontecimentos ATUAIS antes de escrever.

Regras dos posts:
- Gancho forte na primeira linha (ela decide o "ver mais").
- Corpo escaneável: frases curtas, quebras de linha, no máximo ~1.300 caracteres.
- Sem clickbait vazio; cada post precisa de um insight concreto ou dado pesquisado.
- Encerrar com pergunta ou CTA leve.
- 3 a 5 hashtags relevantes por post.

Responda APENAS com JSON válido, sem markdown, no formato:
{"posts": [{"commentary": "...", "hashtags": ["...", "..."], "sources": ["url1"]}]}
"""


def generate_posts(theme: str, instructions: str | None, count: int, language: str) -> list[dict]:
    s = get_settings()
    client = anthropic.Anthropic(api_key=s.ANTHROPIC_API_KEY)

    user_prompt = (
        f"Tema da pauta: {theme}\n"
        f"Idioma dos posts: {language}\n"
        f"Quantidade de posts: {count}\n"
        f"Instruções adicionais do autor: {instructions or 'nenhuma'}"
    )

    msg = client.messages.create(
        model=s.ANTHROPIC_MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
    )

    # A resposta pode intercalar blocos de tool_use/tool_result; o JSON final
    # está nos blocos de texto — concatenar e parsear o último objeto válido.
    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"Resposta sem JSON parseável: {text[:300]}")
    data = json.loads(text[start : end + 1])

    posts = data.get("posts", [])
    if not posts:
        raise ValueError("Modelo não retornou posts")
    for p in posts:
        if not p.get("commentary"):
            raise ValueError("Post sem commentary")
        p.setdefault("hashtags", [])
        p.setdefault("sources", [])
    return posts[:count]
