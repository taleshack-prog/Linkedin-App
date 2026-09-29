"""Ingestão da auditoria: pega os arquivos, persiste e roda o diagnóstico.

Separado do router porque a ordem importa e tem regra de negócio:

  1. O export vira snapshot (janela) + métricas por publicação (acumuladas).
  2. Cada métrica tenta casar com um post nosso pelo share id. Quando casa,
     ganhamos o TEXTO do post — que o export não traz — e é isso que permite
     avaliar escrita contra desempenho.
  3. Só então a auditoria roda, já com os posts casados em mãos.
  4. O bloco `para_geracao` desce para o BrandProfile e, de lá, entra em toda
     geração sem que o gerador saiba que a auditoria existe.

Métricas nunca diminuem: o upsert mantém o maior valor já visto. Se o usuário
reenviar uma janela antiga, o histórico não regride.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AnalyticsSnapshot, BrandProfile, Post, PostMetric, ProfileAudit, User
from app.services.linkedin_export import urn_para_share_id
from app.services.profile_auditor import auditar

MAX_POSTS_PARA_AUDITORIA = 25


def _maior(atual: int | None, novo: int | None) -> int | None:
    if novo is None:
        return atual
    if atual is None:
        return novo
    return max(atual, novo)


def salvar_snapshot(db: Session, user: User, dados: dict) -> AnalyticsSnapshot | None:
    """Grava a janela do export. Reenvio do mesmo período atualiza, não duplica."""
    periodo = dados.get("periodo") or {}
    if not periodo.get("inicio") or not periodo.get("fim"):
        return None

    inicio = date.fromisoformat(periodo["inicio"])
    fim = date.fromisoformat(periodo["fim"])
    resumo = dados.get("resumo") or {}

    snap = db.execute(
        select(AnalyticsSnapshot).where(
            AnalyticsSnapshot.user_id == user.id,
            AnalyticsSnapshot.periodo_inicio == inicio,
            AnalyticsSnapshot.periodo_fim == fim,
        )
    ).scalar_one_or_none()

    if snap is None:
        snap = AnalyticsSnapshot(user_id=user.id, periodo_inicio=inicio, periodo_fim=fim)
        db.add(snap)

    snap.impressoes = resumo.get("impressoes")
    snap.alcance = resumo.get("alcance")
    snap.engajamentos = resumo.get("engajamentos")
    snap.seguidores_total = resumo.get("seguidores_total")
    snap.seguidores_novos = resumo.get("seguidores_novos")
    snap.dados = {
        "serie_diaria": dados.get("serie_diaria") or [],
        "publico": dados.get("publico") or [],
        "conteudo": dados.get("conteudo") or [],
        "avisos": dados.get("avisos") or [],
    }
    return snap


def salvar_metricas(db: Session, user: User, dados: dict) -> tuple[int, int]:
    """Faz o upsert das publicações e casa com os posts do Posthink.

    Devolve (quantas linhas, quantas casaram com post nosso).
    """
    publicacoes = dados.get("publicacoes") or []
    if not publicacoes:
        return 0, 0

    # índice share_id -> post nosso, montado uma vez
    nossos = db.execute(
        select(Post).where(Post.user_id == user.id, Post.linkedin_post_urn.isnot(None))
    ).scalars().all()
    por_share = {}
    for p in nossos:
        sid = urn_para_share_id(p.linkedin_post_urn)
        if sid:
            por_share[sid] = p

    existentes = {
        m.share_id: m
        for m in db.execute(
            select(PostMetric).where(PostMetric.user_id == user.id)
        ).scalars().all()
    }

    casados = 0
    for pub in publicacoes:
        sid = pub.get("share_id")
        if not sid:
            continue
        m = existentes.get(sid)
        if m is None:
            m = PostMetric(user_id=user.id, share_id=sid)
            db.add(m)
            existentes[sid] = m

        m.url = pub.get("url") or m.url
        m.tema_url = pub.get("tema_url") or m.tema_url
        if pub.get("data"):
            m.publicado_em = date.fromisoformat(pub["data"])
        # métrica acumulada só cresce: reenvio de janela antiga não regride
        m.impressoes = _maior(m.impressoes, pub.get("impressoes"))
        m.engajamentos = _maior(m.engajamentos, pub.get("engajamentos"))

        post = por_share.get(sid)
        if post is not None:
            m.post_id = post.id
            casados += 1

    return len(publicacoes), casados


def ultimo_snapshot_como_metricas(db: Session, user: User) -> dict | None:
    """Reconstrói o bloco de métricas a partir do último export guardado.

    O usuário não precisa reenviar a planilha a cada auditoria: o LinkedIn só
    entrega janelas curtas e, entre duas auditorias no mesmo dia, o arquivo
    seria idêntico. O que já foi importado continua valendo — com a data da
    importação explícita, para o auditor saber que não é de hoje.
    """
    snap = db.execute(
        select(AnalyticsSnapshot)
        .where(AnalyticsSnapshot.user_id == user.id)
        .order_by(AnalyticsSnapshot.periodo_fim.desc())
    ).scalars().first()
    if snap is None:
        return None

    dados = snap.dados if isinstance(snap.dados, dict) else {}
    publicacoes = db.execute(
        select(PostMetric)
        .where(PostMetric.user_id == user.id)
        .order_by(PostMetric.impressoes.desc().nullslast())
    ).scalars().all()

    return {
        "periodo": {
            "inicio": snap.periodo_inicio.isoformat() if snap.periodo_inicio else None,
            "fim": snap.periodo_fim.isoformat() if snap.periodo_fim else None,
            "dias": ((snap.periodo_fim - snap.periodo_inicio).days + 1)
                    if snap.periodo_inicio and snap.periodo_fim else None,
        },
        "resumo": {
            "impressoes": snap.impressoes, "alcance": snap.alcance,
            "engajamentos": snap.engajamentos,
            "seguidores_total": snap.seguidores_total,
            "seguidores_novos": snap.seguidores_novos,
        },
        "serie_diaria": dados.get("serie_diaria") or [],
        "publico": dados.get("publico") or [],
        "conteudo": dados.get("conteudo") or [],
        "publicacoes": [
            {
                "share_id": m.share_id, "url": m.url, "tema_url": m.tema_url,
                "data": m.publicado_em.isoformat() if m.publicado_em else None,
                "impressoes": m.impressoes, "engajamentos": m.engajamentos,
            }
            for m in publicacoes
        ],
        "avisos": list(dados.get("avisos") or []) + [
            "Estes números vêm de um export importado antes, não de um arquivo enviado "
            "agora. Servem para avaliar conteúdo; não os trate como movimento recente."
        ],
        "de_importacao_anterior": True,
    }


def posts_para_auditoria(db: Session, user: User) -> list[dict]:
    """Posts publicados, marcados pela ORIGEM.

    A distinção importa e é a única que o Posthink consegue fazer sozinho:
    `post_id` preenchido significa que o post saiu daqui, e então temos o
    texto; sem `post_id`, foi publicado direto no LinkedIn e só temos URL e
    métrica.

    Sem isso, o auditor atribui à geração automática um hábito que é do
    usuário — e uma diretriz sobre algo que o gerador não controla (publicar
    vídeo sem texto, por exemplo, é impossível aqui: o commentary é
    obrigatório) vira ruído no prompt de geração.
    """
    linhas = db.execute(
        select(PostMetric, Post)
        .outerjoin(Post, PostMetric.post_id == Post.id)
        .where(PostMetric.user_id == user.id)
        .order_by(PostMetric.impressoes.desc().nullslast())
        .limit(MAX_POSTS_PARA_AUDITORIA)
    ).all()

    fora = []
    for metrica, post in linhas:
        do_posthink = post is not None
        fora.append({
            "texto": post.commentary if do_posthink else None,
            "tema_url": metrica.tema_url,
            "data": metrica.publicado_em.isoformat() if metrica.publicado_em else None,
            "impressoes": metrica.impressoes,
            "engajamentos": metrica.engajamentos,
            "origem": "posthink" if do_posthink else "fora",
        })
    return fora


def aplicar_ao_perfil_de_marca(db: Session, user: User, para_geracao: dict | None) -> bool:
    """Leva as conclusões da auditoria ao BrandProfile.

    Escreve apenas em `tone` e `pillars`, e só quando estão vazios ou foram
    escritos por uma auditoria anterior — o que a pessoa digitou à mão não é
    sobrescrito por uma máquina.
    """
    if not para_geracao:
        return False

    tom = (para_geracao.get("tom") or "").strip()
    priorizar = para_geracao.get("priorizar") or []
    if not tom and not priorizar:
        return False

    perfil = db.execute(
        select(BrandProfile).where(BrandProfile.user_id == user.id)
    ).scalar_one_or_none()
    if perfil is None:
        perfil = BrandProfile(user_id=user.id)
        db.add(perfil)

    MARCA = "[auditoria]"
    mudou = False
    if tom and (not perfil.tone or perfil.tone.startswith(MARCA)):
        perfil.tone = f"{MARCA} {tom}"
        mudou = True
    if priorizar and (not perfil.pillars or perfil.pillars.startswith(MARCA)):
        perfil.pillars = f"{MARCA} " + "; ".join(str(x) for x in priorizar[:6])
        mudou = True
    return mudou


def rodar_auditoria(
    db: Session,
    user: User,
    *,
    perfil_texto: str | None,
    metricas: dict | None,
    posts_colados: list[str] | None,
    imagens: list[tuple[str, bytes]] | None,
) -> ProfileAudit:
    """Orquestra: persiste o export, casa, audita e grava."""
    if metricas:
        salvar_snapshot(db, user, metricas)
        salvar_metricas(db, user, metricas)
        db.flush()  # para a auditoria já enxergar os casamentos

    # Sem planilha nova, vale o que já foi importado: métricas e textos ficam
    # guardados e não somem porque o usuário não reenviou o mesmo arquivo.
    if not metricas:
        metricas = ultimo_snapshot_como_metricas(db, user)

    posts = posts_para_auditoria(db, user)
    for texto in (posts_colados or []):
        texto = (texto or "").strip()
        if texto:
            posts.append({"texto": texto, "origem": "colado"})

    contexto = None
    perfil_marca = db.execute(
        select(BrandProfile).where(BrandProfile.user_id == user.id)
    ).scalar_one_or_none()
    if perfil_marca is not None:
        contexto = perfil_marca.to_context_dict()

    # A auditoria anterior entra no prompt para que esta não critique o que
    # aquela mandou fazer. Sem isso, quem aplica as recomendações volta e
    # encontra o próprio trabalho listado como defeito — e para de aplicar.
    anterior = db.execute(
        select(ProfileAudit)
        .where(ProfileAudit.user_id == user.id)
        .order_by(ProfileAudit.created_at.desc())
    ).scalars().first()
    bloco_anterior = None
    if anterior is not None and isinstance(anterior.resultado, dict):
        bloco_anterior = {
            "quando": anterior.created_at.strftime("%d/%m/%Y") if anterior.created_at else None,
            "score": anterior.resultado.get("score"),
            "acoes": anterior.resultado.get("acoes") or [],
        }

    resultado = auditar(
        perfil_texto=perfil_texto,
        metricas=metricas,
        posts=posts or None,
        imagens=imagens,
        contexto_marca=contexto,
        auditoria_anterior=bloco_anterior,
    )

    score = resultado.get("score") or {}
    auditoria = ProfileAudit(
        user_id=user.id,
        score_total=score.get("total"),
        score_perfil=score.get("perfil"),
        score_conteudo=score.get("conteudo"),
        score_consistencia=score.get("consistencia"),
        fontes=resultado.get("fontes") or [],
        resultado=resultado,
    )
    db.add(auditoria)

    aplicar_ao_perfil_de_marca(db, user, resultado.get("para_geracao"))
    db.commit()
    db.refresh(auditoria)
    return auditoria
