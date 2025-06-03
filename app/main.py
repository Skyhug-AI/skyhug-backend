import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import chat, summarizer, tts
from dependency_injector.wiring import inject, Provide
from app.services.openai_service import OpenAIService
from app.services.elevenlabs_service import ElevenLabsService
from app.services.summarizer_service import SummarizerService


from app.config import config
from containers import Container

container = Container()

app = FastAPI(title="Skyhug Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # lock down in prod!
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router,       prefix="/chat")
app.include_router(summarizer.router, prefix="", tags=["summarizer"])
app.include_router(tts.router,        prefix="", tags=["tts"])

@app.on_event("startup")
@inject
async def startup_event(
    cfg=Provide[Container.config],
    openai_service: OpenAIService = Provide[Container.openai_service],
    elevenlabs_service: ElevenLabsService = Provide[Container.elevenlabs_service],
    summarizer_service: SummarizerService = Provide[Container.summarizer_service],
):
    # 1) init & wire your DI container
    container.init_resources()
    container.wire(packages=["app.routers", "app.services"])
    app.state.container = container

    # openai_svc: OpenAIService = container.openai_service()
    elevenlabs_service.warmup_elevenlabs_pool()
    openai_service.warmup_models()
    summarizer_service.close_inactive_conversations()

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
