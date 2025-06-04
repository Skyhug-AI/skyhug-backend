import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import summarizer, tts
from dependency_injector.wiring import inject, Provide
from services.openai_service import OpenAIService
from services.elevenlabs_service import ElevenLabsService
from services.summarizer_service import SummarizerService
from services.whisper_service import WhisperService
from services.chat_service import ChatService
import asyncio


from containers import Container

container = Container()

app = FastAPI(title="Skyhug Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # lock down in prod!
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(summarizer.router, prefix="", tags=["summarizer"])
app.include_router(tts.router,        prefix="", tags=["tts"])

@app.on_event("startup")
@inject
async def startup_event():
    container.init_resources()
    container.wire(packages=["routers", "services", "repositories", "models", "constants"])
    app.state.container = container

    cfg                 = container.config()
    openai_service      = container.openai_service()
    elevenlabs_service  = container.elevenlabs_service()
    summarizer_service  = container.summarizer_service()
    whisper_service     = container.whisper_service()
    chat_service = await container.chat_service()


    elevenlabs_service.warmup_elevenlabs_pool()
    openai_service.warmup_models()
    summarizer_service.schedule_cleanup(interval_hours=1)

    for msg in whisper_service.fetch_pending("messages", sender_role="user", transcription_status="pending"):
        whisper_service.handle_transcription_record(msg)

    for msg in chat_service.fetch_pending("messages", sender_role="user", transcription_status="done", ai_status="pending"):
        chat_service.handle_ai_record(msg)

    asyncio.create_task(chat_service.start_realtime())

@app.on_event("shutdown")
async def shutdown_event():
    await container.shutdown_resources()

# # import and include your routers
# from apis.health_check import router as health_router
# # …
# app.include_router(health_router, prefix="/health", tags=["health"])
# # include other routers…

if __name__ == "__main__":
    uvicorn.run("main:app", port=8000, reload=True)
