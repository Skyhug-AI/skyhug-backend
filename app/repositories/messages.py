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
