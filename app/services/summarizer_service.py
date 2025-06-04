from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from app.services.supabase_sync import SupabaseSyncClient
from app.services.openai_service import OpenAIService
from app.repositories.messages import MessageRepository
from app.repositories.conversations import ConversationRepository
import threading

@dataclass
class SummarizerService:
    supabase: SupabaseSyncClient
    openai_service: OpenAIService
    message_repo: MessageRepository
    conversation_repo: ConversationRepository

    def summarize_and_store(self, conversation_id: str) -> None:
        """
        1) Fetch all messages for `conversation_id`.
        2) If there are ≥4 assistant replies, ask OpenAI for a short summary.
        3) Store that summary in `conversations.memory_summary`.
        """
        history = self.message_repo.fetch_all_history_for_conversation(conversation_id)

        # 2) require at least 4 assistant replies
        assistant_count = sum(1 for m in history if m["sender_role"] == "assistant")
        if assistant_count < 4:
            print(f"🛑 Skipping summary for conv {conversation_id} — only {assistant_count} assistant replies")
            return

        # 3) build chat history for OpenAI
        chat_history = []
        for m in history:
            role = "user" if m["sender_role"] == "user" else "assistant"
            content = m["transcription"] if role == "user" else m["assistant_text"]
            chat_history.append({"role": role, "content": content})

        # 4) ask OpenAI for a noun‐phrase summary
        prompt = """
        You are a concise summarizer. Return a single plain noun phrase (≤8 words)
        that captures the conversation topic. Do NOT return a full sentence,
        no punctuation, no articles like “the” or “a”.
        """.strip()

        resp = self.openai_service.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": prompt}] + chat_history,
            temperature=0.5,
            max_tokens=30,
        )
        raw = resp.choices[0].message.content.strip()
        summary = raw.rstrip(".!?,;").strip()

        # 5) store it
        self.conversation_repo.update_summary(conversation_id, summary)
        print(f"🧠 Stored memory for conv {conversation_id}: {summary}")

    def close_inactive_conversations(self, interval_hours: int = 1) -> None:
        """
        1) Find conversations where `ended = False` and `updated_at` < (now − 1h).
        2) For each, run summarize_and_store and then set `ended = True`.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=interval_hours)
        print("⏰ Checking for inactive conversations...")

        # 1) find only active convs that have gone quiet for >1h
        cutoff_iso = cutoff.isoformat()
        stale_ids = self.conversation_repo.fetch_stale_conversation_ids(cutoff_iso)

        for conv_id in stale_ids:
            self.summarize_and_store(conv_id)
            self.conversation_repo.mark_ended(conv_id)

    def schedule_cleanup(self, interval_hours: int = 1) -> None:
        """
        Kick off `close_inactive_conversations()` immediately, then
        schedule it to run again every `interval_hours` hours.
        """
        def _job():
            try:
                self.close_inactive_conversations(interval_hours=interval_hours)
            except Exception:
                # swallow exceptions so the Timer loop does not die
                pass
            # schedule next run
            threading.Timer(interval_hours * 3600, _job).start()

        # run for the first time right away
        _job()
