import uuid
from datetime import datetime

from pydantic import BaseModel


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