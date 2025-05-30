import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import chat, summarizer, tts
from .services.elevenlabs import warmup_elevenlabs_pool
from .services.openai_service import warmup_openai_models
from dependency_injector.wiring import inject, Provide
from app.services.openai_service import OpenAIService

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
    eleven_sess=Provide[Container.elevenlabs_session],
    openai_client=Provide[Container.openai_client],
    cfg=Provide[Container.config],
    openai_service: OpenAIService = Provide[Container.openai_service],
):
    # 1) init & wire your DI container
    container.init_resources()
    container.wire(packages=["app.routers", "app.services"])
    app.state.container = container

    # 2) warm up the default ElevenLabs voice & OpenAI
    warmup_elevenlabs_pool(eleven_sess, cfg.ELEVENLABS_VOICE_ID)
    openai_service.warmup_models()

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
