# app/services/elevenlabs_service.py
from dataclasses import dataclass
from typing import Optional
import requests
from fastapi import HTTPException
from app.utils.regex_utils import sanitize_text, split_sentences
from app.services.supabase_sync import SupabaseSyncClient

@dataclass
class ElevenLabsService:
    supabase: SupabaseSyncClient
    elevenlabs_session: requests.Session
    default_voice_id: str     

    def download_audio(self, path: str, bucket: str = "raw-audio") -> bytes:
        """
        Given a Supabase storage path, generate a signed URL and fetch the audio bytes.
        """
        signed = (
            self.supabase
            .storage
            .from_(bucket)
            .create_signed_url(path, 60)["signedURL"]
        )
        resp = self.elevenlabs_session.get(signed, timeout=5)
        resp.raise_for_status()
        return resp.content

    def warmup_pool(self) -> None:
        """
        Hit HEAD + a tiny POST to the default voice to spin up the ElevenLabs pool.
        Call this once on app startup.
        """
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

    def stream_tts_snippet(
        self,
        text: str,
        voice_id: Optional[str] = None,
        stability: float = 0.45,
        similarity_boost: float = 0.45,
        latency_boost: bool = True,
    ):
        """
        Proxy a streaming TTS call for a given chunk of text.
        Returns a requests.Response-like iterable of bytes.
        """
        vid = voice_id or self.default_voice_id
        upstream = self.elevenlabs_session.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{vid}",
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

    def fetch_and_stream(self, message_id: str, snippet: int = 0):
        """
        Full flow for your `/tts-stream/{message_id}` endpoint:
          1. fetch assistant_text + conversation_id
          2. sanitize & split
          3. verify voice_enabled & pick voice_id from therapist
          4. proxy the stream
        """
        # 1) fetch
        row = (
            self.supabase
            .table("messages")
            .select("assistant_text,conversation_id")
            .eq("id", message_id)
            .single()
            .execute()
            .data
        ) or {}
        text = row.get("assistant_text", "")
        if not text:
            raise HTTPException(404, "No assistant_text for that message")

        # 2) split
        sentences = split_sentences(sanitize_text(text))
        if snippet < 0 or snippet >= len(sentences):
            raise HTTPException(400, "snippet index out of range")
        piece = sentences[snippet].strip()

        # 3) pick voice_id
        convo = (
            self.supabase
            .table("conversations")
            .select("voice_enabled,therapist_id")
            .eq("id", row["conversation_id"])
            .single()
            .execute()
            .data
        ) or {}
        if not convo.get("voice_enabled"):
            raise HTTPException(403, "TTS only in Voice Mode")

        tid = convo.get("therapist_id")
        if tid:
            trow = (
                self.supabase
                .table("therapists")
                .select("elevenlabs_voice_id")
                .eq("id", tid)
                .single()
                .execute()
                .data
            ) or {}
            vid = trow.get("elevenlabs_voice_id") or self.default_voice_id
        else:
            vid = self.default_voice_id

        # 4) proxy & return generator
        return self.stream_tts_snippet(piece, voice_id=vid)
