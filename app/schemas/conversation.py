from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


class ChatMessageBase(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1)


class ChatMessageCreate(ChatMessageBase):
    pass


class ChatMessageResponse(ChatMessageBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationStart(BaseModel):
    business_slug: str = Field(..., min_length=1, max_length=120)
    user_session_id: str | None = Field(None, max_length=120)
    channel: str | None = "CHAT"


class ConversationResponse(BaseModel):
    id: UUID
    business_id: UUID
    channel: str
    status: str
    outcome: str | None = None
    started_at: datetime
    last_message_at: datetime | None = None

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    conversation_id: str
    message: str
    intent: str | None = None
    booking_id: str | None = None
    booking_status: str | None = None
    public_tracking_id: str | None = None
    payment_url: str | None = None
    requires_action: str | None = None
    available_slots: list | None = None
    service_options: list | None = None


class HandoffRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=80)
    contact_name: str = Field(..., min_length=1, max_length=120)
    contact_phone: str = Field(..., min_length=6, max_length=40)
    contact_email: str = Field(..., max_length=255)


class HandoffResponse(BaseModel):
    id: UUID
    public_ticket_id: str
    handoff_token: str
    status: str
    message: str = "A team member will contact you shortly."

    class Config:
        from_attributes = True


class HandoffStatusResponse(BaseModel):
    public_ticket_id: str
    status: str
    reason: str
    created_at: datetime
    resolved_at: datetime | None = None
