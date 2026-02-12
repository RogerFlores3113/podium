import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Conversation, Message
from app.schemas import ChatRequest, ChatResponse, ConversationResponse
from app.services.retrieval import retrieve_relevant_chunks
from app.services.llm import generate_response

router = APIRouter(prefix="/chat", tags=["chat"])

DEFAULT_USER_ID = "user_01"


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
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
            user_id=DEFAULT_USER_ID,
            title=request.message[:100],  # Use first 100 chars as title
        )
        db.add(conversation)
        await db.flush()

    # Store user message
    user_message = Message(
        conversation_id=conversation.id,
        user_id=DEFAULT_USER_ID,
        role="user",
        content=request.message,
    )
    db.add(user_message)

    # Retrieve relevant chunks
    chunks = await retrieve_relevant_chunks(db, request.message, DEFAULT_USER_ID)

    # Generate response
    response_text = await generate_response(request.message, chunks)

    # Store assistant message
    assistant_message = Message(
        conversation_id=conversation.id,
        user_id=DEFAULT_USER_ID,
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
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a conversation with all messages."""
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation