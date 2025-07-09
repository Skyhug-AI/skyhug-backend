from dataclasses import dataclass
import json
import asyncio
from datetime import datetime, timezone
import re
from openai import OpenAI
from realtime import RealtimeSubscribeStates
from collections import defaultdict
from dataclasses import field
from supabase import Client
from supabase._async.client import AsyncClient
from repositories.messages import MessageRepository
from repositories.conversations import ConversationRepository
from repositories.therapists import TherapistRepository
from repositories.user_profiles import UserProfileRepository
from constants.prompts import PROFILE_PROMPT_TEMPLATE

from constants.prompts import (
    DEFAULT_SYSTEM_PROMPT,
    SKY_EXAMPLE_DIALOG,
    PERSONA_TEMPLATE,
    FUNCTION_DEFS,
)

@dataclass
class ChatService:
    supabase_sync: Client
    supabase_async: AsyncClient
    openai_client: OpenAI
    message_repo: MessageRepository
    conversation_repo: ConversationRepository
    therapist_repo: TherapistRepository
    user_profile_repo: UserProfileRepository
    START_TS: str = datetime.now(timezone.utc).isoformat()
    MAX_HISTORY: int = 10

    _profile_injected_sessions: set[str] = field(default_factory=set, init=False)
    _reminded_fields: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set), init=False)
    # define which keywords map to which profile fields
    _keyword_map: dict[str, list[str]] = field(default_factory=lambda: {
        "career": ["job", "career", "work", "office"],
        "self_diagnosed_issues": ["anxiety", "depression", "ptsd", "panic", "stress"],
        "topics_on_mind": ["mindful", "mind", "think", "ponder", "topic", "interest", "anxious"],
    }, init=False)

    def build_chat_payload(self, conv_id: str, voice_mode: bool = False) -> list[dict]:
        """
        1) Load memory_summary (and clear “needs_resummarization” if flagged)
        2) Load message history
        3) Load any therapist override (system_prompt)
        4) Build `system_prompt` (override > persona_template > default)
        5) Prepend that + SKY_EXAMPLE_DIALOG
        6) Append “memory” message if brand‐new conversation
        7) Turn DB rows into chat turns
        8) If too many turns, ask OpenAI for a brief summary of older turns
        """
        # Fetch any saved memory
        memory = self.conversation_repo.fetch_memory_summary(conv_id)

        # 1a) if flagged for resummarization, clear it
        self.conversation_repo.clear_memory_if_resummarize_flag(conv_id)
        memory = "" if self.conversation_repo.fetch_memory_summary(conv_id) == "" else self.conversation_repo.fetch_memory_summary(conv_id)

        # Fetch the message history
        history = self.message_repo.fetch_history_for_conversation(conv_id)

        # fetch which therapist this convo is using
        therapist_id = self.conversation_repo.fetch_therapist_id(conv_id)
        trow = self.therapist_repo.fetch_therapist_persona(therapist_id) if therapist_id else {}

        # 4) pick which system_prompt to use
        if trow.get("system_prompt"):
            system_prompt = trow["system_prompt"]
        elif trow:
            specialties_list = ", ".join(trow.get("specialties", []))
            system_prompt = PERSONA_TEMPLATE.format(
                name=trow["name"],
                description=trow["description"],
                bio=trow["bio"],
                approach=trow["approach"],
                session_structure=trow["session_structure"],
                specialties_list=specialties_list,
            )
        else:
            system_prompt = DEFAULT_SYSTEM_PROMPT

        # ─── 4a) inject profile ONCE at session start ────────────────────────────
        row = self.supabase_sync.table("conversations") \
            .select("patient_id") \
            .eq("id", conv_id) \
            .single() \
            .execute()
        patient_id = (row.data or {}).get("patient_id")

        profile = {}
        if patient_id:
            profile = self.user_profile_repo.fetch_profile(patient_id) or {}

        # ─── build mini-profile text ────────────────────────────────────────────
        mini = None
        if profile:
            mini = (
                f"Profile: {profile.get('age','?')}-year-old {profile.get('gender','')}, "
                f"{profile.get('career','Unknown')} who struggles with {profile.get('self_diagnosed_issues','none')}. "
                f"Often thinks about {', '.join(profile.get('topics_on_mind',[]))}."
            )


        if patient_id and conv_id not in self._profile_injected_sessions:
            profile = self.user_profile_repo.fetch_profile(patient_id)
            print(f"🛠️ DEBUG fetched profile: {profile}")
            if profile:
                # render only non‐empty fields
                details = []
                for key, val in profile.items():
                    if val:
                        label = key.replace("_", " ").capitalize()
                        # arrays → comma list
                        if isinstance(val, list):
                            val = ", ".join(val)
                        details.append(f"{label}: {val}")
                profile_str = "\n".join(details)
                # append to system prompt
                system_prompt += "\n\n" + PROFILE_PROMPT_TEMPLATE.format(
                    profile_details=profile_str
                )    
                print("🔍 [debug] profile injected for session", conv_id)
                self._profile_injected_sessions.add(conv_id)

        # ─── 4a) inject mini profile AGAIN every 5 turns  ────────────────────────────
        # 5) build initial messages
        messages: list[dict] = [{"role": "system", "content": system_prompt}] + SKY_EXAMPLE_DIALOG

        if mini:
            messages.append({"role": "system", "content": mini})
        messages.append({"role": "system", "content": system_prompt})
        messages.extend(SKY_EXAMPLE_DIALOG)

        # 5a) if brand‐new but memory exists, inject a “last time we talked about…” message
        if memory and not history:
            messages.append({
                "role": "assistant",
                "content": f"Last time we spoke, we discussed {memory}. Would you like to continue?"
            })

        # 6) convert DB rows into chat turns
        turns: list[dict] = []
        for m in history:
            if m["sender_role"] == "user":
                turns.append({"role": "user", "content": m["transcription"]})
            else:
                turns.append({"role": "assistant", "content": m["assistant_text"]})

        # 7) if too many turns, ask GPT to summarize the older ones
        if len(turns) > self.MAX_HISTORY:
            summary_resp = self.openai_client.chat.completions.create(
                model="gpt-4-turbo" if voice_mode else "gpt-4-turbo",
                messages=messages
                         + [{"role": "assistant", "content": "Please summarize the earlier conversation briefly."}]
                         + turns[:-self.MAX_HISTORY],
                temperature=0.3,
                max_tokens=600,
            )
            summary = summary_resp.choices[0].message.content
            messages += [
                {"role": "assistant", "content": f"Summary of earlier conversation: {summary}"}
            ] + turns[-self.MAX_HISTORY:]
        else:
            messages += turns
        
        # ─── 5b) keyword-triggered reminders ───────────────────────────────
        # look at the last user message (if any)
        if conv_id in self._profile_injected_sessions and history:
            print("🔍 [debug] entering drift logic for", conv_id)
            last = history[-1]
            if last["sender_role"] == "user":
                user_text = (last.get("transcription") or "").lower()
                # reuse same fetched profile
                profile = self.user_profile_repo.fetch_profile(patient_id)
                for field, keywords in self._keyword_map.items():
                    if (
                        field not in self._reminded_fields[conv_id]
                        and any(kw in user_text for kw in keywords)
                        and profile.get(field)
                    ):
                        reminder = f"Reminder: user’s {field.replace('_',' ')} is {profile[field]}."
                        print("🔔 Drift reminder injected:", reminder) 

                        # ——— determine the new_topic phrase ———
                        if field == "topics_on_mind":
                            # look for “about X” or “think about X”
                            m = re.search(r"\b(?:about|think about)\s+([\w\s]+)", user_text)
                            new_topic = m.group(1).strip() if m else next(kw for kw in keywords if kw in user_text)
                        else:
                            # for other fields, just use the matched keyword
                            new_topic = next(kw for kw in keywords if kw in user_text)

                        # ——— persist it if new ———
                        old_topics = profile.get("topics_on_mind") or []
                        if field == "topics_on_mind" and new_topic and new_topic not in old_topics:
                            updated_topics = old_topics + [new_topic]
                            self.supabase_sync.table("user_profiles") \
                                .update({"topics_on_mind": updated_topics}) \
                                .eq("user_id", patient_id) \
                                .execute()
                            print(f"💾 Added topic_on_mind '{new_topic}' to user_profiles")

                        print("🔔 Drift reminder injected:", reminder)
                        messages.append({"role": "system", "content": reminder})
                        self._reminded_fields[conv_id].add(field)

        return messages

    def handle_ai_record(self, msg: dict) -> None:
        """
        1) Mark msg.ai_started = True
        2) Check voice_enabled on the conversation
        3) Build chat payload
        4) Pick model based on user_text
        5) If chat mode: stream deltas into DB
           If voice mode: run full completion, insert assistant_text + snippet_url
        6) Finally set original msg.ai_status = "done"
        """
        # 1) skip if already started
        if msg.get("ai_started"):
            return

        self.supabase_sync.table("messages") \
            .update({"ai_started": True}) \
            .eq("id", msg["id"]) \
            .execute()

        print(f"💬 ⏳ Generating AI reply for message {msg['id']}…")
        try:
            # 2) figure out if voice_mode is on
            conv_row = (
                self.supabase_sync
                .table("conversations")
                .select("voice_enabled")
                .eq("id", msg["conversation_id"])
                .single()
                .execute()
            )
            voice_mode = bool(conv_row.data.get("voice_enabled", False))

            # 3) build payload
            payload = self.build_chat_payload(msg["conversation_id"], voice_mode=voice_mode)

            # 4) model selection
            user_text = (msg.get("transcription") or "").strip()
            lc = user_text.lower()

            if lc.startswith(("what is ", "define ")):
                model_name, max_tokens = "gpt-3.5-turbo", 150
            elif lc.startswith(("i feel", "i’m feeling", "i am feeling", "i am", "i'm")):
                model_name, max_tokens = "gpt-4-turbo", 600
            elif lc.startswith(("why ", "how ", "explain ", "describe ", "compare ", "recommend ", "suggest ")):
                model_name, max_tokens = "gpt-4-turbo", 600
            else:
                words = [w for w in user_text.split() if w.strip()]
                if len(words) > 6:
                    model_name, max_tokens = "gpt-4-turbo", 600
                else:
                    model_name, max_tokens = "gpt-3.5-turbo", 150

            print("Selected model:", model_name)

            # 5) generate & store assistant reply
            if not voice_mode:
                # —— CHAT MODE: stream deltas into a new “assistant” row ——
                insert_resp = self.supabase_sync.table("messages").insert({
                    "conversation_id": msg["conversation_id"],
                    "sender_role":     "assistant",
                    "assistant_text":  "",
                    "ai_status":       "pending",
                    "ai_started":      False,
                    "tts_status":      "done"
                }).execute()
                mid = insert_resp.data[0]["id"]

                # stream GPT‐style responses back into that “assistant_text” column
                stream = self.openai_client.chat.completions.create(
                    model=model_name,
                    messages=payload,
                    temperature=0.7,
                    stream=True,
                    max_tokens=max_tokens
                )

                accumulated = ""
                finish_reason = None
                for chunk in stream:
                    delta = chunk.choices[0].delta.content or ""
                    accumulated += delta
                    if chunk.choices[0].finish_reason:
                        finish_reason = chunk.choices[0].finish_reason

                    # write partial text back
                    self.supabase_sync.table("messages") \
                        .update({"assistant_text": accumulated}) \
                        .eq("id", mid) \
                        .execute()

                # if truncated mid‐sentence, send a continuation prompt
                if finish_reason == "length" or not accumulated.strip().endswith((".", "!", "?")):
                    cont = self.openai_client.chat.completions.create(
                        model=model_name,
                        messages=payload + [{"role": "assistant", "content": accumulated}],
                        temperature=0.7,
                        max_tokens=200
                    )
                    extra = cont.choices[0].message.content or ""
                    accumulated = accumulated.rstrip() + " " + extra.strip()
                    self.supabase_sync.table("messages") \
                        .update({"assistant_text": accumulated}) \
                        .eq("id", mid) \
                        .execute()

                # mark AI done
                self.supabase_sync.table("messages") \
                    .update({"ai_status": "done"}) \
                    .eq("id", mid) \
                    .execute()

            else:
                # —— VOICE MODE: full completion + snippet_url ——
                resp = self.openai_client.chat.completions.create(
                    model=model_name,
                    messages=payload,
                    temperature=0.7,
                    max_tokens=max_tokens,
                    functions=FUNCTION_DEFS,
                    function_call="auto"
                )
                choice = resp.choices[0].message

                # handle function calls (e.g. suicidal mentions)
                if getattr(choice, "function_call", None):
                    args = json.loads(choice.function_call.arguments)
                    content = (
                        "I'm so sorry you’re feeling this way. "
                        f"If you ever think about harming yourself, call {args['hotline_number']}."
                    )
                else:
                    # base content
                    content = choice.content or ""
                    finish_reason = resp.choices[0].finish_reason
                    if finish_reason == "length" or not content.strip().endswith((".", "!", "?")):
                        cont = self.openai_client.chat.completions.create(
                            model=model_name,
                            messages=payload + [{"role": "assistant", "content": content}],
                            temperature=0.7,
                            max_tokens=200,
                            functions=FUNCTION_DEFS,
                            function_call="auto"
                        )
                        extra = cont.choices[0].message.content or ""
                        content = content.rstrip() + " " + extra.lstrip()

                # insert the row with full assistant_text
                insert_resp = self.supabase_sync.table("messages").insert({
                    "conversation_id": msg["conversation_id"],
                    "sender_role":     "assistant",
                    "assistant_text":  content,
                    "ai_status":       "done",
                    "tts_status":      "pending",
                    "snippet_url":     ""
                }).execute()
                mid = insert_resp.data[0]["id"]

                # seed snippet_url
                snippet_url = f"/tts-stream/{mid}?snippet=0"
                try:
                    self.supabase_sync.table("messages") \
                        .update({"snippet_url": snippet_url}) \
                        .eq("id", mid) \
                        .execute()
                except Exception:
                    self.supabase_sync.table("messages") \
                        .update({"tts_status": "error"}) \
                        .eq("id", mid) \
                        .execute()

            # 6) mark the original user message AI‐done
            self.supabase_sync.table("messages") \
                .update({"ai_status": "done"}) \
                .eq("id", msg["id"]) \
                .execute()

            print(f"✅ Assistant response created for message {msg['id']}")
        except Exception as e:
            print(f"❌ AI error for {msg['id']}: {e}")
            self.supabase_sync.table("messages") \
                .update({"ai_status": "error"}) \
                .eq("id", msg["id"]) \
                .execute()

    async def start_realtime(self) -> None:
        """
        Kick off a Realtime subscription to “messages” table. Whenever
        a new user‐message row arrives (or gets edited), call handle_ai_record.
        """

        def on_insert(payload):
            msg = payload["data"]["record"]
            # only pick up new text messages (or audio → transcription complete)
            if (
                msg["sender_role"] == "user"
                and msg.get("ai_status") == "pending"
                and msg.get("transcription_status") == "done"
                and not msg.get("ai_started")
            ):
                loop = asyncio.get_event_loop()
                loop.run_in_executor(None, self.handle_ai_record, msg)

        def on_update(payload):
            msg = payload["data"]["record"]
            # only pick up true edits (trascription → done, or user‐edited)
            if (
                msg["sender_role"] == "user"
                and msg.get("ai_status") == "pending"
                and msg.get("edited_at")  # only set by your edit‐message call
                and not msg.get("ai_started")
            ):
                loop = asyncio.get_event_loop()
                loop.run_in_executor(None, self.handle_ai_record, msg)

        def on_subscribe(status, err):
            if status == RealtimeSubscribeStates.SUBSCRIBED:
                print("🔌 SUBSCRIBED to messages_changes")
            else:
                print("❗ Realtime status:", status, err)

        channel = self.supabase_async.channel("messages_changes")
        channel.on_postgres_changes(event="INSERT", schema="public", table="messages", callback=on_insert)
        channel.on_postgres_changes(event="UPDATE", schema="public", table="messages", callback=on_update)
        await channel.subscribe(on_subscribe)

        # never return
        await asyncio.Event().wait()

    def fetch_pending(self, table: str, **conds) -> list[dict]:
        """
        Fetch rows matching conds from the given table. If table == "messages",
        only return any that were created after self.START_TS.
        """
        q = self.supabase_sync.table(table).select("*").match(conds)
        if table == "messages":
            q = q.gt("created_at", self.START_TS)
        return q.execute().data or []


    # def schedule_cleanup(self, interval_hours: int = 1) -> None:
    #     """
    #     Run close_inactive_conversations() every interval_hours via a repeating Timer.
    #     """
    #     from app.services.summarizer_service import SummarizerService

    #     def job():
    #         summarizer = SummarizerService(
    #             message_repo=self.message_repo,
    #             conversation_repo=self.conversation_repo,
    #             openai_service=<Injected OpenAIService>  # however you wire it
    #         )
    #         summarizer.close_inactive_conversations(interval_hours=interval_hours)
    #         threading.Timer(interval_hours * 3600, job).start()

    #     job()
