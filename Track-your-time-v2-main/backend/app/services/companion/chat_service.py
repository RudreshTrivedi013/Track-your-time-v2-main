"""
chat_service.py — Orchestrates the full AI chat flow.

Flow:
1. Receive user message
2. Build context
3. Generate prompt
4. Call Groq
5. Parse structured response
6. Execute actions
7. Save chat history
8. Return response
"""
import logging
import uuid
from datetime import datetime, timezone

from groq import AsyncGroq
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.companion import ChatMessage, MessageRole
from app.models.user import User
from app.schemas.companion import ChatMessageOut
from app.services.companion.context_builder import build_context
from app.services.companion.intent_parser import parse_intent
from app.services.companion.prompt_builder import (
    build_system_prompt,
    build_user_message,
)
from app.services.companion.task_actions import execute_intent

logger = logging.getLogger(__name__)
_UTC = timezone.utc

_client = None


def _get_groq_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    return _client


async def process_chat_message(
    db: AsyncSession, user: User, content: str, task_id: uuid.UUID | None
) -> list[ChatMessageOut]:
    """Process a user chat message end-to-end, returning the new message pair."""
    now = datetime.now(_UTC)

    # 1. Save user message
    user_msg = ChatMessage(
        id=uuid.uuid4(),
        user_id=user.id,
        task_id=task_id,
        role=MessageRole.user,
        content=content,
        token_count=len(content.split()),
        created_at=now,
    )
    db.add(user_msg)
    # Flush to ensure it's recorded (in case context builder fetches it, though
    # context builder will fetch it anyway if it shares the same session).
    await db.flush()

    # 2. Build context
    ctx = await build_context(db, user)

    # 3. Generate prompt
    system_prompt = build_system_prompt(ctx)
    user_prompt = build_user_message(content, ctx)

    # 4. Call Groq
    client = _get_groq_client()
    try:
        response = await client.chat.completions.create(
            model=settings.GROQ_MODEL,
            max_tokens=1024,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        raw_text = response.choices[0].message.content or ""
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        raw_text = (
            '{"action":"unknown", "reply":"I am having trouble connecting to my '
            'brain right now. Please try again later."}'
        )

    # 5. Parse structured response
    intent = parse_intent(raw_text)

    # 6. Execute actions
    try:
        await execute_intent(db, user, intent)
    except Exception as e:
        logger.error(f"Error executing intent: {e}")
        intent.reply = (
            "I understood you, but I ran into a database error trying to do that."
        )

    # 7. Save chat history
    assistant_msg = ChatMessage(
        id=uuid.uuid4(),
        user_id=user.id,
        task_id=task_id,
        role=MessageRole.assistant,
        content=intent.reply,
        token_count=len(intent.reply.split()),
        created_at=datetime.now(_UTC),
    )
    db.add(assistant_msg)

    # Commit all side-effects and the message pair
    await db.commit()
    
    await db.refresh(user_msg)
    await db.refresh(assistant_msg)

    return [
        ChatMessageOut.model_validate(user_msg),
        ChatMessageOut.model_validate(assistant_msg),
    ]
