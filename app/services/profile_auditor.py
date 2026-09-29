"""Auditoria de marca: lê perfil, desempenho e posts e devolve diagnóstico.

Uma chamada ao Claude com tudo que o usuário forneceu (texto do PDF de perfil,
métricas já parseadas do export, textos de posts e, opcionalmente, imagens do
perfil) e um JSON estruturado de volta.

Duas regras que valem mais que o resto:

  1. NUNCA inventar número. Se a métrica não veio, o campo fica nulo e o
     diagnóstico daquela dimensão não existe. O produto inteiro é vendido
     sobre aprovação humana e honestidade; uma auditoria que estima
     engajamento destrói isso.
  2. Toda afirmação carrega a evidência de onde saiu. É o que permite ao
     usuário discordar — e discordar é o que mantém ele no controle.

O bloco `para_geracao` é a ponte: vai para o BrandProfile e, de lá, já entra
em toda geração de post sem que o gerador precise saber que a auditoria existe.
"""
from __future__ import annotations

import base64
import json

from app.config import get_settings

MAX_POSTS_NO_PROMPT = 25
MAX_CHARS_POR_POST = 1_200
MAX_IMAGENS = 4
MAX_BYTES_IMAGEM = 4_000_000  # limite prático por imagem na API

SYSTEM_PROMPT = """Você é um consultor de posicionamento no LinkedIn. Audita o perfil e o conteúdo de uma pessoa e devolve um diagnóstico acionável.

COMO VOCÊ TRABALHA

Você recebe algum subconjunto destes materiais: texto do perfil, métricas de desempenho, textos de posts publicados, imagens do perfil. Nunca recebe todos garantidamente. Você avalia o que chegou e é explícito sobre o que não pôde avaliar.

REGRAS INEGOCIÁVEIS

1. Não invente números. Se as métricas não vieram, não fale de desempenho — nem em termos vagos como "seus posts parecem ter pouco alcance". Sem dado, a dimensão de conteúdo fica nula.
2. Toda afirmação sua cita a base: o que no material te levou àquilo. O campo `evidencia` é obrigatório em cada achado e deve citar o material, não o seu raciocínio.
3. Métrica pequena é métrica pequena. Com 168 impressões em 7 dias, você não tem base para concluir "qual formato performa melhor" — diga isso em vez de fingir análise. Volume baixo permite observação, não conclusão.
4. Não elogie para suavizar. O valor está no que está errado e em como consertar. Reconheça acertos só quando forem reproduzíveis — e diga como reproduzir.
5. Escreva para a pessoa, em segunda pessoa, direto. Nada de "o usuário deveria". Português do Brasil.
6. Separe o que a máquina controla do que a pessoa controla. Cada post vem marcado com a origem. Os escritos no Posthink passaram pela IA de geração: vício de escrita neles é instrução que cabe em `para_geracao.evitar`. Os publicados fora do Posthink são hábito da pessoa, e o gerador não tem como mudá-los — isso vira `acoes`, nunca `evitar`. Atribuir errado faz duas coisas ruins ao mesmo tempo: enche o prompt de geração com regra que ele não pode violar, e esconde da pessoa um conselho que era para ela.

COMO PONTUAR

Cada componente do score vai de 0 a 100 e só existe se você teve material para avaliá-lo:
- `perfil`: headline, resumo, competências — precisa do texto do perfil.
- `conteudo`: ganchos, tom, formatos, consistência temática — precisa de textos de posts.
- `consistencia`: o que o perfil promete versus o que os posts entregam — precisa dos dois.
O `total` é a média dos componentes existentes. Se só um existe, o total é ele.

Seja rigoroso. 100 é um perfil que você não teria o que melhorar; isso praticamente não existe. Um perfil mediano fica entre 40 e 60. Não infle para agradar.

AÇÕES

No máximo 5, ordenadas por impacto. Cada uma diz o que fazer e como — com o texto pronto quando for reescrita de headline ou de resumo. "Melhore sua headline" não é ação; "troque para: <texto>" é.

O BLOCO para_geracao

É o que vai direcionar a escrita automática dos próximos posts. Preencha com o que você descobriu: o tom que funciona para esta pessoa, o ângulo que o posicionamento pede, o que evitar e o que priorizar. Seja concreto e curto: cada item vira instrução para outra IA.

O `evitar` só admite o que a IA de geração é capaz de fazer de errado — vícios de escrita observados nos posts marcados como escritos no Posthink. Comportamentos de publicação (postar sem texto, frequência, formato escolhido na hora de publicar) não são dela: vão em `acoes`.

AS PAUTAS

Proponha de 3 a 6 temas para os próximos posts. Não são ideias genéricas de conteúdo: cada pauta nasce de algo que você encontrou nesta auditoria — uma lacuna entre o que a pessoa domina e o que ela publica, uma divergência entre o perfil e a prática, um assunto que o público dela demonstra buscar e ela não cobre.

Cada pauta traz o tema como a pessoa digitaria numa caixa de busca (específico, não "falar sobre IA"), o motivo pelo qual você a propõe, e o ângulo que ela deve tomar. A escolha é sempre do usuário — você propõe, ele decide."""

