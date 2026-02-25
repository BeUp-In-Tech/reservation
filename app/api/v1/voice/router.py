"""
Twilio Voice Webhook Router.
Rule-based voice flow using TwiML - no AI/LLM.

Twilio calls these endpoints and receives TwiML XML responses.
Flow is driven by DTMF key presses (digits).

FLOW:
  /twilio/incoming -> greeting + gather (1=details, 2=no)
  /twilio/after-greeting -> routes based on digit
  /twilio/after-details -> service details + gather (1=again, 0=book, 9=human, 8=bye)
  /twilio/after-details-choice -> routes based on digit
  /twilio/how-can-help -> gather (1=details, 0=book, 9=human, 8=bye)
  /twilio/help-choice -> routes based on digit
  /twilio/goodbye -> end call
  /twilio/escalate -> end call with escalation
  /twilio/book-redirect -> end call, trigger chat handoff
"""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import uuid as uuid_lib

from app.core.database import get_db
from app.core.config import settings
from app.services.voice_flow_service import VoiceFlowService
from app.services.call_session_service import CallSessionService
from app.services.handoff_service import HandoffService
from app.models import CallSession, Conversation, ConversationMessage, Business

router = APIRouter()


def twiml_response(twiml: str) -> Response:
    """Return TwiML XML response."""
    return Response(content=twiml, media_type="application/xml")


# ==================== INITIATE CALL (API - called by frontend) ====================

from pydantic import BaseModel


class StartCallRequest(BaseModel):
    business_id: str
    service_id: str
    caller_phone: str | None = None
    provider_call_id: str | None = None


class ChatHandoffResponse(BaseModel):
    success: bool
    conversation_id: str
    business_id: str
    first_message: str


@router.post("/calls/start")
async def start_call(
    request: StartCallRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Start a new voice call session.
    Called by frontend when customer clicks 'Call' on a service card.
    Returns call session info. Frontend then initiates Twilio call.
    """
    from twilio.rest import Client

    voice_flow = VoiceFlowService(db)

    # Validate business
    biz = await voice_flow.get_business(request.business_id)
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")

    # Validate service belongs to business
    svc = await voice_flow.get_service(request.service_id)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    if svc["business_id"] != request.business_id:
        raise HTTPException(status_code=400, detail="Service does not belong to this business")

    # Create call session
    call_service = CallSessionService(db)
    call_result = await call_service.start_call(
        business_id=request.business_id,
        caller_phone=request.caller_phone,
        provider_call_id=request.provider_call_id,
        channel="VOICE"
    )

    # Store service_id in extra_data
    result = await db.execute(
        select(CallSession).where(CallSession.id == uuid_lib.UUID(call_result["call_session_id"]))
    )
    call_session = result.scalar_one()
    call_session.extra_data = {
        "service_id": request.service_id,
        "business_id": request.business_id,
    }
    await db.commit()

    # If caller_phone provided, initiate outbound Twilio call
    if request.caller_phone and settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
        try:
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            base_url = settings.BASE_URL.rstrip("/")

            call = client.calls.create(
                to=request.caller_phone,
                from_=settings.TWILIO_PHONE_NUMBER,
                url=f"{base_url}/api/v1/voice/twilio/incoming?call_session_id={call_result['call_session_id']}&service_id={request.service_id}&business_id={request.business_id}",
                method="POST",
            )
            call_session.provider_call_id = call.sid
            await db.commit()

            call_result["twilio_call_sid"] = call.sid
        except Exception as e:
            call_result["twilio_error"] = str(e)

    call_result["service_id"] = request.service_id
    call_result["service_name"] = svc["service_name"]
    call_result["mode"] = "RULE_BASED"

    return call_result


# ==================== TWILIO WEBHOOKS ====================

@router.post("/twilio/incoming")
async def twilio_incoming(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Twilio calls this URL when the call connects.
    Greets the customer and asks if they want service details.
    """
    form = await request.form()
    call_session_id = request.query_params.get("call_session_id", "")
    service_id = request.query_params.get("service_id", "")
    business_id = request.query_params.get("business_id", "")

    voice_flow = VoiceFlowService(db)
    greeting = await voice_flow.get_greeting(business_id, service_id)

    base_url = settings.BASE_URL.rstrip("/")
    action_url = f"{base_url}/api/v1/voice/twilio/after-greeting?call_session_id={call_session_id}&service_id={service_id}&business_id={business_id}"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="dtmf" numDigits="1" action="{action_url}" method="POST" timeout="10">
        <Say voice="Polly.Joanna">{greeting}</Say>
    </Gather>
    <Say voice="Polly.Joanna">We didn't receive any input. Goodbye!</Say>
    <Hangup/>
</Response>"""

    return twiml_response(twiml)


@router.post("/twilio/after-greeting")
async def twilio_after_greeting(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """After greeting: 1=hear details, 2=no thanks."""
    form = await request.form()
    digit = form.get("Digits", "")
    call_session_id = request.query_params.get("call_session_id", "")
    service_id = request.query_params.get("service_id", "")
    business_id = request.query_params.get("business_id", "")

    base_url = settings.BASE_URL.rstrip("/")
    params = f"call_session_id={call_session_id}&service_id={service_id}&business_id={business_id}"

    if digit == "1":
        # YES - read service details
        return Response(
            content=f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Redirect method="POST">{base_url}/api/v1/voice/twilio/after-details?{params}</Redirect>
</Response>""",
            media_type="application/xml"
        )
    elif digit == "2":
        # NO - how can I help
        return Response(
            content=f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Redirect method="POST">{base_url}/api/v1/voice/twilio/how-can-help?{params}</Redirect>
</Response>""",
            media_type="application/xml"
        )
    else:
        # Invalid input - repeat
        voice_flow = VoiceFlowService(db)
        greeting = await voice_flow.get_greeting(business_id, service_id)
        action_url = f"{base_url}/api/v1/voice/twilio/after-greeting?{params}"

        return twiml_response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">Sorry, that wasn't a valid option.</Say>
    <Gather input="dtmf" numDigits="1" action="{action_url}" method="POST" timeout="10">
        <Say voice="Polly.Joanna">{greeting}</Say>
    </Gather>
    <Say voice="Polly.Joanna">We didn't receive any input. Goodbye!</Say>
    <Hangup/>
</Response>""")


