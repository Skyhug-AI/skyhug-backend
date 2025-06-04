from dataclasses import dataclass
from supabase import Client
from typing import Optional


@dataclass
class ConversationRepository:
    supabase_sync_client: Client

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

    def update_summary(self, conversation_id: str, summary: str) -> None:
        """
        Writes `summary` into the conversations.memory_summary column.
        """
        self.supabase_sync_client \
            .table("conversations") \
            .update({"memory_summary": summary}) \
            .eq("id", conversation_id) \
            .execute()

    def mark_ended(self, conversation_id: str) -> None:
        """
        Sets ended = True for a given conversation.
        """
        self.supabase_sync_client \
            .table("conversations") \
            .update({"ended": True}) \
            .eq("id", conversation_id) \
            .execute()

    def fetch_stale_conversation_ids(self, cutoff_iso: str) -> list[str]:
            """
            Returns a list of conversation IDs where ended=False and updated_at < cutoff_iso.
            """
            rows = (
                self.supabase_sync_client
                    .table("conversations")
                    .select("id")
                    .eq("ended", False)
                    .lt("updated_at", cutoff_iso)
                    .execute()
                    .data
                or []
            )
            return [r["id"] for r in rows]

    def fetch_memory_summary(self, conversation_id: str) -> str:
        """
        Returns the memory_summary for a given conversation_id, or "" if none.
        """
        row = (
            self.supabase_sync_client
                .table("conversations")
                .select("memory_summary")
                .eq("id", conversation_id)
                .single()
                .execute()
                .data
        ) or {}
        return row.get("memory_summary", "")

    def clear_memory_if_resummarize_flag(self, conversation_id: str) -> None:
        """
        If needs_resummarization is True, clear memory_summary and reset the flag.
        """
        row = (
            self.supabase_sync_client
                .table("conversations")
                .select("needs_resummarization")
                .eq("id", conversation_id)
                .single()
                .execute()
                .data
        ) or {}

        if row.get("needs_resummarization"):
            self.supabase_sync_client \
                .table("conversations") \
                .update({"memory_summary": "", "needs_resummarization": False}) \
                .eq("id", conversation_id) \
                .execute()

    def fetch_therapist_id(self, conversation_id: str) -> Optional[str]:
        """
        Returns the therapist_id for the given conversation_id,
        or None if not set.
        """
        row = (
            self.supabase_sync_client
                .table("conversations")
                .select("therapist_id")
                .eq("id", conversation_id)
                .single()
                .execute()
                .data
        ) or {}
        return row.get("therapist_id")
