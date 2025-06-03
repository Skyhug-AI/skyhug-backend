from fastapi import APIRouter, Depends
from dependency_injector.wiring import inject, Provide

from app.containers import Container
from app.services.elevenlabs_service import ElevenLabsService


router = APIRouter()


@router.get("/tts-stream/{message_id}")
@inject
async def tts_stream(
    message_id: str,
    snippet: int = 0,
    elevenlabs_service: ElevenLabsService = Depends(Provide[Container.elevenlabs_service]),
):
    return elevenlabs_service.fetch_and_stream(message_id, snippet)
