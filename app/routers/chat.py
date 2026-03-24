import uuid
import json
from sse_starlette.sse import EventSourceResponse

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Conversation, Message
from app.schemas import ChatRequest, ChatResponse, ConversationResponse
from app.services.retrieval import retrieve_relevant_chunks
from app.services.llm import (
    generate_response,
    generate_response_stream,
    build_conversation_history,
    get_user_api_key,
)
from app.config import settings
from app.limiter import limiter

from app.auth import get_current_user_id 

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
@limiter.limit("30/minute")
async def chat(
    request_obj: Request, # slowapi needs the raw Request
    request: ChatRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a message and get a RAG-augmented response.

    If conversation_id is provided, continues that conversation.
    Otherwise, creates a new one.
    """
    # Get or create conversation
    if request.conversation_id:
        result = await db.execute(
            select(Conversation).where(Conversation.id == request.conversation_id)
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = Conversation(
            user_id=user_id,
            title=request.message[:100],  # Use first 100 chars as title
        )
        db.add(conversation)
        await db.flush()

    # Store user message
    user_message = Message(
        conversation_id=conversation.id,
        user_id=user_id,
        role="user",
        content=request.message,
    )
    db.add(user_message)
    await db.flush()

    # Retrieve relevant chunks
    chunks = await retrieve_relevant_chunks(db, request.message, user_id)

    # Build conversation history (skip for brand new conversations)
    history = []
    if request.conversation_id:
        history = await build_conversation_history(
            db, conversation.id, settings.memory_max_tokens
        )

    # get user api key
    user_api_key = await get_user_api_key(db, user_id, "openai")

    # Generate response
    response_text = await generate_response(
        request.message, chunks, history, api_key=user_api_key
    )

    # Store assistant message
    assistant_message = Message(
        conversation_id=conversation.id,
        user_id=user_id,
        role="assistant",
        content=response_text,
    )
    db.add(assistant_message)

    await db.commit()

    return ChatResponse(
        conversation_id=conversation.id,
        response=response_text,
        sources=[c["content"] for c in chunks],
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a conversation with all messages."""
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
            )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a message and get a streaming RAG-augmented response via SSE.

    Events:
      - type "token": individual response tokens
      - type "sources": the retrieved chunks (sent first)
      - type "done": final message with conversation_id and full response
    """
    # Get or create conversation (same logic as non-streaming)
    if request.conversation_id:
        result = await db.execute(
            select(Conversation).where(Conversation.id == request.conversation_id)
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = Conversation(
            user_id=user_id,
            title=request.message[:100],
        )
        db.add(conversation)
        await db.flush()

    # Store user message
    user_message = Message(
        conversation_id=conversation.id,
        user_id=user_id,
        role="user",
        content=request.message,
    )
    db.add(user_message)
    await db.flush()

    # Retrieve relevant chunks
    chunks = await retrieve_relevant_chunks(db, request.message, user_id)

    # Build conversation history
    history = []
    if request.conversation_id:
        history = await build_conversation_history(
            db, conversation.id, settings.memory_max_tokens
        )

    # get user api key
    user_api_key = await get_user_api_key(db, user_id, "openai")

    async def event_generator():
        # Send sources first so the frontend can display them
        yield {
            "event": "sources",
            "data": json.dumps([c["content"] for c in chunks]),
        }

        # Stream the response
        full_response = ""
        async for token in generate_response_stream(
            request.message, chunks, history, api_key=user_api_key
        ):
            full_response += token
            yield {
                "event": "token",
                "data": json.dumps({"token": token}),
            }

        # Save the complete response to DB
        assistant_message = Message(
            conversation_id=conversation.id,
            user_id=user_id,
            role="assistant",
            content=full_response,
        )
        db.add(assistant_message)
        await db.commit()

        # Send the final event with metadata
        yield {
            "event": "done",
            "data": json.dumps({
                "conversation_id": str(conversation.id),
                "response": full_response,
            }),
        }

    return EventSourceResponse(event_generator())