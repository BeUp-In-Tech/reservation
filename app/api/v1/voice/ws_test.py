"""
WebSocket-based voice endpoint.
Accepts business_slug + service_name (from frontend)
OR business_id + service_id (from voice_test.html).
"""

import json
import uuid as uuid_lib
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.services.voice_flow_service import VoiceFlowService
from app.services.call_session_service import CallSessionService
from app.services.handoff_service import HandoffService
from app.models import CallSession, Business, Service

ws_router = APIRouter()


class VoiceCallState:
    def __init__(self, business_id: str, service_id: str, business_slug: str = None, call_session_id: str = None):
        self.business_id = business_id
        self.service_id = service_id
        self.business_slug = business_slug
        self.call_session_id = call_session_id
        self.step = "greeting"


async def _resolve_ids(db: AsyncSession, msg: dict) -> tuple[str, str, str]:
    """
    Resolve business_id and service_id from either:
      - business_id + service_id (UUIDs)
      - business_slug + service_name (strings from frontend)
    Returns (business_id, service_id, business_slug) or raises ValueError.
    """
    business_id = msg.get("business_id")
    service_id = msg.get("service_id")
    business_slug = msg.get("business_slug")
    service_name = msg.get("service_name")

    # If we already have UUIDs, just resolve slug
    if business_id and service_id:
        if not business_slug:
            result = await db.execute(
                select(Business).where(Business.id == uuid_lib.UUID(business_id))
            )
            biz = result.scalar_one_or_none()
            business_slug = biz.slug if biz else None
        return business_id, service_id, business_slug

    # Resolve from slug + name
    if not business_slug:
        raise ValueError("business_slug or business_id is required")

    result = await db.execute(
        select(Business).where(Business.slug == business_slug)
    )
    business = result.scalar_one_or_none()
    if not business:
        raise ValueError(f"Business not found: {business_slug}")

    business_id = str(business.id)

    # Resolve service
    if service_id:
        return business_id, service_id, business_slug

    if not service_name:
        raise ValueError("service_name or service_id is required")

    result = await db.execute(
        select(Service).where(
            Service.business_id == business.id,
            Service.service_name == service_name,
            Service.is_active == True
        )
    )
    service = result.scalar_one_or_none()
    if not service:
        raise ValueError(f"Service not found: {service_name}")

    return business_id, str(service.id), business_slug


@ws_router.websocket("/ws/voice-test")
async def voice_test_ws(websocket: WebSocket):
    """
    WebSocket voice flow.

    Client sends:
        {"action": "start", "business_slug": "sunset-spa", "service_name": "Spa Massage"}
        OR
        {"action": "start", "business_id": "uuid", "service_id": "uuid"}

        {"action": "press", "digit": "1"}

    Server sends:
        {"type": "speak", "text": "...", "step": "greeting", "options": [...]}
        {"type": "ended", "text": "...", "reason": "goodbye"}
        {"type": "handoff_to_chat", "conversation_id": "...", "business_slug": "..."}
    """
    await websocket.accept()
    state = None

    async with AsyncSessionLocal() as db:
        try:
            while True:
                data = await websocket.receive_text()
                msg = json.loads(data)
                action = msg.get("action")

                if action == "start":
                    try:
                        business_id, service_id, business_slug = await _resolve_ids(db, msg)
                    except ValueError as e:
                        await websocket.send_json({"type": "error", "text": str(e)})
                        continue

                    voice_flow = VoiceFlowService(db)

                    biz = await voice_flow.get_business(business_id)
                    svc = await voice_flow.get_service(service_id)

                    if not biz:
                        await websocket.send_json({"type": "error", "text": "Business not found"})
                        continue
                    if not svc:
                        await websocket.send_json({"type": "error", "text": "Service not found"})
                        continue

                    call_service = CallSessionService(db)
                    call_result = await call_service.start_call(
                        business_id=business_id,
                        channel="VOICE_WS"
                    )

                    state = VoiceCallState(
                        business_id=business_id,
                        service_id=service_id,
                        business_slug=business_slug,
                        call_session_id=call_result["call_session_id"],
                    )

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
                        await websocket.send_json({"type": "error", "text": "Call not started"})
                        continue

                    digit = str(msg.get("digit", ""))
                    voice_flow = VoiceFlowService(db)

                    # === GREETING ===
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

                    # === AFTER DETAILS ===
                    elif state.step == "after_details":
                        await _handle_menu(websocket, db, state, digit, voice_flow)

                    # === HOW CAN HELP ===
                    elif state.step == "how_can_help":
                        await _handle_menu(websocket, db, state, digit, voice_flow)

                    # === ENDED ===
                    elif state.step == "ended":
                        await websocket.send_json({
                            "type": "ended", "text": "The call has ended.",
                            "step": "ended", "reason": "already_ended",
                        })

        except WebSocketDisconnect:
            pass
        except Exception as e:
            try:
                await websocket.send_json({"type": "error", "text": str(e)})
            except:
                pass


async def _handle_menu(websocket, db, state, digit, voice_flow):
    """Shared handler for after_details and how_can_help steps."""
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
            "business_slug": handoff_data.get("business_slug", state.business_slug),
            "service_id": state.service_id,
        })
    elif digit == "9":
        escalation_msg = await voice_flow.get_escalation_message()
        state.step = "ended"
        await _do_escalation(db, state)
        await websocket.send_json({
            "type": "ended", "text": escalation_msg,
            "step": "ended", "reason": "escalated",
        })
    elif digit == "8":
        goodbye = await voice_flow.get_goodbye_message()
        state.step = "ended"
        await websocket.send_json({
            "type": "ended", "text": goodbye,
            "step": "ended", "reason": "goodbye",
        })
    else:
        not_understood = await voice_flow.get_not_understood_message()
        await websocket.send_json({
            "type": "speak",
            "text": not_understood,
            "step": state.step,
            "options": [
                {"digit": "1", "label": "Hear details again" if state.step == "after_details" else "Hear service details"},
                {"digit": "0", "label": "Book via chat"},
                {"digit": "9", "label": "Speak to a person"},
                {"digit": "8", "label": "End call"},
            ],
        })


async def _do_chat_handoff(db: AsyncSession, state: VoiceCallState) -> dict:
    try:
        from app.services.chat_service import ChatService

        if not state.business_slug:
            result = await db.execute(
                select(Business).where(Business.id == uuid_lib.UUID(state.business_id))
            )
            biz = result.scalar_one_or_none()
            state.business_slug = biz.slug if biz else None

        if not state.business_slug:
            return {}

        chat_service = ChatService(db)
        chat_result = await chat_service.start_conversation(
            business_slug=state.business_slug,
            service_id=state.service_id,
            user_session_id=f"voice-ws-{state.call_session_id}",
            channel="CHAT",
        )
        return {
            "conversation_id": chat_result.get("conversation_id"),
            "business_slug": state.business_slug,
        }
    except Exception:
        return {}


async def _do_escalation(db: AsyncSession, state: VoiceCallState) -> None:
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