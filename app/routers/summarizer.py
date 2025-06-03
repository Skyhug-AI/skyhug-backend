from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from dependency_injector.wiring import Provide, inject

from app.containers import Container
from app.services.summarizer_service import SummarizerService

router = APIRouter(tags=["summarizer"])


class SummarizeRequest(BaseModel):
    conversation_id: str


@router.post("/summarize_conversation")
@inject
async def summarize_conversation(
    req: SummarizeRequest,
    summarizer: SummarizerService = Depends(Provide[Container.summarizer_service]),
):
    try:
        summarizer.summarize_and_store(req.conversation_id)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup_inactive")
@inject
async def cleanup_inactive(
    summarizer: SummarizerService = Depends(Provide[Container.summarizer_service]),
):
    try:
        summarizer.close_inactive_conversations()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
