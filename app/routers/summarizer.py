from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.workers import summarize_and_store, close_inactive_conversations

router = APIRouter(tags=["summarizer"])

class SummarizeRequest(BaseModel):
    conversation_id: str

@router.post("/summarize_conversation")
async def summarize_conversation(req: SummarizeRequest):
    try:
        summarize_and_store(req.conversation_id)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cleanup_inactive")
async def cleanup_inactive():
    """
    Manually trigger auto-ending and summarizing any conversation
    that has been idle >1h.
    """
    try:
        close_inactive_conversations()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
