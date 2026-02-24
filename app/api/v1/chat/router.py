from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import uuid

from app.core.database import get_db
from app.services.chat_service import ChatService
from app.schemas.conversation import (
    ConversationStart,
    ConversationResponse,
    ChatRequest,
    ChatResponse,
)
from app.models import CallSession, Conversation, ConversationMessage
from datetime import datetime

router = APIRouter(prefix="/chat", tags=["Chat"])


class VoiceHandoffRequest(BaseModel):
    call_session_id: str


# ==================== START CONVERSATION ====================

@router.post("/conversations", response_model=dict)
async def start_conversation(
    request: ConversationStart,
    db: AsyncSession = Depends(get_db)
):
    """Start a new chat conversation with a business."""
    try:
        chat_service = ChatService(db)
        result = await chat_service.start_conversation(
            business_slug=request.business_slug,
            service_id=request.service_id,
            user_session_id=request.user_session_id,
            channel=request.channel or "CHAT"
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


# ==================== START FROM VOICE HANDOFF ====================

@router.post("/from-voice", response_model=dict)
async def start_from_voice(
    request: VoiceHandoffRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Start chat conversation after voice call ends with 00.
    AI automatically sends first message asking for booking details.
    """
    
    # Find call session
    try:
        call_uuid = uuid.UUID(request.call_session_id)
        result = await db.execute(
            select(CallSession).where(CallSession.id == call_uuid)
        )
    except ValueError:
        result = await db.execute(
            select(CallSession).where(CallSession.public_call_id == request.call_session_id)
        )

    call_session = result.scalar_one_or_none()

    if not call_session:
        raise HTTPException(status_code=404, detail="Call session not found")

    # Create new conversation for chat
    conversation = Conversation(
        business_id=call_session.business_id,
        channel="CHAT",
        status="STARTED",
        started_at=datetime.utcnow(),
    )
    db.add(conversation)
    await db.flush()

    # Update call session with chat conversation link
    extra = call_session.extra_data or {}
    extra["chat_conversation_id"] = str(conversation.id)
    call_session.extra_data = extra

    # AI's first message asking for ALL booking details
    first_message = """Great! Let's complete your booking.

Please provide:
- Which service would you like?
- What date and time works for you?
- Your name
- Your email
- Your phone number

You can share everything in one message!"""

    ai_msg = ConversationMessage(
        business_id=call_session.business_id,
        conversation_id=conversation.id,
        role="assistant",
        content=first_message,
        created_at=datetime.utcnow()
    )
    db.add(ai_msg)

    await db.commit()

    # Load business info
    chat_service = ChatService(db)
    business_info = await chat_service._load_business_info(call_session.business_id)

    return {
        "conversation_id": str(conversation.id),
        "business_id": str(call_session.business_id),
        "call_session_id": str(call_session.id),
        "first_message": first_message,
        "available_services": business_info.get("available_services", []),
    }


# ==================== SEND MESSAGE ====================

@router.post("/conversations/{conversation_id}/messages", response_model=ChatResponse)
async def send_message(
    conversation_id: str,
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """Send a message in an existing conversation and get AI response."""
    try:
        chat_service = ChatService(db)
        result = await chat_service.send_message(
            conversation_id=conversation_id,
            user_message=request.message
        )

        return ChatResponse(
            conversation_id=result["conversation_id"],
            message=result["response"],
            intent=result.get("intent"),
            booking_id=result.get("public_tracking_id"),
            booking_status=result.get("booking_status"),
            public_tracking_id=result.get("public_tracking_id"),
            payment_url=result.get("payment_url"),
            requires_action=result.get("requires_action"),
            available_slots=result.get("available_slots"),
            service_options=result.get("service_options"),
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing message: {str(e)}"
        )


# ==================== GET CONVERSATION ====================

@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get details of a conversation."""
    chat_service = ChatService(db)
    result = await chat_service.get_conversation(conversation_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    return result


# ==================== GET CONVERSATION HISTORY ====================

@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_history(
    conversation_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get all messages in a conversation."""
    chat_service = ChatService(db)

    conversation = await chat_service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    messages = await chat_service.get_conversation_history(conversation_id)
    return {"messages": messages}
