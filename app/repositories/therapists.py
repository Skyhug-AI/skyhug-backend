from dataclasses import dataclass
from app.services.supabase_sync import SupabaseSyncClient


@dataclass
class TherapistRepository:
    supabase_sync_client: SupabaseSyncClient

    def fetch_voice_id(self, therapist_id: str) -> str:
        """
        Returns the ElevenLabs voice ID for a given therapist,
        or an empty string if none was found.
        """
        row = (
            self.supabase_sync_client
                .table("therapists")
                .select("elevenlabs_voice_id")
                .eq("id", therapist_id)
                .single()
                .execute()
                .data
        ) or {}
        return row.get("elevenlabs_voice_id", "")


    def fetch_therapist_persona(self, therapist_id: str) -> Dict[str, Any]:
        """
        Returns a dict with keys:
          "system_prompt", "name", "description", "bio",
          "approach", "session_structure", "specialties"
        for the given therapist_id, or an empty dict if none exists.
        """
        row = (
            self.supabase_sync_client
                .table("therapists")
                .select(
                    "system_prompt, name, description, bio, approach, session_structure, specialties"
                )
                .eq("id", therapist_id)
                .single()
                .execute()
                .data
        ) or {}
        return row
