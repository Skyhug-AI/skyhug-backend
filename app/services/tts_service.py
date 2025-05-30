# app/services/tts_service.py
from dependency_injector.wiring import Provide, inject
from app.containers import Container
from app.repositories.messages import MessageRepository
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from dataclasses import dataclass

@dataclass
class TTSService:
    message_repo: MessageRepository
    conversation_repo: ConversationRepository
    eleven_labs_session = ElevenLabsSession

    def stream_snippet(self, message_id: str, snippet: int, default_voice: str):
        row = self._msg_repo.fetch_text(message_id)
        text = row.get("assistant_text", "")
        if not text:
            raise HTTPException(404, "No assistant_text")

        # sanitize & split (reuse your utils)
        from app.utils.regex_utils import sanitize_text, split_sentences
        sentences = split_sentences(sanitize_text(text))
        if snippet < 0 or snippet >= len(sentences):
            raise HTTPException(400, "snippet out of range")
        piece = sentences[snippet]

        # check voice mode & pick voice_id
        convo = self._convo_repo.fetch(row["conversation_id"])
        if not convo.get("voice_enabled"):
            raise HTTPException(403, "TTS only in Voice Mode")
        voice_id = convo.get("elevenlabs_voice_id") or default_voice

        upstream = self._session.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            json={"text": piece, "voice_settings": {...}, "stream": True},
            stream=True,
            timeout=(5, None),
        )
        upstream.raise_for_status()
        return StreamingResponse(
            upstream.iter_content(chunk_size=4096),
            media_type="audio/mpeg",
            headers={"Cache-Control":"no-cache","Transfer-Encoding":"chunked"},
        )
