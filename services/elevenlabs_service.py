from dataclasses import dataclass
from typing import Optional
from fastapi import HTTPException
from supabase import Client
import requests, re
from fastapi.responses import StreamingResponse
from repositories.messages import MessageRepository
from repositories.conversations import ConversationRepository
from repositories.therapists import TherapistRepository

@dataclass
class ElevenLabsService:
    message_repo: MessageRepository
    conversation_repo: ConversationRepository
    therapist_repo: TherapistRepository
    supabase_sync: Client
    elevenlabs_session: requests.Session
    default_voice_id: str

    def warmup_elevenlabs_pool(self) -> None:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.default_voice_id}"
        for _ in range(3):
            try:
                self.elevenlabs_session.head(url, timeout=1)
            except:
                pass
        try:
            dummy = self.elevenlabs_session.post(
                url,
                json={
                    "text": ".",
                    "voice_settings": {
                        "stability": 0.2,
                        "similarity_boost": 0.2,
                        "latency_boost": True,
                    },
                    "stream": True,
                },
                stream=True,
                timeout=(1, 1),
            )
            dummy.close()
        except:
            pass

    def fetch_and_stream(self, message_id: str, snippet: int = 0) -> StreamingResponse:
        """
        Full flow for the /tts-stream/{message_id} endpoint:
          1) fetch assistant_text + conversation_id
          2) sanitize & split
          3) verify voice_enabled & pick voice_id from therapist
          4) proxy the stream to ElevenLabs and return a FastAPI StreamingResponse
        """
        msg = self.message_repo.fetch_text(message_id)
        text = msg.get("assistant_text", "")
        if not text:
            raise HTTPException(404, "No assistant_text for that message")

        sanitized = re.sub(r"[*/{}\[\]<>&#@_\\|+=%]", "", text)
        sentences = re.split(r'(?<=[.!?])\s+', sanitized)
        if snippet < 0 or snippet >= len(sentences):
            raise HTTPException(400, "snippet index out of range")
        piece = sentences[snippet].strip()

        convo = self.conversation_repo.fetch_voice_info(msg["conversation_id"])

        if not convo.get("voice_enabled"):
            raise HTTPException(403, "TTS only in Voice Mode")

        therapist_id = convo.get("therapist_id")
        if therapist_id:
            eleven_id = self.therapist_repo.fetch_voice_id(therapist_id)
            voice_id = eleven_id or self.default_voice_id
        else:
            voice_id = self.default_voice_id

        chunk_generator = self.stream_tts_snippet(piece, custom_voice_id=voice_id)

        return StreamingResponse(
            chunk_generator,
            media_type="audio/mpeg",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Transfer-Encoding": "chunked",
            },
        )

    def stream_tts_snippet(
            self,
            text: str,
            custom_voice_id: Optional[str] = None,
            stability: float = 0.45,
            similarity_boost: float = 0.45,
            latency_boost: bool = True,
        ):
            """
            Proxy a streaming TTS call for a given chunk of text.
            Returns a generator of bytes from the upstream response.
            """
            voice_id = custom_voice_id or self.default_voice_id
            upstream = self.elevenlabs_session.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                json={
                    "text": text,
                    "voice_settings": {
                        "stability": stability,
                        "similarity_boost": similarity_boost,
                        "latency_boost": latency_boost,
                    },
                    "stream": True,
                },
                stream=True,
                timeout=(5, None),
            )
            upstream.raise_for_status()
            return upstream.iter_content(chunk_size=4096)
