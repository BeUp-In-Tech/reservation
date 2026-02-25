"""
WebSocket-based voice test endpoint.
Simulates the Twilio voice flow over WebSocket for browser testing.
Uses browser's SpeechSynthesis API on the frontend to "speak" responses.

Add to main.py:
    from app.api.v1.voice.ws_test import ws_router as voice_ws_router
    app.include_router(voice_ws_router, prefix="/api/v1/voice", tags=["Voice WS Test"])
"""

import json
import uuid as uuid_lib
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.services.voice_flow_service import VoiceFlowService
from app.services.call_session_service import CallSessionService
from app.services.handoff_service import HandoffService
from app.models import CallSession

ws_router = APIRouter()


class VoiceCallState:
    """Tracks the current state of a voice call over WebSocket."""

    def __init__(self, business_id: str, service_id: str, call_session_id: str = None):
        self.business_id = business_id
        self.service_id = service_id
        self.call_session_id = call_session_id
        self.step = "greeting"  # greeting, after_greeting, after_details, how_can_help, ended


@ws_router.websocket("/ws/voice-test")
async def voice_test_ws(websocket: WebSocket):
    """
    WebSocket endpoint for testing the voice flow in browser.

    Client sends JSON:
        {"action": "start", "business_id": "...", "service_id": "..."}
        {"action": "press", "digit": "1"}

    Server sends JSON:
        {"type": "speak", "text": "Hello! ...", "step": "greeting", "options": [...]}
        {"type": "ended", "reason": "goodbye"}
        {"type": "handoff_to_chat", "conversation_id": "...", "business_slug": "..."}
    """
    await websocket.accept()

    state = None

    # Get DB session
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            while True:
                data = await websocket.receive_text()
                msg = json.loads(data)
                action = msg.get("action")

                if action == "start":
                    business_id = msg.get("business_id")
                    service_id = msg.get("service_id")

                    if not business_id or not service_id:
                        await websocket.send_json({"type": "error", "text": "business_id and service_id required"})
                        continue

                    voice_flow = VoiceFlowService(db)

                    # Validate
                    biz = await voice_flow.get_business(business_id)
                    svc = await voice_flow.get_service(service_id)

                    if not biz:
                        await websocket.send_json({"type": "error", "text": "Business not found"})
                        continue
                    if not svc:
                        await websocket.send_json({"type": "error", "text": "Service not found"})
                        continue

                    # Create call session
                    call_service = CallSessionService(db)
                    call_result = await call_service.start_call(
                        business_id=business_id,
                        channel="VOICE_WS_TEST"
                    )

                    state = VoiceCallState(business_id, service_id, call_result["call_session_id"])

                    greeting = await voice_flow.get_greeting(business_id, service_id)

                    await websocket.send_json({
                        "type": "speak",
                        "text": greeting,
                        "step": "greeting",
                        "call_session_id": call_result["call_session_id"],
                        "public_call_id": call_result["public_call_id"],
                        "options": [
                            {"digit": "1", "label": "Yes, hear details"},
                            {"digit": "2", "label": "No thanks"},
                        ],
                    })

                elif action == "press":
                    if not state:
                        await websocket.send_json({"type": "error", "text": "Call not started. Send 'start' first."})
                        continue

                    digit = str(msg.get("digit", ""))
                    voice_flow = VoiceFlowService(db)

                    # === GREETING STEP ===
                    if state.step == "greeting":
                        if digit == "1":
                            details = await voice_flow.get_service_details_text(state.service_id)
                            after_prompt = await voice_flow.get_after_details_prompt()
                            state.step = "after_details"

                            await websocket.send_json({
                                "type": "speak",
                                "text": f"Here are the details. {details}. {after_prompt}",
                                "step": "after_details",
                                "options": [
                                    {"digit": "1", "label": "Hear details again"},
                                    {"digit": "0", "label": "Book via chat"},
                                    {"digit": "9", "label": "Speak to a person"},
                                    {"digit": "8", "label": "End call"},
                                ],
                            })

                        elif digit == "2":
                            prompt = await voice_flow.get_how_can_help_prompt()
                            state.step = "how_can_help"

                            await websocket.send_json({
                                "type": "speak",
                                "text": prompt,
                                "step": "how_can_help",
                                "options": [
                                    {"digit": "1", "label": "Hear service details"},
                                    {"digit": "0", "label": "Book via chat"},
                                    {"digit": "9", "label": "Speak to a person"},
                                    {"digit": "8", "label": "End call"},
                                ],
                            })

                        else:
                            greeting = await voice_flow.get_greeting(state.business_id, state.service_id)
                            await websocket.send_json({
                                "type": "speak",
                                "text": f"Sorry, that wasn't a valid option. {greeting}",
                                "step": "greeting",
                                "options": [
                                    {"digit": "1", "label": "Yes, hear details"},
                                    {"digit": "2", "label": "No thanks"},
                                ],
                            })

                    # === AFTER DETAILS STEP ===
                    elif state.step == "after_details":
                        if digit == "1":
                            details = await voice_flow.get_service_details_text(state.service_id)
                            after_prompt = await voice_flow.get_after_details_prompt()

                            await websocket.send_json({
                                "type": "speak",
                                "text": f"Here are the details. {details}. {after_prompt}",
                                "step": "after_details",
                                "options": [
                                    {"digit": "1", "label": "Hear details again"},
                                    {"digit": "0", "label": "Book via chat"},
                                    {"digit": "9", "label": "Speak to a person"},
                                    {"digit": "8", "label": "End call"},
                                ],
                            })

                        elif digit == "0":
                            # Book via chat
                            redirect_msg = await voice_flow.get_booking_redirect_message()
                            state.step = "ended"

                            # Create chat handoff
                            handoff_data = await _do_chat_handoff(db, state)

                            await websocket.send_json({
                                "type": "handoff_to_chat",
                                "text": redirect_msg,
                                "step": "ended",
                                "conversation_id": handoff_data.get("conversation_id"),
                                "business_slug": handoff_data.get("business_slug"),
                                "service_id": state.service_id,
                            })

                        elif digit == "9":
                            escalation_msg = await voice_flow.get_escalation_message()
                            state.step = "ended"

                            # Create handoff
                            await _do_escalation(db, state)

                            await websocket.send_json({
                                "type": "ended",
                                "text": escalation_msg,
                                "step": "ended",
                                "reason": "escalated",
                            })

                        elif digit == "8":
                            goodbye = await voice_flow.get_goodbye_message()
                            state.step = "ended"

                            await websocket.send_json({
                                "type": "ended",
                                "text": goodbye,
                                "step": "ended",
                                "reason": "goodbye",
                            })

                        else:
                            not_understood = await voice_flow.get_not_understood_message()
                            await websocket.send_json({
                                "type": "speak",
                                "text": not_understood,
                                "step": "after_details",
                                "options": [
                                    {"digit": "1", "label": "Hear details again"},
                                    {"digit": "0", "label": "Book via chat"},
                                    {"digit": "9", "label": "Speak to a person"},
                                    {"digit": "8", "label": "End call"},
                                ],
                            })

                    # === HOW CAN HELP STEP ===
                    elif state.step == "how_can_help":
                        if digit == "1":
                            details = await voice_flow.get_service_details_text(state.service_id)
                            after_prompt = await voice_flow.get_after_details_prompt()
                            state.step = "after_details"

                            await websocket.send_json({
                                "type": "speak",
                                "text": f"Here are the details. {details}. {after_prompt}",
                                "step": "after_details",
                                "options": [
                                    {"digit": "1", "label": "Hear details again"},
                                    {"digit": "0", "label": "Book via chat"},
                                    {"digit": "9", "label": "Speak to a person"},
                                    {"digit": "8", "label": "End call"},
                                ],
                            })

                        elif digit == "0":
                            redirect_msg = await voice_flow.get_booking_redirect_message()
                            state.step = "ended"
                            handoff_data = await _do_chat_handoff(db, state)

                            await websocket.send_json({
                                "type": "handoff_to_chat",
                                "text": redirect_msg,
                                "step": "ended",
                                "conversation_id": handoff_data.get("conversation_id"),
                                "business_slug": handoff_data.get("business_slug"),
                                "service_id": state.service_id,
                            })

                        elif digit == "9":
                            escalation_msg = await voice_flow.get_escalation_message()
                            state.step = "ended"
                            await _do_escalation(db, state)

                            await websocket.send_json({
                                "type": "ended",
                                "text": escalation_msg,
                                "step": "ended",
                                "reason": "escalated",
                            })

                        elif digit == "8":
                            goodbye = await voice_flow.get_goodbye_message()
                            state.step = "ended"

                            await websocket.send_json({
                                "type": "ended",
                                "text": goodbye,
                                "step": "ended",
                                "reason": "goodbye",
                            })

                        else:
                            not_understood = await voice_flow.get_not_understood_message()
                            await websocket.send_json({
                                "type": "speak",
                                "text": not_understood,
                                "step": "how_can_help",
                                "options": [
                                    {"digit": "1", "label": "Hear service details"},
                                    {"digit": "0", "label": "Book via chat"},
                                    {"digit": "9", "label": "Speak to a person"},
                                    {"digit": "8", "label": "End call"},
                                ],
                            })

                    # === ENDED ===
                    elif state.step == "ended":
                        await websocket.send_json({
                            "type": "ended",
                            "text": "The call has ended.",
                            "step": "ended",
                            "reason": "already_ended",
                        })

        except WebSocketDisconnect:
            pass
        except Exception as e:
            try:
                await websocket.send_json({"type": "error", "text": str(e)})
            except:
                pass


