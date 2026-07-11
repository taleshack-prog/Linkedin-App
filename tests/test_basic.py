"""Testes unitários das partes puras (sem rede, sem banco)."""
import os
from datetime import datetime, timedelta, timezone

# Env mínimo ANTES de importar app.* (Settings valida no primeiro get_settings())
os.environ.setdefault("SECRET_KEY", "x" * 43 + "=")  # placeholder; Fernet só é usado lazy
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("LINKEDIN_CLIENT_ID", "test")
os.environ.setdefault("LINKEDIN_CLIENT_SECRET", "test")
os.environ.setdefault("ANTHROPIC_API_KEY", "test")

import pytest
from pydantic import ValidationError

from app.schemas import PostApprove, PostUpdate
from app.services.linkedin_client import escape_commentary


class TestEscapeCommentary:
    def test_escapa_reservados_do_little_text(self):
        assert escape_commentary("a*b_c(d)") == r"a\*b\_c\(d\)"

    def test_backslash_escapado_primeiro(self):
        # Se '\' não fosse o primeiro, escaparíamos os escapes gerados.
        assert escape_commentary("a\\b") == "a\\\\b"

    def test_texto_limpo_intacto(self):
        assert escape_commentary("Post normal, sem reservados.") == "Post normal, sem reservados."


class TestPostApprove:
    def test_rejeita_publish_at_no_passado(self):
        with pytest.raises(ValidationError):
            PostApprove(publish_at=datetime.now(timezone.utc) - timedelta(hours=1))

    def test_naive_vira_utc(self):
        futuro_naive = datetime.utcnow() + timedelta(days=1)  # noqa: DTZ003
        approved = PostApprove(publish_at=futuro_naive)
        assert approved.publish_at.tzinfo is not None

    def test_aceita_futuro_aware(self):
        alvo = datetime.now(timezone.utc) + timedelta(hours=2)
        assert PostApprove(publish_at=alvo).publish_at == alvo


class TestPostUpdate:
    def test_rejeita_commentary_acima_de_3000(self):
        with pytest.raises(ValidationError):
            PostUpdate(commentary="x" * 3001)

    def test_aceita_commentary_no_limite(self):
        assert len(PostUpdate(commentary="x" * 3000).commentary) == 3000


class TestFernetLazy:
    def test_import_nao_exige_fernet_valido(self):
        # security foi importado indiretamente sem instanciar Fernet — se
        # chegou aqui, o lazy init funciona.
        import app.security  # noqa: F401


class TestPostPayload:
    def test_payload_sem_imagem_nao_tem_content(self):
        from app.services.linkedin_client import build_post_payload
        p = build_post_payload("urn:li:person:X", "texto")
        assert "content" not in p and p["author"] == "urn:li:person:X"

    def test_payload_com_imagem_referencia_urn(self):
        from app.services.linkedin_client import build_post_payload
        p = build_post_payload("urn:li:person:X", "texto", image_urn="urn:li:image:ABC")
        assert p["content"] == {"media": {"id": "urn:li:image:ABC"}}

    def test_commentary_escapado_no_payload(self):
        from app.services.linkedin_client import build_post_payload
        p = build_post_payload("urn:li:person:X", "a(b)")
        assert p["commentary"] == r"a\(b\)"


class TestImageGenerator:
    def test_prompt_inclui_tema_e_proibe_texto(self):
        from app.services.image_generator import build_image_prompt
        p = build_image_prompt("Tendências de Web3 no Brasil")
        assert "Tendências de Web3 no Brasil" in p and "NÃO incluir nenhum texto" in p

    def test_prompt_trunca_e_anexa_instrucoes(self):
        from app.services.image_generator import build_image_prompt
        p = build_image_prompt("x" * 5000, instructions="tons de azul")
        assert "x" * 700 in p and "x" * 701 not in p and "tons de azul" in p

    def test_parse_extrai_base64_e_mime(self):
        import base64
        from app.services.image_generator import parse_image_response
        raw = b"\x89PNG-fake"
        data = {"candidates": [{"content": {"parts": [
            {"text": "aqui está"},
            {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(raw).decode()}},
        ]}}]}
        img, mime = parse_image_response(data)
        assert img == raw and mime == "image/png"

    def test_parse_sem_imagem_levanta_erro(self):
        import pytest as _pytest
        from app.services.image_generator import ImageGenError, parse_image_response
        with _pytest.raises(ImageGenError):
            parse_image_response({"candidates": [{"content": {"parts": [{"text": "só texto"}]}}]})


class TestProfileContext:
    def test_perfil_vazio_gera_bloco_vazio(self):
        from app.services.content_generator import build_profile_context
        assert build_profile_context(None) == ""
        assert build_profile_context({"role": None, "goal": None}) == ""

    def test_contexto_traduz_atuacao_e_objetivo(self):
        from app.services.content_generator import build_profile_context
        ctx = build_profile_context({
            "entity_type": "autonomo", "role": "eng. de software", "company": "HTF",
            "industry": "tecnologia", "audience": "fundadores", "goal": "leads",
            "tone": "direto", "pillars": "IA; automação", "positioning": "jogo infinito",
        })
        assert "profissional autônomo(a)" in ctx
        assert "gerar leads/clientes" in ctx
        assert "jogo infinito" in ctx and "Contexto do autor" in ctx

    def test_campos_ausentes_sao_omitidos(self):
        from app.services.content_generator import build_profile_context
        ctx = build_profile_context({"goal": "autoridade"})
        assert "Objetivo" in ctx and "Tom de voz" not in ctx and "Empresa" not in ctx
