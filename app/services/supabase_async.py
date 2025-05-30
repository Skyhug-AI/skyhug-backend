# app/services/supabase_async_client.py
from dataclasses import dataclass
import asyncio
from supabase._async.client import Client as AsyncClient
from realtime import RealtimeSubscribeStates
from dependency_injector.wiring import inject, Provide
from app.containers import Container
from app.services.handlers import handle_ai_record

@dataclass
class SupabaseAsyncClient:
    client: AsyncClient

    async def subscribe_to_messages(self):
        # ---- callbacks ----
        def on_insert(payload):
            msg = payload["data"]["record"]
            if (
                msg["sender_role"] == "user"
                and msg.get("ai_status") == "pending"
                and msg.get("transcription_status") == "done"
                and not msg.get("ai_started")
            ):
                loop = asyncio.get_event_loop()
                loop.run_in_executor(None, handle_ai_record, msg)

        def on_update(payload):
            msg = payload["data"]["record"]
            if (
                msg["sender_role"] == "user"
                and msg.get("ai_status") == "pending"
                and msg.get("edited_at")
                and not msg.get("ai_started")
            ):
                loop = asyncio.get_event_loop()
                loop.run_in_executor(None, handle_ai_record, msg)

        def on_subscribe(status, err):
            if status == RealtimeSubscribeStates.SUBSCRIBED:
                print("🔌 SUBSCRIBED to messages_changes")
            else:
                print("❗ Realtime status:", status, err)

        # ---- subscription ----
        channel = self.client.channel("messages_changes")
        channel.on_postgres_changes(
            event="INSERT", schema="public", table="messages", callback=on_insert
        )
        channel.on_postgres_changes(
            event="UPDATE", schema="public", table="messages", callback=on_update
        )
        await channel.subscribe(on_subscribe)

        # keep alive
        await asyncio.Event().wait()
