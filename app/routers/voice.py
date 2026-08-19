"""Pauta por voz: transcreve o áudio (Deepgram, pt-BR) e devolve o texto.

Privacidade/LGPD: o áudio é dado biométrico. NÃO é persistido — fica só em
memória durante o request e é descartado ao final. Guardamos apenas o texto,
e só depois que o usuário confirmar (Fluxo A). Disponível em Pro/Agency.
"""
import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.config import get_settings
from app.models import User
from app.security import get_current_user
from app.services.plans import require_feature

router = APIRouter(prefix="/voice", tags=["voice"])

ALLOWED_AUDIO_MIMES = {
    "audio/webm", "audio/ogg", "audio/mp4", "audio/m4a",
    "audio/mpeg", "audio/wav", "audio/x-wav",
}
MAX_AUDIO_BYTES = 25 * 1024 * 1024  # ~muito além de 5 min de voz
DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"


@router.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    if not require_feature(user, "voice"):
        raise HTTPException(402, "Pauta por voz está disponível nos planos Pro e Agency")
    settings = get_settings()
    if not settings.DEEPGRAM_API_KEY:
        raise HTTPException(503, "Transcrição indisponível no momento")
    mime = (file.content_type or "").split(";")[0]
    if mime not in ALLOWED_AUDIO_MIMES:
        raise HTTPException(415, "Formato de áudio não suportado")

    # Acumula o áudio SÓ em memória (nunca toca o disco) com corte de tamanho.
    audio = bytearray()
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        audio.extend(chunk)
        if len(audio) > MAX_AUDIO_BYTES:
            raise HTTPException(413, "Áudio muito longo (máximo ~5 minutos)")
    if not audio:
        raise HTTPException(400, "Áudio vazio")

    try:
        resp = httpx.post(
            DEEPGRAM_URL,
            params={
                "model": "nova-3",
                "language": "pt-BR",
                "smart_format": "true",
                "punctuate": "true",
                "filler_words": "false",
            },
            headers={
                "Authorization": f"Token {settings.DEEPGRAM_API_KEY}",
                "Content-Type": file.content_type or "audio/webm",
            },
            content=bytes(audio),
            timeout=60,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Falha ao transcrever: {exc}")

    if resp.status_code != 200:
        raise HTTPException(502, "O serviço de transcrição recusou o áudio")
    data = resp.json()
    try:
        alt = data["results"]["channels"][0]["alternatives"][0]
        transcript = (alt.get("transcript") or "").strip()
        confidence = alt.get("confidence")
    except (KeyError, IndexError, TypeError):
        raise HTTPException(502, "Resposta de transcrição inválida")
    if not transcript:
        raise HTTPException(422, "Não consegui entender o áudio. Tente de novo, com menos ruído.")
    return {
        "transcript": transcript,
        "confidence": confidence,
        "duration_s": data.get("metadata", {}).get("duration"),
    }
