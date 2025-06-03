from dataclasses import dataclass
from app.services.supabase_sync import SupabaseSyncClient


@dataclass
class ConversationRepository:
    supabase_sync_client: SupabaseSyncClient

    def fetch_voice_info(self, conversation_id: str) -> dict:
        """
        Returns a dict with keys "voice_enabled" and "therapist_id",
        or an empty dict if none was found.
        """
        row = (
            self.supabase_sync_client
                .table("conversations")
                .select("voice_enabled,therapist_id")
                .eq("id", conversation_id)
                .single()
                .execute()
                .data
        ) or {}
        return row
