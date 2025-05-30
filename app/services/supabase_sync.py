from app.containers import Container
from dataclasses import dataclass
from supabase import Client

@dataclass
class SupabaseSyncClient:
    client: Client

    def table(self, name: str):
        return self.client.table(name)
