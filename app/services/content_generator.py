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
Se um "Contexto do autor" for fornecido, TODOS os posts devem servir ao objetivo
declarado (autoridade, leads, networking, recrutamento ou marca empregadora),
falar diretamente com o público-alvo descrito, respeitar o tom de voz e reforçar
o posicionamento de longo prazo — construção de marca consistente, não posts soltos.

Regras dos posts:
- Gancho forte na primeira linha (ela decide o "ver mais").
- Corpo escaneável: frases curtas, quebras de linha, no máximo ~1.300 caracteres.
- Sem clickbait vazio; cada post precisa de um insight concreto ou dado pesquisado.
- Encerrar com pergunta ou CTA leve.
- 3 a 5 hashtags relevantes por post.

Responda APENAS com JSON válido, sem markdown, no formato:
{"posts": [{"commentary": "...", "hashtags": ["...", "..."], "sources": ["url1"]}]}
"""


_ENTITY_LABEL = {
    "autonomo": "profissional autônomo(a)",
    "colaborador": "profissional que trabalha em uma empresa",
    "empresa": "empresa (PJ)",
}
_GOAL_LABEL = {
    "autoridade": "construir autoridade no tema",
    "leads": "gerar leads/clientes",
    "networking": "expandir networking",
    "recrutamento": "atrair oportunidades/talentos",
    "marca_empregadora": "fortalecer a marca empregadora",
}


def build_profile_context(profile: dict | None) -> str:
    """Bloco 'Contexto do autor' anexado ao prompt. Vazio se não houver perfil."""
    if not profile or not any(profile.values()):
        return ""
    lines = ["Contexto do autor (usar para direcionar TODOS os posts):"]
    if profile.get("entity_type"):
        lines.append(f"- Atuação: {_ENTITY_LABEL.get(profile['entity_type'], profile['entity_type'])}")
    if profile.get("role"):
        lines.append(f"- Profissão/atividade: {profile['role']}")
    if profile.get("company"):
        lines.append(f"- Empresa: {profile['company']}")
    if profile.get("industry"):
        lines.append(f"- Ramo/segmento: {profile['industry']}")
    if profile.get("audience"):
        lines.append(f"- Público-alvo: {profile['audience']}")
    if profile.get("goal"):
        lines.append(f"- Objetivo no LinkedIn: {_GOAL_LABEL.get(profile['goal'], profile['goal'])}")
    if profile.get("tone"):
        lines.append(f"- Tom de voz: {profile['tone']}")
    if profile.get("pillars"):
        lines.append(f"- Pilares de conteúdo: {profile['pillars']}")
    if profile.get("positioning"):
        lines.append(f"- Posicionamento/visão de longo prazo: {profile['positioning']}")
    return "\n".join(lines)


def generate_posts(
    theme: str, instructions: str | None, count: int, language: str,
    profile: dict | None = None,
) -> list[dict]:
    s = get_settings()
    client = anthropic.Anthropic(api_key=s.ANTHROPIC_API_KEY)

    user_prompt = (
        f"Tema da pauta: {theme}\n"
        f"Idioma dos posts: {language}\n"
        f"Quantidade de posts: {count}\n"
        f"Instruções adicionais do autor: {instructions or 'nenhuma'}"
    )
    context = build_profile_context(profile)
    if context:
        user_prompt = f"{context}\n\n{user_prompt}"

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
