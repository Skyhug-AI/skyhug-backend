import boto3
import requests
from dependency_injector import containers, providers
from supabase import create_client as create_supabase_sync
from supabase._async.client import create_client as create_supabase_async
from openai import OpenAI
from config import config
from app.repositories.messages import MessageRepository
from app.services.tts_service import TTSService
from app.services.supabase_sync import SupabaseSyncClient
from app.services.supabase_async import SupabaseAsyncClient
from app.services.openai_service import OpenAIService
from app.services.elevenlabs_service import ElevenLabsService


class Container(containers.DeclarativeContainer):

    config = providers.Object(config)

    # Repositories
    message_repository      = providers.Factory(MessageRepository)
    conversation_repository = providers.Factory(ConversationRepository)

    # Services
    tts_service = providers.Factory(TTSService)

    supabase_sync = providers.Singleton(
        create_supabase_sync,
        config.provided.SUPABASE_URL,
        config.provided.SERVICE_ROLE_KEY,
    )

    supabase_sync_client = providers.Factory(
        SupabaseSyncClient,
        client=supabase_sync
    )

    supabase_admin = supabase_sync
    supabase_async = providers.Singleton(
        create_supabase_async,
        config.provided.SUPABASE_URL,
        config.provided.SERVICE_ROLE_KEY,
    )

    supabase_async_client = providers.Factory(
        SupabaseAsyncClient,
        client=supabase_async
    )

    openai_client = providers.Singleton(
        OpenAI,
        api_key=config.provided.OPENAI_API_KEY,
    )

    openai_service = providers.Factory(
        OpenAIService,
        client=openai_client,
    )

    elevenlabs_session = providers.Singleton(
        lambda key: (
            s := requests.Session(),
            s.headers.update({"xi-api-key": key, "Content-Type":"application/json"}),
            s
        )[-1],
        config.provided.ELEVENLABS_API_KEY
    )

    elevenlabs_service = providers.Factory(
        ElevenLabsService,
        supabase=     supabase_sync,
        session=     elevenlabs_session,
        default_voice_id=config.provided.ELEVENLABS_VOICE_ID,
    )
