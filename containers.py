import requests
from dependency_injector import containers, providers
from supabase import create_client as create_client_sync
from supabase._async.client import create_client as create_client_async
from openai import OpenAI
from config import config
from repositories.messages import MessageRepository
from repositories.conversations import ConversationRepository
from repositories.therapists import TherapistRepository
from repositories.user_profiles import UserProfileRepository


from services.openai_service import OpenAIService
from services.elevenlabs_service import ElevenLabsService
from services.summarizer_service import SummarizerService
from services.chat_service import ChatService
from services.whisper_service import WhisperService

class Container(containers.DeclarativeContainer):

    config = providers.Object(config)

    # Database clients
    supabase_sync = providers.Singleton(
        create_client_sync,
        config.provided.SUPABASE_URL,
        config.provided.SERVICE_ROLE_KEY,
    )

    supabase_async = providers.Singleton(
        create_client_async,
        config.provided.SUPABASE_URL,
        config.provided.SERVICE_ROLE_KEY,
    )

    # Repositories
    message_repository = providers.Factory(
        MessageRepository,
        supabase_sync_client=supabase_sync
    )

    conversation_repository = providers.Factory(
        ConversationRepository,
        supabase_sync_client=supabase_sync
    )

    therapist_repository = providers.Factory(
        TherapistRepository,
        supabase_sync_client=supabase_sync
    )

    # External API clients
    openai_client = providers.Singleton(
        OpenAI,
        api_key=config.provided.OPENAI_API_KEY,
    )

    elevenlabs_session = providers.Singleton(
        lambda key: (
            s := requests.Session(),
            s.headers.update({"xi-api-key": key, "Content-Type":"application/json"}),
            s
        )[-1],
        config.provided.ELEVENLABS_API_KEY
    )

    # Services
    openai_service = providers.Factory(
        OpenAIService,
        client=openai_client,
    )

    elevenlabs_service = providers.Factory(
        ElevenLabsService,
        message_repo=message_repository,
        conversation_repo=conversation_repository,
        therapist_repo=therapist_repository,
        supabase_sync=supabase_sync,
        elevenlabs_session=elevenlabs_session,
        default_voice_id=config.provided.ELEVENLABS_VOICE_ID,
    )

    summarizer_service = providers.Factory(
        SummarizerService,
        supabase_sync=supabase_sync,
        openai_service=openai_service,
        message_repo=message_repository,
        conversation_repo=conversation_repository,
    )

    chat_service = providers.Singleton(
        ChatService,
        supabase_sync=supabase_sync,
        supabase_async=supabase_async,
        openai_client=openai_client,
        message_repo=message_repository,
        conversation_repo=conversation_repository,
        therapist_repo=therapist_repository,
        user_profile_repo=UserProfileRepository(sync_client),
    )

    whisper_service = providers.Factory(
        WhisperService,
        supabase_sync=supabase_sync,
        openai_client=openai_client,
        elevenlabs_session=elevenlabs_session,
    )
