from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime
import uuid as uuid_lib

from app.core.database import get_db
from app.services.call_session_service import CallSessionService
from app.services.voice_chat_service import VoiceChatService
from app.models import CallSession, Conversation, ConversationMessage


router = APIRouter()


class StartCallRequest(BaseModel):
    business_id: str
    caller_phone: str | None = None
    provider_call_id: str | None = None


class VoiceMessageRequest(BaseModel):
    call_session_id: str
    message: str


class EndCallRequest(BaseModel):
    call_session_id: str
    pressed_00: bool = False


class ChatHandoffResponse(BaseModel):
    success: bool
    conversation_id: str
    business_id: str
    first_message: str


# ============== Endpoints ==============

@router.post("/calls/start")
async def start_call(
    request: StartCallRequest,
    db: AsyncSession = Depends(get_db)
):
    """Start a new voice call session - INFO ONLY mode."""
    call_service = CallSessionService(db)

    result = await call_service.start_call(
        business_id=request.business_id,
        caller_phone=request.caller_phone,
        provider_call_id=request.provider_call_id,
        channel="VOICE"
    )

    result["greeting"] = "Welcome! I can help you with information about our services. What would you like to know?"
    result["mode"] = "INFO_ONLY"

    return result


@router.post("/calls/message")
async def process_voice_message(
    request: VoiceMessageRequest,
    db: AsyncSession = Depends(get_db)
):
    """Process voice message - INFO ONLY, no booking."""
    
    # Check if user pressed 00 - end call and redirect to chat
    if request.message.strip() == "00":
        # Auto-end call with pressed_00=True
        end_request = EndCallRequest(call_session_id=request.call_session_id, pressed_00=True)
        return await end_call(end_request, db)
    
    # Find call session
    try:
        call_uuid = uuid_lib.UUID(request.call_session_id)
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

    # Get conversation history
    history = []
    if call_session.conversation_id:
        msg_result = await db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == call_session.conversation_id)
            .order_by(ConversationMessage.created_at)
        )
        messages = msg_result.scalars().all()
        history = [{"role": m.role, "content": m.content} for m in messages]

    # Process message (INFO ONLY)
    voice_service = VoiceChatService(db)
    chat_result = await voice_service.process_voice_message(
        business_id=str(call_session.business_id),
        user_message=request.message,
        conversation_history=history
    )

    # Save messages to conversation
    if call_session.conversation_id:
        user_msg = ConversationMessage(
            business_id=call_session.business_id,
            conversation_id=call_session.conversation_id,
            role="user",
            content=request.message,
            created_at=datetime.utcnow()
        )
        ai_msg = ConversationMessage(
            business_id=call_session.business_id,
            conversation_id=call_session.conversation_id,
            role="assistant",
            content=chat_result["response"],
            created_at=datetime.utcnow()
        )
        db.add(user_msg)
        db.add(ai_msg)
        await db.commit()

    return {
        "response": chat_result["response"],
        "ready_to_book": chat_result.get("ready_to_book", False),
        "press_00": chat_result.get("press_00", False),
    }


@router.post("/calls/end")
async def end_call(
    request: EndCallRequest,
    db: AsyncSession = Depends(get_db)
):
    """End voice call - if pressed_00, return chat handoff info."""
    
    # Find call session
    try:
        call_uuid = uuid_lib.UUID(request.call_session_id)
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

    # Update call session
    call_session.status = "COMPLETED"
    call_session.ended_at = datetime.utcnow()
    
    if call_session.started_at:
        duration = (datetime.utcnow() - call_session.started_at.replace(tzinfo=None)).total_seconds()
        call_session.duration_seconds = int(duration)

    if request.pressed_00:
        call_session.resolution_type = "AI_RESOLVED"
        call_session.outcome = "INFO_PROVIDED"
        
        # Mark for chat handoff
        call_session.extra_data = {
            "handoff_to_chat": True,
            "pressed_00": True,
            "call_ended_at": datetime.utcnow().isoformat()
        }
    else:
        call_session.resolution_type = "USER_ABANDONED"
        call_session.outcome = "NO_ACTION"

    await db.commit()

    response = {
        "success": True,
        "call_session_id": str(call_session.id),
        "public_call_id": call_session.public_call_id,
        "status": call_session.status,
        "duration_seconds": call_session.duration_seconds,
    }

    # If pressed 00, include chat handoff info
    if request.pressed_00:
        response["redirect_to_chat"] = True
        response["chat_handoff"] = {
            "business_id": str(call_session.business_id),
            "call_session_id": str(call_session.id),
        }

    return response


@router.post("/calls/{call_session_id}/handoff-to-chat", response_model=ChatHandoffResponse)
async def handoff_to_chat(
    call_session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Create chat conversation after voice call ends with 00.
    Returns conversation_id and AI's first message asking for booking details.
    """
    
    # Find call session
    try:
        call_uuid = uuid_lib.UUID(call_session_id)
        result = await db.execute(
            select(CallSession).where(CallSession.id == call_uuid)
        )
    except ValueError:
        result = await db.execute(
            select(CallSession).where(CallSession.public_call_id == call_session_id)
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

    # Link conversation to call session
    call_session.extra_data = call_session.extra_data or {}
    call_session.extra_data["chat_conversation_id"] = str(conversation.id)

    # Create AI's first message asking for details
    first_message = """Welcome! I'm ready to help you complete your booking.

Please provide the following details:
1. Which service would you like to book?
2. What date and time?
3. Your name
4. Your email
5. Your phone number

You can provide all details in one message or one at a time."""

    ai_msg = ConversationMessage(
        business_id=call_session.business_id,
        conversation_id=conversation.id,
        role="assistant",
        content=first_message,
        created_at=datetime.utcnow()
    )
    db.add(ai_msg)

    await db.commit()

    return ChatHandoffResponse(
        success=True,
        conversation_id=str(conversation.id),
        business_id=str(call_session.business_id),
        first_message=first_message
    )


@router.get("/calls/{call_id}")
async def get_call(
    call_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get call session details."""
    call_service = CallSessionService(db)

    call = await call_service.get_call_by_public_id(call_id)

    if not call:
        try:
            result = await db.execute(
                select(CallSession).where(CallSession.id == uuid_lib.UUID(call_id))
            )
            cs = result.scalar_one_or_none()
            if cs:
                call = call_service._call_to_dict(cs)
        except:
            pass

    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    return call

