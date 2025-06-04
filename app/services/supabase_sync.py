from app.containers import Container
from dataclasses import dataclass
from supabase import Client

@dataclass
class SupabaseSyncClient:
    client: Client

    def table(self, name: str):
        return self.client.table(name)

    def update_status(self, table_name: str, record_id: str, fields: dict) -> None:
        """
        A convenience wrapper around supabase.table(table_name).update(fields).eq("id", record_id).execute().
        """
        self.client.table(table_name).update(fields).eq("id", record_id).execute()