AUDIT_TOOL = {
    "name": "emit_audit",
    "description": "Devolve a auditoria estruturada.",
    "input_schema": {
        "type": "object",
        "properties": {
            "score": {
                "type": "object",
                "properties": {
                    "total": {"type": ["integer", "null"]},
                    "perfil": {"type": ["integer", "null"]},
                    "conteudo": {"type": ["integer", "null"]},
                    "consistencia": {"type": ["integer", "null"]},
                    "base": {
                        "type": "string",
                        "description": "Uma frase dizendo o que foi avaliado e o que faltou.",
                    },
                },
                "required": ["total", "base"],
            },
            "achados": {
                "type": "array",
                "description": "Diagnóstico item a item. Máximo 8.",
                "items": {
                    "type": "object",
                    "properties": {
                        "area": {
                            "type": "string",
                            "enum": ["headline", "resumo", "competencias", "posicionamento",
                                     "publico", "gancho", "tom", "formato", "temas", "visual"],
                        },
                        "severidade": {"type": "string", "enum": ["alta", "media", "baixa"]},
                        "diagnostico": {"type": "string"},
                        "evidencia": {
                            "type": "string",
                            "description": "O trecho ou número do material que sustenta isto.",
                        },
                    },
                    "required": ["area", "severidade", "diagnostico", "evidencia"],
                },
            },
            "acoes": {
                "type": "array",
                "description": "Até 5, ordenadas por impacto.",
                "items": {
                    "type": "object",
                    "properties": {
                        "titulo": {"type": "string"},
                        "porque": {"type": "string"},
                        "como": {
                            "type": "string",
                            "description": "O passo concreto. Se for reescrita, o texto pronto.",
                        },
                        "impacto": {"type": "string", "enum": ["alto", "medio", "baixo"]},
                    },
                    "required": ["titulo", "porque", "como", "impacto"],
                },
            },
            "para_geracao": {
                "type": "object",
                "description": "Instruções que passam a direcionar a escrita dos próximos posts.",
                "properties": {
                    "tom": {"type": "string"},
                    "angulo": {"type": "string"},
                    "evitar": {"type": "array", "items": {"type": "string"}},
                    "priorizar": {"type": "array", "items": {"type": "string"}},
                },
            },
            "pautas": {
                "type": "array",
                "description": "3 a 6 temas para os próximos posts, cada um nascido de um achado desta auditoria.",
                "items": {
                    "type": "object",
                    "properties": {
                        "tema": {
                            "type": "string",
                            "description": "Como a pessoa digitaria numa caixa de busca. Específico.",
                        },
                        "porque": {
                            "type": "string",
                            "description": "O achado desta auditoria que motiva esta pauta.",
                        },
                        "angulo": {"type": "string"},
                    },
                    "required": ["tema", "porque", "angulo"],
                },
            },
            "nao_avaliado": {
                "type": "array",
                "description": "O que faltou material para analisar, e qual arquivo resolveria.",
                "items": {"type": "string"},
            },
        },
        "required": ["score", "achados", "acoes", "para_geracao", "pautas"],
    },
}


def _bloco_perfil(texto: str | None) -> str:
    if not texto:
        return ""
    return f"<perfil_linkedin>\n{texto[:20_000]}\n</perfil_linkedin>"


def _bloco_metricas(dados: dict | None) -> str:
    """Serializa o que saiu de linkedin_export.parse_analytics_xlsx."""
    if not dados:
        return ""
    periodo = dados.get("periodo") or {}
    dias = periodo.get("dias")
    corpo = json.dumps(dados, ensure_ascii=False, indent=1)
    nota = ""
    if dias and dias <= 31:
        nota = (
            f"\nATENÇÃO: a janela é de apenas {dias} dias. Volume assim permite observar, "
            "não concluir. Não afirme qual formato ou tema performa melhor com esta base."
        )
    return f"<desempenho>{nota}\n{corpo}\n</desempenho>"


ORIGEM_ROTULO = {
    "posthink": "escrito pela IA e aprovado pelo autor no Posthink",
    "fora": "publicado direto no LinkedIn, fora do Posthink — texto indisponível",
    "colado": "colado pelo autor, origem não identificada",
}


