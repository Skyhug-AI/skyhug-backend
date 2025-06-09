from dataclasses import dataclass
from supabase import Client
from typing import Any

@dataclass
class UserProfileRepository:
    supabase_sync_client: Client

    def fetch_profile(self, user_id: str) -> dict[str, Any]:
        row = (
            self.supabase_sync_client
                .table("user_profiles")
                .select(
                    "age, gender, sexual_preferences, career, "
                    "self_diagnosed_issues, topics_on_mind, additional_info"
                )
                .eq("user_id", user_id)
                .single()
                .execute()
                .data
        ) or {}
        return row
