import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# --- Documents ---

class DocumentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    status: str
    page_count: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Chat ---

class ChatRequest(BaseModel):
    message: str
    conversation_id: uuid.UUID | None = None
    model: str | None = None  # Override default chat_model for this request
    effort: Literal["fast", "balanced", "thorough"] = "balanced"  # Effort level — gates actor-critic pass (AGT-04, D-09-04)


class ConversationUpdate(BaseModel):
    title: str = Field(..., max_length=500)


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    response: str
    sources: list[str]  # chunk contents used for context


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationListItemResponse(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: datetime
    messages: list[MessageResponse]

    model_config = {"from_attributes": True}

    # --- API Keys ---

class ApiKeyCreate(BaseModel):
    provider: str  # "openai", "anthropic", "ollama"
    api_key: str   # The actual key — only sent on creation, never returned


class ApiKeyResponse(BaseModel):
    id: uuid.UUID
    provider: str
    key_hint: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Memories ---

class MemoryResponse(BaseModel):
    id: uuid.UUID
    category: str
    content: str
    is_active: bool
    edited_by_user: bool
    created_at: datetime
    updated_at: datetime
    source_conversation_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class MemoryCreate(BaseModel):
    category: str  # "fact" | "preference" | "context"
    content: str


class MemoryUpdate(BaseModel):
    content: str