from dependency_injector.wiring import Provide, inject
from app.containers import Container
from supabase import Client
from dataclasses import dataclass
from app.services.supabase_sync import SupabaseSyncClient

@dataclass
class MessageRepository:
    supabase_sync_client: SupabaseSyncClient

    def fetch_text(self, message_id: str) -> dict:
        row = (
            self.supabase_sync_client.table("messages")
            .select("assistant_text,conversation_id")
            .eq("id", message_id)
            .single()
            .execute()
            .data
        ) or {}
        return row

    def update(self, message_id: str, fields: dict):
        self.supabase_sync_client.table("messages").update(fields).eq("id", message_id).execute()

    def fetch_all_history_for_conversation(self, conversation_id: str) -> list[dict]:
        """
        Returns a list of rows (dictionaries) for all messages in this conversation,
        ordered by created_at. Each row contains at least "sender_role", "transcription", and "assistant_text".
        """
        history = (
            self.supabase_sync_client
                .table("messages")
                .select("sender_role, transcription, assistant_text")
                .eq("conversation_id", conversation_id)
                .order("created_at")
                .execute()
                .data
            or []
        )
        return history

    def fetch_history_for_conversation(self, conversation_id: str) -> List[Dict]:
        """
        Returns every non‐invalidated message row for a given conversation_id,
        ordered by created_at. Each row includes sender_role, transcription,
        assistant_text, and created_at.
        """
        history = (
            self.supabase_sync_client
                .table("messages")
                .select("sender_role, transcription, assistant_text, created_at")
                .eq("conversation_id", conversation_id)
                .eq("invalidated", False)
                .order("created_at")
                .execute()
                .data
            or []
        )
        return history