@router.post("/twilio/after-details")
async def twilio_after_details(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Read service details, then ask what next."""
    form = await request.form()
    service_id = request.query_params.get("service_id", "")
    call_session_id = request.query_params.get("call_session_id", "")
    business_id = request.query_params.get("business_id", "")

    voice_flow = VoiceFlowService(db)
    details = await voice_flow.get_service_details_text(service_id)
    after_prompt = await voice_flow.get_after_details_prompt()

    base_url = settings.BASE_URL.rstrip("/")
    params = f"call_session_id={call_session_id}&service_id={service_id}&business_id={business_id}"
    action_url = f"{base_url}/api/v1/voice/twilio/after-details-choice?{params}"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">Here are the details. {details}</Say>
    <Pause length="1"/>
    <Gather input="dtmf" numDigits="1" action="{action_url}" method="POST" timeout="10">
        <Say voice="Polly.Joanna">{after_prompt}</Say>
    </Gather>
    <Say voice="Polly.Joanna">We didn't receive any input. Goodbye!</Say>
    <Hangup/>
</Response>"""

    return twiml_response(twiml)


@router.post("/twilio/after-details-choice")
async def twilio_after_details_choice(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """After details: 1=again, 0=book via chat, 9=human, 8=bye."""
    form = await request.form()
    digit = form.get("Digits", "")
    call_session_id = request.query_params.get("call_session_id", "")
    service_id = request.query_params.get("service_id", "")
    business_id = request.query_params.get("business_id", "")

    base_url = settings.BASE_URL.rstrip("/")
    params = f"call_session_id={call_session_id}&service_id={service_id}&business_id={business_id}"

    if digit == "1":
        # Hear details again
        return twiml_response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Redirect method="POST">{base_url}/api/v1/voice/twilio/after-details?{params}</Redirect>
</Response>""")

    elif digit == "0":
        # Book via chat
        return twiml_response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Redirect method="POST">{base_url}/api/v1/voice/twilio/book-redirect?{params}</Redirect>
</Response>""")

    elif digit == "9":
        # Human escalation
        return twiml_response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Redirect method="POST">{base_url}/api/v1/voice/twilio/escalate?{params}</Redirect>
</Response>""")

    elif digit == "8":
        # Goodbye
        return twiml_response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Redirect method="POST">{base_url}/api/v1/voice/twilio/goodbye?{params}</Redirect>
</Response>""")

    else:
        # Invalid - repeat options
        voice_flow = VoiceFlowService(db)
        not_understood = await voice_flow.get_not_understood_message()
        action_url = f"{base_url}/api/v1/voice/twilio/after-details-choice?{params}"

        return twiml_response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="dtmf" numDigits="1" action="{action_url}" method="POST" timeout="10">
        <Say voice="Polly.Joanna">{not_understood}</Say>
    </Gather>
    <Say voice="Polly.Joanna">We didn't receive any input. Goodbye!</Say>
    <Hangup/>
