"""Extração de texto de arquivos de referência das pautas.

Suporta: PDF (pypdf), DOCX (python-docx), XLSX (openpyxl), TXT/MD/CSV
(decodificação direta). O texto extraído é truncado e injetado no prompt de
geração — o binário original não é armazenado.

Para o export de analytics do LinkedIn (.xlsx) existe um caminho próprio em
`linkedin_export.parse_analytics_xlsx`, que devolve dados estruturados em vez
de texto corrido. Aqui o .xlsx é tratado apenas como material de referência.
"""
import io
import re

MAX_SOURCE_CHARS = 60_000  # teto do texto guardado/injetado no prompt

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".txt", ".md", ".csv"}

# Bloco de contato do PDF de perfil do LinkedIn: endereço, telefone e e-mail.
# Não serve para auditoria de marca e é dado pessoal que não precisa trafegar
# até a IA — removido antes de qualquer envio (ver limpar_contato_do_perfil).
_RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_RE_TEL = re.compile(r"\(?\d{2,3}\)?[\s-]?\d{4,5}[\s-]?\d{4}")


class ExtractionError(Exception):
    pass


def _ext(filename: str) -> str:
    name = (filename or "").lower()
    dot = name.rfind(".")
    return name[dot:] if dot != -1 else ""


def extract_text(filename: str, data: bytes) -> str:
    """Extrai texto do arquivo. Levanta ExtractionError se não suportado/vazio."""
    ext = _ext(filename)
    if ext not in SUPPORTED_EXTENSIONS:
        raise ExtractionError(
            f"Formato '{ext or 'desconhecido'}' não suportado — use PDF, DOCX, TXT, MD ou CSV"
        )

    if ext == ".pdf":
        from pypdf import PdfReader

        try:
            reader = PdfReader(io.BytesIO(data))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception as exc:  # noqa: BLE001
            raise ExtractionError(f"Falha ao ler o PDF: {exc}")
    elif ext == ".docx":
        from docx import Document

        try:
            doc = Document(io.BytesIO(data))
            parts = [p.text for p in doc.paragraphs]
            for table in doc.tables:
                for row in table.rows:
                    parts.append(" | ".join(cell.text for cell in row.cells))
            text = "\n".join(parts)
        except Exception as exc:  # noqa: BLE001
            raise ExtractionError(f"Falha ao ler o DOCX: {exc}")
    elif ext == ".xlsx":
        try:
            import openpyxl

            wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
            partes = []
            for nome in wb.sheetnames:
                partes.append(f"## {nome}")
                for row in wb[nome].iter_rows(values_only=True):
                    celulas = [str(c) for c in row if c is not None and str(c).strip()]
                    if celulas:
                        partes.append(" | ".join(celulas))
            text = "\n".join(partes)
        except ImportError:
            raise ExtractionError("Leitura de XLSX indisponível no servidor")
        except Exception as exc:  # noqa: BLE001
            raise ExtractionError(f"Falha ao ler a planilha: {exc}")
    else:  # txt / md / csv
        text = data.decode("utf-8", errors="ignore")

    text = text.strip()
    if not text:
        raise ExtractionError("Não foi possível extrair texto do arquivo (está vazio ou é digitalizado sem OCR)")
    return text[:MAX_SOURCE_CHARS]


def limpar_contato_do_perfil(texto: str) -> str:
    """Remove e-mail, telefone e endereço do PDF de perfil do LinkedIn.

    O PDF exportado abre com um bloco de contato (endereço residencial,
    celular, e-mail). Nada disso serve para auditar posicionamento, e é dado
    pessoal que, uma vez enviado à IA, entra na declaração de transferência
    internacional da LGPD. O que não trafega não precisa ser declarado.
    """
    if not texto:
        return texto
    limpo = _RE_EMAIL.sub("[e-mail removido]", texto)
    limpo = _RE_TEL.sub("[telefone removido]", limpo)

    # O cabeçalho "Contato" do template vai até a próxima seção conhecida.
    linhas = limpo.split("\n")
    fora, pulando = [], False
    for ln in linhas:
        cru = ln.strip().lower()
        if cru in ("contato", "contact"):
            pulando = True
            continue
        if pulando:
            # a seção seguinte no template é competências/idiomas/resumo
            if any(cru.startswith(p) for p in (
                "principais competências", "top skills", "languages", "idiomas",
                "certifications", "certificações", "resumo", "summary",
            )):
                pulando = False
            else:
                continue
        fora.append(ln)
    return "\n".join(fora).strip()
