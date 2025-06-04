import io
from dataclasses import dataclass
from openai import OpenAI
from app.services.supabase_sync import SupabaseSyncClient
import requests

@dataclass
class WhisperService:
    supabase: SupabaseSyncClient
    openai_client: OpenAI
    elevenlabs_session: requests.Session

    def download_audio(self, path: str, bucket: str = "raw-audio") -> bytes:
        """
        Given a Supabase storage path, generate a signed URL and fetch the audio bytes.
        """
        signed = (
            self.supabase
                .client.storage
                .from_(bucket)
                .create_signed_url(path, 60)["signedURL"]
        )
        resp = self.elevenlabs_session.get(signed, timeout=5)
        resp.raise_for_status()
        return resp.content

    def handle_transcription_record(self, msg: dict) -> None:
        """
        1) Download raw audio from Supabase storage.
        2) Call Whisper to transcribe.
        3) Update messages.transcription & transcription_status.
        """
        message_id = msg["id"]
        audio_path = msg.get("audio_path")
        if not audio_path:
            return

        print(f"📝 ⏳ Transcribing message {message_id}…")
        try:
            audio_bytes = self.download_audio(audio_path)
            resp = self.openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=io.BytesIO(audio_bytes),
            )
            self.supabase.update_status(
                "messages",
                message_id,
                {"transcription": resp.text, "transcription_status": "done"}
            )
            print(f"✅ Transcribed {message_id}: “{resp.text[:30]}…”")
        except Exception as e:
            self.supabase.update_status(
                "messages",
                message_id,
                {"transcription_status": "error"}
            )
            print(f"❌ Transcription error for {message_id}:", e)