def _bloco_posts(posts: list[dict] | None) -> str:
    """Posts com a origem explícita.

    Post sem texto entra assim mesmo, com o tema deduzido do endereço: a
    ausência do texto é informação (foi publicado fora), e o auditor precisa
    saber que ele existe para não concluir sobre um feed incompleto.
    """
    if not posts:
        return ""
    linhas = []
    for i, p in enumerate(posts[:MAX_POSTS_NO_PROMPT], 1):
        texto = (p.get("texto") or "").strip()[:MAX_CHARS_POR_POST]
        cab = f"[post {i}"
        if p.get("data"):
            cab += f" · {p['data']}"
        if p.get("impressoes") is not None:
            cab += f" · {p['impressoes']} impressões"
        if p.get("engajamentos") is not None:
            cab += f" · {p['engajamentos']} engajamentos"
        origem = p.get("origem")
        if origem in ORIGEM_ROTULO:
            cab += f" · {ORIGEM_ROTULO[origem]}"
        cab += "]"
        if texto:
            linhas.append(f"{cab}\n{texto}")
        elif p.get("tema_url"):
            linhas.append(f"{cab}\n(sem texto disponível; tema pelo endereço: {p['tema_url']})")
        else:
            linhas.append(f"{cab}\n(sem texto disponível)")
    if not linhas:
        return ""
    return "<posts_publicados>\n" + "\n\n---\n\n".join(linhas) + "\n</posts_publicados>"


def _blocos_imagem(imagens: list[tuple[str, bytes]] | None) -> list[dict]:
    """[(mime, bytes)] -> blocos de imagem da API. Serve para avaliar foto,
    banner e coerência visual — o que nenhum arquivo de texto carrega."""
    if not imagens:
        return []
    fora = []
    for mime, dados in imagens[:MAX_IMAGENS]:
        if not dados or len(dados) > MAX_BYTES_IMAGEM:
            continue
        if mime not in ("image/png", "image/jpeg", "image/webp", "image/gif"):
            continue
        fora.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mime,
                "data": base64.standard_b64encode(dados).decode("ascii"),
            },
        })
    return fora


def extrair_auditoria(msg) -> dict:
    for bloco in msg.content:
        if getattr(bloco, "type", None) == "tool_use" and getattr(bloco, "name", "") == "emit_audit":
            return bloco.input
    texto = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError as exc:
        raise ValueError("A auditoria não retornou um resultado estruturado.") from exc


def auditar(
    *,
    perfil_texto: str | None = None,
    metricas: dict | None = None,
    posts: list[dict] | None = None,
    imagens: list[tuple[str, bytes]] | None = None,
    contexto_marca: dict | None = None,
) -> dict:
    """Roda a auditoria. Exige ao menos uma fonte de material."""
    import anthropic

    s = get_settings()
    fontes = {
        "perfil_pdf": bool(perfil_texto),
        "analytics": bool(metricas),
        "posts": bool(posts),
        "imagens": bool(imagens),
    }
    if not any(fontes.values()):
        raise ValueError("Envie ao menos o PDF do perfil, o export de desempenho ou textos de posts.")

    partes = [b for b in (
        _bloco_perfil(perfil_texto),
        _bloco_metricas(metricas),
        _bloco_posts(posts),
    ) if b]

    if contexto_marca and any(contexto_marca.values()):
        partes.append(
            "<contexto_declarado>\n"
            + json.dumps(contexto_marca, ensure_ascii=False, indent=1)
            + "\nO que a pessoa declarou no cadastro. Compare com o que o material mostra: "
            "divergência entre o declarado e o praticado é achado de alta severidade.\n"
            "</contexto_declarado>"
        )

    faltando = [k for k, v in fontes.items() if not v]
    if faltando:
        partes.append(
            "Material NÃO fornecido nesta auditoria: " + ", ".join(faltando)
            + ". Não especule sobre essas dimensões; liste-as em `nao_avaliado` dizendo qual "
            "arquivo o usuário precisa enviar."
        )

    conteudo: list[dict] = [{"type": "text", "text": "\n\n".join(partes)}]
    imgs = _blocos_imagem(imagens)
    if imgs:
        conteudo.append({
            "type": "text",
            "text": (
                "Imagens do perfil (foto, banner, layout). Avalie coerência visual com o "
                "posicionamento — não descreva a imagem, diagnostique.\n\n"
                "ATENÇÃO: estas capturas quase sempre são a tela do DONO do perfil, não a "
                "do visitante. Botões de ação ('Disponível para', 'Adicionar seção', "
                "'Aprimorar perfil', 'Recursos'), ícones de lápis, painéis de Análise e "
                "cartões de sugestão do LinkedIn aparecem só para quem é dono e NÃO são "
                "vistos por quem visita. Não os trate como conteúdo público nem gere achado "
                "sobre eles — recomendar 'desmarcar' um botão que não dá para desmarcar faz "
                "a pessoa perder tempo e tira a credibilidade do resto do diagnóstico.\n"
                "Avalie apenas o que o visitante vê: banner, foto, nome, headline, e as "
                "seções de conteúdo do perfil. Selos que o público vê (a moldura verde de "
                "'Aberto para trabalho', a faixa de 'Prestando serviços') são conteúdo "
                "público e valem achado; a barra de ferramentas do dono, não."
            ),
        })
        conteudo.extend(imgs)

    client = anthropic.Anthropic(api_key=s.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=s.ANTHROPIC_MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": conteudo}],
        tools=[AUDIT_TOOL],
        tool_choice={"type": "tool", "name": "emit_audit"},
    )

    dados = extrair_auditoria(msg)
    dados["fontes"] = [k for k, v in fontes.items() if v]
    return dados