</Response>""")


@router.post("/twilio/how-can-help")
async def twilio_how_can_help(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """User said no to details - offer options."""
    form = await request.form()
    call_session_id = request.query_params.get("call_session_id", "")
    service_id = request.query_params.get("service_id", "")
    business_id = request.query_params.get("business_id", "")

    voice_flow = VoiceFlowService(db)
    prompt = await voice_flow.get_how_can_help_prompt()

    base_url = settings.BASE_URL.rstrip("/")
    params = f"call_session_id={call_session_id}&service_id={service_id}&business_id={business_id}"
    action_url = f"{base_url}/api/v1/voice/twilio/help-choice?{params}"

    return twiml_response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="dtmf" numDigits="1" action="{action_url}" method="POST" timeout="10">
        <Say voice="Polly.Joanna">{prompt}</Say>
    </Gather>
    <Say voice="Polly.Joanna">We didn't receive any input. Goodbye!</Say>
    <Hangup/>
</Response>""")


@router.post("/twilio/help-choice")
async def twilio_help_choice(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle choice from how-can-help: 1=details, 0=book, 9=human, 8=bye."""
    form = await request.form()
    digit = form.get("Digits", "")
    call_session_id = request.query_params.get("call_session_id", "")
    service_id = request.query_params.get("service_id", "")
    business_id = request.query_params.get("business_id", "")

    base_url = settings.BASE_URL.rstrip("/")
    params = f"call_session_id={call_session_id}&service_id={service_id}&business_id={business_id}"

    if digit == "1":
        return twiml_response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Redirect method="POST">{base_url}/api/v1/voice/twilio/after-details?{params}</Redirect>
</Response>""")

    elif digit == "0":
        return twiml_response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Redirect method="POST">{base_url}/api/v1/voice/twilio/book-redirect?{params}</Redirect>
</Response>""")

    elif digit == "9":
        return twiml_response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Redirect method="POST">{base_url}/api/v1/voice/twilio/escalate?{params}</Redirect>
</Response>""")

    elif digit == "8":
        return twiml_response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Redirect method="POST">{base_url}/api/v1/voice/twilio/goodbye?{params}</Redirect>
</Response>""")

    else:
        voice_flow = VoiceFlowService(db)
        not_understood = await voice_flow.get_not_understood_message()
        action_url = f"{base_url}/api/v1/voice/twilio/help-choice?{params}"

        return twiml_response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="dtmf" numDigits="1" action="{action_url}" method="POST" timeout="10">
        <Say voice="Polly.Joanna">{not_understood}</Say>
    </Gather>
    <Say voice="Polly.Joanna">We didn't receive any input. Goodbye!</Say>
    <Hangup/>
</Response>""")


# ==================== TERMINAL ACTIONS ====================