async def _do_chat_handoff(db: AsyncSession, state: VoiceCallState) -> dict:
    """Create chat conversation for booking handoff."""
    try:
        from app.services.chat_service import ChatService
        from app.models import Business

        result = await db.execute(
            select(Business).where(Business.id == uuid_lib.UUID(state.business_id))
        )
        business = result.scalar_one_or_none()

        if not business:
            return {}

        chat_service = ChatService(db)
        chat_result = await chat_service.start_conversation(
            business_slug=business.slug,
            service_id=state.service_id,
            user_session_id=f"voice-ws-{state.call_session_id}",
            channel="CHAT",
        )

        return {
            "conversation_id": chat_result.get("conversation_id"),
            "business_slug": business.slug,
        }
    except Exception:
        return {}


async def _do_escalation(db: AsyncSession, state: VoiceCallState) -> None:
    """Create handoff request for human escalation."""
    try:
        result = await db.execute(
            select(CallSession).where(CallSession.id == uuid_lib.UUID(state.call_session_id))
        )
        call_session = result.scalar_one_or_none()

        if call_session and call_session.conversation_id:
            handoff_service = HandoffService(db)
            await handoff_service.create_handoff(
                business_id=state.business_id,
                conversation_id=str(call_session.conversation_id),
                reason="Customer requested human assistance via voice call",
            )
    except Exception:
        pass