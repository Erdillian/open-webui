"""
Open WebUI Filter Function: memory_filter

Inject enriched context (profile + memories + timestamps + anti-sycophancy)
before each LLM call, and capture exchanges for memory extraction afterwards.

Install this function in Open WebUI via Admin > Functions > Create Function,
or ensure it is auto-registered on startup.
"""
import logging
from typing import Optional

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)


class Filter:
    """Filter class required by Open WebUI's function loading mechanism."""

    class Valves(BaseModel):
        enabled: bool = Field(default=True, description="Enable memory layer context injection")
        k_passive: int = Field(default=8, description="Number of memories to inject automatically")
        anti_sycophancy_enabled: bool = Field(default=True, description="Inject anti-sycophancy block")
        timestamp_prefix_messages: bool = Field(default=False, description="Prefix each user message with timestamp")
        priority: int = Field(default=0, description="Filter priority (lower = earlier)")

    def __init__(self):
        self.valves = self.Valves()

    async def inlet(self, body: dict, __user__: dict) -> dict:
        """Inject enriched system prompt BEFORE the LLM call."""
        if not self.valves.enabled:
            return body

        try:
            from open_webui.memory_layer.services.context_builder import (
                build_system_prompt,
                inject_date_markers,
            )

            user_id = __user__.get("id", "")
            if not user_id:
                return body

            messages = body.get("messages", [])
            if not messages:
                return body

            # Get last user message
            user_message = ""
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    user_message = msg.get("content", "")
                    break

            # Build enriched system prompt
            system_prompt = await build_system_prompt(
                user_id=user_id,
                user_message=user_message,
                chat_history=messages,
                k_passive=self.valves.k_passive,
                anti_sycophancy=self.valves.anti_sycophancy_enabled,
            )

            # Inject or replace system message
            if messages and messages[0].get("role") == "system":
                existing = messages[0].get("content", "")
                messages[0]["content"] = system_prompt + "\n\n" + existing
            else:
                messages.insert(0, {"role": "system", "content": system_prompt})

            # Inject date markers
            messages = inject_date_markers(messages)

            # Optional: prefix timestamps to user messages
            if self.valves.timestamp_prefix_messages:
                for msg in messages:
                    if msg.get("role") == "user" and msg.get("timestamp"):
                        ts_str = msg["timestamp"]
                        try:
                            from datetime import datetime

                            dt = datetime.fromtimestamp(ts_str)
                            prefix = dt.strftime("[%d/%m %H:%M] ")
                            msg["content"] = prefix + msg.get("content", "")
                        except Exception:
                            pass

            body["messages"] = messages

            # Log injected memories count for debugging
            log.debug(f"memory_filter inlet: injected context for user {user_id}")

        except Exception as e:
            log.error(f"memory_filter inlet error: {e}")
            # Fail open: don't break the chat if memory layer fails

        return body

    async def outlet(self, body: dict, __user__: dict) -> dict:
        """Capture exchange AFTER LLM response for memory extraction."""
        log.info("memory_filter outlet called")
        if not self.valves.enabled:
            log.info("memory_filter outlet: disabled")
            return body

        try:
            user_id = __user__.get("id", "")
            if not user_id:
                log.info("memory_filter outlet: no user_id")
                return body

            messages = body.get("messages", [])
            chat_id = body.get("chat_id")
            log.info(f"memory_filter outlet: user={user_id}, chat_id={chat_id}, messages_count={len(messages)}")

            # If assistant response is not yet in body (streaming), fetch from DB
            if not messages or messages[-1].get("role") != "assistant":
                if chat_id:
                    try:
                        from open_webui.models.chats import Chats

                        chat = await Chats.get_chat_by_id(chat_id)
                        if chat and chat.chat:
                            history = chat.chat.get("history", {}).get("messages", {})
                            if history:
                                sorted_msgs = sorted(
                                    history.items(),
                                    key=lambda x: int(x[0]) if str(x[0]).isdigit() else x[0]
                                )
                                msgs = [v for k, v in sorted_msgs]
                                if msgs and msgs[-1].get("role") == "assistant":
                                    messages = msgs
                    except Exception:
                        pass

            if len(messages) >= 2:
                # Capture last user + assistant exchange
                last_exchange = messages[-2:]

                # Enqueue for extraction
                try:
                    from open_webui.memory_layer.workers.extraction_queue import enqueue

                    await enqueue(
                        user_id=user_id,
                        messages=last_exchange,
                        chat_id=chat_id,
                    )
                    log.info(f"memory_filter outlet: enqueued exchange for user {user_id}")
                except Exception as queue_e:
                    # extraction_queue may not exist yet during early phases
                    log.info(f"memory_filter outlet: could not enqueue: {queue_e}")
            else:
                log.info(f"memory_filter outlet: not enough messages ({len(messages)})")

        except Exception as e:
            log.error(f"memory_filter outlet error: {e}")
            # Fail open

        return body