@router.post("/twilio/goodbye")
async def twilio_goodbye(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """End the call with a goodbye message."""
    form = await request.form()
    call_session_id = request.query_params.get("call_session_id", "")

    voice_flow = VoiceFlowService(db)
    goodbye = await voice_flow.get_goodbye_message()

    # Update call session
    await _end_call_session(db, call_session_id, "COMPLETED", "AI_RESOLVED", "INFO_PROVIDED")

    return twiml_response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">{goodbye}</Say>
    <Hangup/>
</Response>""")


@router.post("/twilio/escalate")
async def twilio_escalate(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Escalate to human - end call for now."""
    form = await request.form()
    call_session_id = request.query_params.get("call_session_id", "")
    business_id = request.query_params.get("business_id", "")

    voice_flow = VoiceFlowService(db)
    escalation_msg = await voice_flow.get_escalation_message()

    # Create handoff request
    if call_session_id:
        try:
            result = await db.execute(
                select(CallSession).where(CallSession.id == uuid_lib.UUID(call_session_id))
            )
            call_session = result.scalar_one_or_none()

            if call_session and call_session.conversation_id:
                handoff_service = HandoffService(db)
                await handoff_service.create_handoff(
                    business_id=business_id or str(call_session.business_id),
                    conversation_id=str(call_session.conversation_id),
                    reason="Customer requested human assistance via phone",
                    contact_name=None,
                    contact_phone=call_session.caller_phone,
                )
        except Exception:
            pass

    await _end_call_session(db, call_session_id, "COMPLETED", "HUMAN_ESCALATED", "ESCALATED_TO_HUMAN")

    return twiml_response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">{escalation_msg}</Say>
    <Hangup/>
</Response>""")


@router.post("/twilio/book-redirect")
async def twilio_book_redirect(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Redirect to chat for booking - end call."""
    form = await request.form()
    call_session_id = request.query_params.get("call_session_id", "")
    service_id = request.query_params.get("service_id", "")
    business_id = request.query_params.get("business_id", "")

    voice_flow = VoiceFlowService(db)
    redirect_msg = await voice_flow.get_booking_redirect_message()

    # Mark call session for chat handoff
    if call_session_id:
        try:
            result = await db.execute(
                select(CallSession).where(CallSession.id == uuid_lib.UUID(call_session_id))
            )
            call_session = result.scalar_one_or_none()
            if call_session:
                call_session.extra_data = {
                    **(call_session.extra_data or {}),
                    "handoff_to_chat": True,
                    "service_id": service_id,
                    "business_id": business_id,
                }
                await db.commit()
        except Exception:
            pass

    await _end_call_session(db, call_session_id, "COMPLETED", "AI_RESOLVED", "BOOKING_CREATED")

    return twiml_response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">{redirect_msg}</Say>
    <Hangup/>
</Response>""")


# ==================== CHAT HANDOFF (called by frontend after call) ====================

@router.post("/calls/{call_session_id}/handoff-to-chat", response_model=ChatHandoffResponse)
async def handoff_to_chat(
    call_session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Create chat conversation after voice call ends with press 0.
    Returns conversation_id so frontend can open chat with service pre-selected.
    """
    result = await db.execute(
        select(CallSession).where(CallSession.id == uuid_lib.UUID(call_session_id))
    )
    call_session = result.scalar_one_or_none()

    if not call_session:
        raise HTTPException(status_code=404, detail="Call session not found")

    extra = call_session.extra_data or {}
    service_id = extra.get("service_id")
    business_id = extra.get("business_id", str(call_session.business_id))

    # Use the chat service to start conversation with pre-selected service
    from app.services.chat_service import ChatService
    chat_service = ChatService(db)

    # Get business slug
    biz_result = await db.execute(
        select(Business).where(Business.id == call_session.business_id)
    )
    business = biz_result.scalar_one_or_none()

    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    chat_result = await chat_service.start_conversation(
        business_slug=business.slug,
        service_id=service_id,
        user_session_id=f"voice-handoff-{call_session_id}",
        channel="CHAT",
    )

    # Link conversation to call session
    call_session.extra_data = {
        **extra,
        "chat_conversation_id": chat_result["conversation_id"],
    }
    await db.commit()

    return ChatHandoffResponse(
        success=True,
        conversation_id=chat_result["conversation_id"],
        business_id=business_id,
        first_message=chat_result.get("first_message", "Welcome! Let's complete your booking."),
    )


# ==================== GET CALL ====================

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
        except Exception:
            pass

    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    return call


# ==================== HELPER ====================

async def _end_call_session(
    db: AsyncSession,
    call_session_id: str,
    status: str,
    resolution_type: str,
    outcome: str,
):
    """Update call session to ended state."""
    if not call_session_id:
        return

    try:
        result = await db.execute(
            select(CallSession).where(CallSession.id == uuid_lib.UUID(call_session_id))
        )
        call_session = result.scalar_one_or_none()
        if call_session:
            call_session.status = status
            call_session.resolution_type = resolution_type
            call_session.outcome = outcome
            call_session.ended_at = datetime.utcnow()

            if call_session.started_at:
                duration = (datetime.utcnow() - call_session.started_at.replace(tzinfo=None)).total_seconds()
                call_session.duration_seconds = int(duration)

            await db.commit()
    except Exception:
        pass