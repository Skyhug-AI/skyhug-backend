from fastapi import APIRouter, Depends
from dependency_injector.wiring import inject, Provide

from app.containers import Container
from app.services.tts_service import TTSService

router = APIRouter()


@router.get("/tts-stream/{message_id}")
@inject
async def tts_stream(
    message_id: str,
    snippet: int = 0,
    tts: TTSService = Depends(Provide[Container.tts_service]),
    cfg=Depends(Provide[Container.config]),
):
    return tts.stream_snippet(message_id, snippet, cfg.ELEVENLABS_VOICE_ID)
