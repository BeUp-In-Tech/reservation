"""
Rule-based chat service for the booking system.
No AI/LLM calls - uses regex parsing and database lookups.
"""

import uuid
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import (
    Business,
    Service,
    Conversation,
    ConversationMessage,
    BusinessAISettings,
    Booking,
)
from app.services.chat_parser import parse_message
from app.services.booking_service import BookingService
from app.services.slot_service import SlotService
from app.services.handoff_service import HandoffService


class ChatService:
    """
    Rule-based chat service. No AI/LLM.
    Uses regex to parse user messages and database to drive all responses.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.booking_service = BookingService(db)
        self.slot_service = SlotService(db)
        self.handoff_service = HandoffService(db)

    # ==================== START CONVERSATION ====================

    async def start_conversation(
        self,
        business_slug: str,
        service_id: str | None = None,
        service_name: str | None = None,
        user_session_id: str | None = None,
        channel: str = "CHAT"
    ) -> dict:
        """Start a new conversation for a business with a pre-selected service."""

        if not business_slug:
            raise ValueError("Business slug is required")

        result = await self.db.execute(
            select(Business).where(Business.slug == business_slug)
        )
        business = result.scalar_one_or_none()
        if not business:
            raise ValueError(f"Business not found: {business_slug}")

        # If service_name provided but not service_id, look up by name
        if not service_id and service_name:
            svc_result = await self.db.execute(
                select(Service).where(
                    Service.business_id == business.id,
                    Service.service_name == service_name,
                    Service.is_active == True
                )
            )
            found_svc = svc_result.scalar_one_or_none()
            if found_svc:
                service_id = str(found_svc.id)

        # Validate service belongs to this business
        selected_service = None
        if service_id:
            try:
                svc_uuid = uuid.UUID(service_id)
            except ValueError:
                raise ValueError(f"Invalid service ID format: {service_id}")

            svc_result = await self.db.execute(
                select(Service).where(
                    Service.id == svc_uuid,
                    Service.business_id == business.id,
                    Service.is_active == True
                )
            )
            selected_service = svc_result.scalar_one_or_none()
            if not selected_service:
                raise ValueError(f"Service not found in business {business_slug}")

        # Create conversation
        conversation = Conversation(
            business_id=business.id,
            channel=channel,
            status="STARTED",
            user_session_id=user_session_id,
            started_at=datetime.utcnow(),
        )
        self.db.add(conversation)
        await self.db.flush()

        # Load business info
        business_info = await self._load_business_info(business.id)

        # Build first message
        if selected_service:
            first_message = (
                f"Welcome! You've selected **{selected_service.service_name}**.\n\n"
                f"When would you like to book? Please provide your preferred date and time.\n"
                f"(e.g., \"tomorrow 3pm\", \"next Monday 10am\", \"March 15 2pm\")"
            )

            # Create booking immediately since service is selected
            booking = await self.booking_service.create_booking(
                business_id=str(business.id),
                service_id=str(selected_service.id),
                conversation_id=str(conversation.id)
            )

            # Save first AI message
            ai_msg = ConversationMessage(
                business_id=business.id,
                conversation_id=conversation.id,
                role="assistant",
                content=first_message,
                created_at=datetime.utcnow(),
            )
            self.db.add(ai_msg)
            await self.db.commit()

            return {
                "conversation_id": str(conversation.id),
                "business_id": str(business.id),
                "business_name": business.business_name,
                "selected_service": {
                    "service_id": str(selected_service.id),
                    "service_name": selected_service.service_name,
                },
                "booking_id": booking["booking_id"],
                "public_tracking_id": booking["public_tracking_id"],
                "first_message": first_message,
                "current_step": "awaiting_slot",
                **business_info,
            }
        else:
            # No service selected - show available services
            services = business_info.get("available_services", [])
            if services:
                svc_lines = "\n".join(
                    [f"- **{s['service_name']}**" + (f" ({s['base_price']} {s['currency']})" if s.get('base_price') else "")
                     for s in services]
                )
                first_message = (
                    f"Welcome to **{business.business_name}**!\n\n"
                    f"Here are our available services:\n{svc_lines}\n\n"
                    f"Which service would you like to book?"
                )
            else:
                first_message = f"Welcome to **{business.business_name}**! Unfortunately, no services are currently available."

            ai_msg = ConversationMessage(
                business_id=business.id,
                conversation_id=conversation.id,
                role="assistant",
                content=first_message,
                created_at=datetime.utcnow(),
            )
            self.db.add(ai_msg)
            await self.db.commit()

            return {
                "conversation_id": str(conversation.id),
                "business_id": str(business.id),
                "business_name": business.business_name,
                "first_message": first_message,
                "current_step": "awaiting_service",
                **business_info,
            }

    # ==================== SEND MESSAGE ====================

    async def send_message(
        self,
        conversation_id: str,
        user_message: str
    ) -> dict:
        """Process a user message using regex parsing and database operations."""

        conv_uuid = uuid.UUID(conversation_id)

        # Load conversation
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conv_uuid)
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise ValueError(f"Conversation not found: {conversation_id}")

        # Load business
        result = await self.db.execute(
            select(Business).where(Business.id == conversation.business_id)
        )
        business = result.scalar_one()

        # Load business info (services, AI settings)
        business_info = await self._load_business_info(conversation.business_id)

        # Load existing booking
        existing_booking = await self.booking_service.get_booking_by_conversation(conversation_id)
        # Also check latest (includes PENDING_PAYMENT)
        latest_booking = await self.booking_service.get_latest_booking_by_conversation(conversation_id)

        # Load existing handoff
        existing_handoff = await self.handoff_service.get_handoff_by_conversation(conversation_id)

        # Determine current step from conversation state
        current_step = self._determine_current_step(existing_booking, latest_booking, existing_handoff)

        # Save user message
        user_msg_record = ConversationMessage(
            business_id=conversation.business_id,
            conversation_id=conv_uuid,
            role="user",
            content=user_message,
            created_at=datetime.utcnow(),
        )
        self.db.add(user_msg_record)

        # Parse the message
        parse_context = {
            "current_step": current_step,
            "available_services": business_info.get("available_services", []),
        }
        parsed = parse_message(user_message, parse_context)

        # Route to handler based on intent
        intent = parsed["intent"]
        handler_map = {
            "greet": self._handle_greet,
            "list_services": self._handle_list_services,
            "select_service": self._handle_select_service,
            "select_slot": self._handle_select_slot,
            "provide_contact": self._handle_provide_contact,
            "confirm_booking": self._handle_confirm_booking,
            "check_status": self._handle_check_status,
            "cancel_booking": self._handle_cancel_booking,
            "confirm_cancel": self._handle_confirm_cancel,
            "reschedule": self._handle_reschedule,
            "escalate": self._handle_escalate,
            "decline": self._handle_decline,
            "other": self._handle_other,
        }

        handler = handler_map.get(intent, self._handle_other)
        response_data = await handler(
            parsed=parsed,
            conversation=conversation,
            business=business,
            business_info=business_info,
            existing_booking=existing_booking,
            latest_booking=latest_booking,
            existing_handoff=existing_handoff,
            current_step=current_step,
        )

        ai_response = response_data.get("response", "I didn't understand that. Could you rephrase?")

        # Save AI response
        ai_msg_record = ConversationMessage(
            business_id=conversation.business_id,
            conversation_id=conv_uuid,
            role="assistant",
            content=ai_response,
            created_at=datetime.utcnow(),
        )
        self.db.add(ai_msg_record)

        conversation.last_message_at = datetime.utcnow()
        conversation.status = "IN_PROGRESS"

        await self.db.commit()

        # Fetch updated booking after commit
        updated_booking = await self.booking_service.get_latest_booking_by_conversation(conversation_id)
        updated_handoff = await self.handoff_service.get_handoff_by_conversation(conversation_id)

        return {
            "conversation_id": conversation_id,
            "response": ai_response,
            "intent": intent,
            "needs_escalation": parsed.get("wants_human", False),
            "selected_service": response_data.get("selected_service"),
            "selected_slot": response_data.get("selected_slot"),
            "booking_id": updated_booking["booking_id"] if updated_booking else None,
            "public_tracking_id": updated_booking["public_tracking_id"] if updated_booking else None,
            "booking_status": updated_booking["status"] if updated_booking else None,
            "slot_unavailable": response_data.get("slot_unavailable", False),
            "slot_alternatives": response_data.get("slot_alternatives", []),
            "handoff_ticket_id": updated_handoff["public_ticket_id"] if updated_handoff else None,
            "payment_url": response_data.get("payment_url"),
        }

    # ==================== INTENT HANDLERS ====================

    async def _handle_greet(self, parsed, conversation, business, business_info, existing_booking, latest_booking, existing_handoff, current_step, **kw):
        services = business_info.get("available_services", [])

        if existing_booking:
            svc_name = existing_booking.get("service_name", "your service")
            if current_step == "awaiting_slot":
                return {"response": f"Hello! You're currently booking **{svc_name}**. When would you like to book? (e.g., \"tomorrow 3pm\")"}
            elif current_step == "awaiting_contact":
                return {"response": f"Hello! You're booking **{svc_name}**. I still need your contact info. Please provide your name, phone number, and email."}
            elif current_step == "awaiting_confirm":
                return {"response": f"Hello! Your booking for **{svc_name}** is ready to confirm. Type \"confirm\" to proceed."}
            else:
                return {"response": f"Hello! How can I help you with your booking?"}

        if services:
            svc_lines = "\n".join(
                [f"- **{s['service_name']}**" + (f" ({s['base_price']} {s['currency']})" if s.get('base_price') else "")
                 for s in services]
            )
            return {"response": f"Hello! Welcome to **{business.business_name}**.\n\nHere are our services:\n{svc_lines}\n\nWhich service would you like to book?"}
        else:
            return {"response": f"Hello! Welcome to **{business.business_name}**. How can I help you?"}

    async def _handle_list_services(self, parsed, conversation, business, business_info, **kw):
        services = business_info.get("available_services", [])
        if services:
            svc_lines = "\n".join([
                f"- **{s['service_name']}**"
                + (f" - {s['description']}" if s.get('description') else "")
                + (f" | {s['base_price']} {s['currency']}" if s.get('base_price') else "")
                + (f" | {s['duration_minutes']} min" if s.get('duration_minutes') else "")
                for s in services
            ])
            return {"response": f"Here are our available services:\n\n{svc_lines}\n\nWhich one would you like to book?"}
        else:
            return {"response": "Sorry, there are no services available at the moment."}

    async def _handle_select_service(self, parsed, conversation, business, business_info, existing_booking, **kw):
        service_name = parsed.get("service_mentioned")
        services = business_info.get("available_services", [])

        # Find the service
        matched_service = None
        for svc in services:
            if svc["service_name"].lower() == service_name.lower():
                matched_service = svc
                break

        if not matched_service:
            available_names = [s["service_name"] for s in services]
            return {"response": f"Sorry, \"{service_name}\" is not available. Our services are: {', '.join(available_names)}. Which one would you like?"}

        # Create booking if none exists
        if not existing_booking:
            booking = await self.booking_service.create_booking(
                business_id=str(conversation.business_id),
                service_id=matched_service["id"],
                conversation_id=str(conversation.id)
            )
            return {
                "response": (
                    f"You've selected **{matched_service['service_name']}**.\n\n"
                    f"When would you like to book?\n"
                    f"(e.g., \"tomorrow 3pm\", \"next Monday 10am\", \"March 15 2pm\")"
                ),
                "selected_service": matched_service["service_name"],
            }
        else:
            return {"response": f"You already have an active booking for **{existing_booking.get('service_name')}**. Would you like to continue with it or cancel it first?"}

    async def _handle_select_slot(self, parsed, conversation, business, business_info, existing_booking, latest_booking, **kw):
        date_str = parsed.get("date")
        time_str = parsed.get("time")
        slot_start_str = parsed.get("slot_start")

        # Need a booking first
        booking = existing_booking or latest_booking
        if not booking:
            services = business_info.get("available_services", [])
            if services:
                svc_names = ", ".join([s["service_name"] for s in services])
                return {"response": f"Please select a service first. Available: {svc_names}"}
            return {"response": "Please select a service first."}

        # Need both date and time
        if date_str and not time_str:
            return {
                "response": f"Got it, **{date_str}**. What time would you prefer?\n(e.g., \"10am\", \"2:30pm\", \"15:00\")",
                "selected_slot": date_str,
            }

        if time_str and not date_str:
            return {
                "response": f"Got it, **{time_str}**. What date would you prefer?\n(e.g., \"tomorrow\", \"next Monday\", \"March 15\")",
            }

        if not slot_start_str:
            return {"response": "Please provide both a date and time. (e.g., \"tomorrow 3pm\")"}

        # Parse the slot
        try:
            if "T" in slot_start_str:
                slot_start = datetime.fromisoformat(slot_start_str.replace("Z", "+00:00"))
            else:
                slot_start = datetime.fromisoformat(slot_start_str)
        except ValueError:
            return {"response": "I couldn't understand that date/time. Please try again. (e.g., \"tomorrow 3pm\")"}

        # Check if slot is in the past
        if slot_start < datetime.now():
            return {"response": "That time has already passed. Please choose a future date and time."}

        slot_end = slot_start + timedelta(hours=1)
        service_id = booking.get("service_id")

        # Check availability
        slot_check = await self.slot_service.validate_and_reserve_slot(
            service_id=service_id,
            slot_start=slot_start,
            slot_end=slot_end
        )

        if slot_check["available"]:
            await self.booking_service.update_slot(
                booking_id=booking["booking_id"],
                slot_start=slot_start,
                slot_end=slot_end
            )

            slot_display = slot_start.strftime("%B %d, %Y at %I:%M %p")
            return {
                "response": (
                    f"Slot confirmed: **{slot_display}** for **{booking.get('service_name')}**.\n\n"
                    f"Now I need your contact information:\n"
                    f"- Full name\n"
                    f"- Phone number\n"
                    f"- Email address\n\n"
                    f"You can provide all at once, e.g.:\n"
                    f"\"John Doe, +8801712345678, john@email.com\""
                ),
                "selected_slot": slot_start.isoformat(),
            }
        else:
            alternatives = slot_check.get("alternatives", [])
            if alternatives:
                alt_lines = "\n".join([f"- {alt['start']}" for alt in alternatives[:5]])
                return {
                    "response": f"Sorry, that slot is not available.\n\nHere are some alternatives:\n{alt_lines}\n\nWhich one would you prefer?",
                    "slot_unavailable": True,
                    "slot_alternatives": alternatives,
                }
            else:
                return {
                    "response": "Sorry, that slot is not available. Please try another date or time.",
                    "slot_unavailable": True,
                }

    async def _handle_provide_contact(self, parsed, conversation, business, business_info, existing_booking, latest_booking, **kw):
        booking = existing_booking or latest_booking
        if not booking:
            return {"response": "Please select a service and time slot first before providing contact info."}

        contact = parsed.get("contact", {})
        new_name = contact.get("name") or booking.get("customer_name")
        new_phone = contact.get("phone") or booking.get("customer_phone")
        new_email = contact.get("email") or booking.get("customer_email")

        missing = []
        if not new_name:
            missing.append("full name")
        if not new_phone:
            missing.append("phone number")
        if not new_email:
            missing.append("email address")

        if missing:
            provided = []
            if new_name:
                provided.append(f"Name: {new_name}")
            if new_phone:
                provided.append(f"Phone: {new_phone}")
            if new_email:
                provided.append(f"Email: {new_email}")

            provided_text = "\n".join([f"- {p}" for p in provided]) if provided else ""
            missing_text = ", ".join(missing)

            response = ""
            if provided_text:
                response += f"Got it!\n{provided_text}\n\n"
            response += f"I still need your **{missing_text}**. Please provide it."

            # Partial update - save what we have
            if any([contact.get("name"), contact.get("phone"), contact.get("email")]):
                await self._partial_contact_update(booking["booking_id"], new_name, new_phone, new_email)

            return {"response": response}

        # All contact info present - update and show summary
        await self.booking_service.update_contact(
            booking_id=booking["booking_id"],
            customer_name=new_name,
            customer_phone=new_phone,
            customer_email=new_email
        )

        slot_display = "Not selected"
        if booking.get("slot_start"):
            try:
                dt = datetime.fromisoformat(booking["slot_start"].replace("Z", "+00:00"))
                slot_display = dt.strftime("%B %d, %Y at %I:%M %p")
            except (ValueError, TypeError):
                slot_display = str(booking["slot_start"])

        return {
            "response": (
                f"Here's your booking summary:\n\n"
                f"- **Service:** {booking.get('service_name')}\n"
                f"- **Date/Time:** {slot_display}\n"
                f"- **Name:** {new_name}\n"
                f"- **Phone:** {new_phone}\n"
                f"- **Email:** {new_email}\n\n"
                f"Type **\"confirm\"** to finalize your booking."
            ),
        }

    async def _handle_confirm_booking(self, parsed, conversation, business, business_info, existing_booking, latest_booking, **kw):
        booking = existing_booking or latest_booking
        if not booking:
            return {"response": "No active booking found to confirm."}

        # Check all required data is present
        missing = []
        if not booking.get("slot_start"):
            missing.append("date/time")
        if not booking.get("customer_name"):
            missing.append("name")
        if not booking.get("customer_phone"):
            missing.append("phone")
        if not booking.get("customer_email"):
            missing.append("email")

        if missing:
            return {"response": f"Cannot confirm yet. Missing: {', '.join(missing)}. Please provide this information first."}

        # Mark as pending payment
        pending = await self.booking_service.mark_pending_payment(
            booking_id=booking["booking_id"],
            mode="PAY_LATER"
        )

        return {
            "response": (
                f"Your booking is confirmed! Here are the details:\n\n"
                f"- **Booking ID:** {pending['public_tracking_id']}\n"
                f"- **Service:** {booking.get('service_name')}\n"
                f"- **Status:** Pending Payment\n\n"
                f"Your booking will be fully confirmed once payment is completed.\n"
                f"Save your booking ID: **{pending['public_tracking_id']}**"
            ),
            "payment_url": pending.get("payment_url"),
        }

    async def _handle_check_status(self, parsed, conversation, business, business_info, existing_booking, latest_booking, **kw):
        tracking_id = parsed.get("booking_id")

        if not tracking_id:
            if latest_booking:
                tracking_id = latest_booking.get("public_tracking_id")
            else:
                return {"response": "Please provide your booking ID to check status. (e.g., \"check status BK-ABC123\")"}

        booking_info = await self.booking_service.get_booking_by_tracking_id(tracking_id)
        if not booking_info:
            return {"response": f"No booking found with ID **{tracking_id}**. Please check the ID and try again."}

        slot_display = "Not scheduled"
        if booking_info.get("slot_start"):
            try:
                dt = datetime.fromisoformat(booking_info["slot_start"].replace("Z", "+00:00"))
                slot_display = dt.strftime("%B %d, %Y at %I:%M %p")
            except (ValueError, TypeError):
                slot_display = str(booking_info["slot_start"])

        return {
            "response": (
                f"Booking **{tracking_id}** details:\n\n"
                f"- **Service:** {booking_info.get('service_name', 'N/A')}\n"
                f"- **Status:** {booking_info['status']}\n"
                f"- **Date/Time:** {slot_display}\n"
                f"- **Customer:** {booking_info.get('customer_name', 'N/A')}\n"
                f"- **Payment:** {booking_info.get('payment_status', 'N/A')}\n\n"
                f"Is there anything else I can help you with?"
            ),
        }

    async def _handle_cancel_booking(self, parsed, conversation, business, business_info, existing_booking, latest_booking, **kw):
        tracking_id = parsed.get("booking_id")

        if not tracking_id:
            if latest_booking:
                tracking_id = latest_booking.get("public_tracking_id")
            else:
                return {"response": "Please provide the booking ID you want to cancel. (e.g., \"cancel BK-ABC123\")"}

        booking_info = await self.booking_service.get_booking_by_tracking_id(tracking_id)
        if not booking_info:
            return {"response": f"No booking found with ID **{tracking_id}**. Please check and try again."}

        if booking_info["status"] in ["CANCELLED", "CANCELED"]:
            return {"response": f"Booking **{tracking_id}** is already cancelled."}

        return {
            "response": (
                f"Are you sure you want to cancel booking **{tracking_id}** "
                f"for **{booking_info.get('service_name', 'your service')}**?\n\n"
                f"This action cannot be undone. Type **\"yes\"** to confirm cancellation."
            ),
        }

    async def _handle_confirm_cancel(self, parsed, conversation, business, business_info, existing_booking, latest_booking, **kw):
        # Find the booking to cancel - check latest conversation messages for tracking ID
        tracking_id = parsed.get("booking_id")
        if not tracking_id and latest_booking:
            tracking_id = latest_booking.get("public_tracking_id")

        if not tracking_id:
            return {"response": "No booking found to cancel. Please provide the booking ID."}

        try:
            result = await self.booking_service.cancel_booking_by_tracking_id(tracking_id)
            return {
                "response": (
                    f"Booking **{tracking_id}** has been successfully cancelled.\n\n"
                    f"Would you like to make a new booking?"
                ),
            }
        except ValueError as e:
            return {"response": f"Could not cancel: {str(e)}"}

    async def _handle_reschedule(self, parsed, conversation, business, business_info, existing_booking, latest_booking, **kw):
        tracking_id = parsed.get("booking_id")
        if not tracking_id and latest_booking:
            tracking_id = latest_booking.get("public_tracking_id")

        if not tracking_id:
            return {"response": "Please provide the booking ID to reschedule. (e.g., \"reschedule BK-ABC123\")"}

        booking_info = await self.booking_service.get_booking_by_tracking_id(tracking_id)
        if not booking_info:
            return {"response": f"No booking found with ID **{tracking_id}**."}

        slot_start_str = parsed.get("slot_start")

        if not slot_start_str:
            return {"response": f"When would you like to reschedule booking **{tracking_id}** to?\n(e.g., \"tomorrow 3pm\", \"next Monday 10am\")"}

        try:
            slot_start = datetime.fromisoformat(slot_start_str.replace("Z", "+00:00"))
            slot_end = slot_start + timedelta(hours=1)

            result = await self.booking_service.reschedule_booking_by_tracking_id(
                tracking_id=tracking_id,
                new_slot_start=slot_start,
                new_slot_end=slot_end
            )

            slot_display = slot_start.strftime("%B %d, %Y at %I:%M %p")
            return {
                "response": (
                    f"Booking **{tracking_id}** has been rescheduled to **{slot_display}**.\n\n"
                    f"Is there anything else I can help you with?"
                ),
            }
        except ValueError as e:
            return {"response": f"Could not reschedule: {str(e)}"}

    async def _handle_escalate(self, parsed, conversation, business, business_info, existing_booking, latest_booking, existing_handoff, **kw):
        if existing_handoff:
            return {"response": f"You already have an open support ticket: **{existing_handoff['public_ticket_id']}**. A team member will contact you shortly."}

        booking_id = None
        if latest_booking:
            booking_id = latest_booking.get("booking_id")

        handoff = await self.handoff_service.create_handoff(
            business_id=str(conversation.business_id),
            conversation_id=str(conversation.id),
            reason="User requested human assistance",
            contact_name=latest_booking.get("customer_name") if latest_booking else None,
            contact_phone=latest_booking.get("customer_phone") if latest_booking else None,
            contact_email=latest_booking.get("customer_email") if latest_booking else None,
            booking_id=booking_id,
        )

        return {
            "response": (
                f"I've created a support ticket for you.\n\n"
                f"- **Ticket ID:** {handoff['public_ticket_id']}\n\n"
                f"A team member will contact you shortly. Please save your ticket ID for reference."
            ),
        }

    async def _handle_decline(self, parsed, conversation, business, business_info, existing_booking, current_step, **kw):
        if current_step == "awaiting_cancel_confirm":
            return {"response": "Okay, the cancellation has been cancelled. Your booking is still active. Is there anything else I can help you with?"}
        elif current_step == "awaiting_confirm":
            return {"response": "No problem. What would you like to change? You can update the date/time or your contact information."}
        else:
            return {"response": "Okay. How can I help you?"}

    async def _handle_other(self, parsed, conversation, business, business_info, existing_booking, latest_booking, current_step, **kw):
        # Give helpful guidance based on current step
        if current_step == "awaiting_service":
            services = business_info.get("available_services", [])
            svc_names = ", ".join([s["service_name"] for s in services])
            return {"response": f"I didn't quite understand. Please select a service: {svc_names}"}

        elif current_step == "awaiting_slot":
            return {"response": "I didn't understand that. Please provide a date and time for your booking.\n(e.g., \"tomorrow 3pm\", \"next Monday 10am\")"}

        elif current_step == "awaiting_contact":
            return {"response": "I need your contact information to proceed. Please provide your name, phone number, and email address."}

        elif current_step == "awaiting_confirm":
            return {"response": "Your booking is ready. Type **\"confirm\"** to finalize, or let me know if you'd like to change anything."}

        else:
            return {
                "response": (
                    "I can help you with:\n"
                    "- **Book a service** - select a service and schedule a time\n"
                    "- **Check status** - \"status BK-XXXXXX\"\n"
                    "- **Cancel** - \"cancel BK-XXXXXX\"\n"
                    "- **Reschedule** - \"reschedule BK-XXXXXX to tomorrow 3pm\"\n"
                    "- **Talk to a person** - type \"human\"\n\n"
                    "How can I help?"
                ),
            }

    # ==================== HELPER METHODS ====================

    def _determine_current_step(self, existing_booking, latest_booking, existing_handoff) -> str:
        """Determine what step of the booking flow we're in."""
        if existing_handoff and existing_handoff.get("status") in ["OPEN", "ASSIGNED"]:
            return "escalated"

        booking = existing_booking or latest_booking

        if not booking:
            return "awaiting_service"

        status = booking.get("status", "")

        if status == "INITIATED":
            if booking.get("slot_start"):
                return "awaiting_contact"
            return "awaiting_slot"

        if status == "SLOT_SELECTED":
            if all([booking.get("customer_name"), booking.get("customer_phone"), booking.get("customer_email")]):
                return "awaiting_confirm"
            return "awaiting_contact"

        if status == "CONTACT_COLLECTED":
            return "awaiting_confirm"

        if status == "PENDING_PAYMENT":
            return "completed"

        if status == "CONFIRMED":
            return "completed"

        if status in ["CANCELLED", "CANCELED"]:
            return "awaiting_service"

        return "awaiting_service"

    async def _partial_contact_update(self, booking_id: str, name: str = None, phone: str = None, email: str = None):
        """Update individual contact fields without requiring all three."""
        result = await self.db.execute(
            select(Booking).where(Booking.id == uuid.UUID(booking_id))
        )
        booking = result.scalar_one_or_none()
        if booking:
            if name:
                booking.customer_name = name
            if phone:
                booking.customer_phone = phone
            if email:
                booking.customer_email = email
            booking.updated_at = datetime.utcnow()
            await self.db.flush()

    async def _load_business_info(self, business_id: uuid.UUID) -> dict:
        """Load business info for the chatbot."""
        if not business_id:
            raise ValueError("Business ID is required")

        result = await self.db.execute(
            select(BusinessAISettings).where(BusinessAISettings.business_id == business_id)
        )
        ai_settings = result.scalar_one_or_none()

        result = await self.db.execute(
            select(Service).where(
                Service.business_id == business_id,
                Service.is_active == True
            )
        )
        services = result.scalars().all()

        services_list = [
            {
                "id": str(s.id),
                "service_name": s.service_name,
                "description": s.description,
                "base_price": float(s.base_price) if s.base_price else None,
                "currency": s.currency,
                "duration_minutes": s.duration_minutes,
            }
            for s in services
        ]

        return {
            "ai_agent_name": ai_settings.agent_name if ai_settings else "Assistant",
            "ai_tone": ai_settings.tone_of_voice if ai_settings else "friendly and professional",
            "available_services": services_list,
        }

    # ==================== CONVERSATION QUERIES ====================

    async def get_conversation(self, conversation_id: str) -> dict | None:
        """Get conversation details."""
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == uuid.UUID(conversation_id))
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            return None

        return {
            "id": str(conversation.id),
            "business_id": str(conversation.business_id),
            "channel": conversation.channel,
            "status": conversation.status,
            "resolution_type": conversation.resolution_type,
            "outcome": conversation.outcome,
            "started_at": conversation.started_at.isoformat() if conversation.started_at else None,
            "last_message_at": conversation.last_message_at.isoformat() if conversation.last_message_at else None,
        }

    async def get_conversation_history(self, conversation_id: str) -> list[dict]:
        """Get all messages in a conversation."""
        result = await self.db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == uuid.UUID(conversation_id))
            .order_by(ConversationMessage.created_at)
        )
        messages = result.scalars().all()

        return [
            {
                "id": str(msg.id),
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            }
            for msg in messages
        ]

    async def end_conversation(self, conversation_id: str, resolution_type: str, outcome: str) -> None:
        """Mark a conversation as ended."""
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == uuid.UUID(conversation_id))
        )
        conversation = result.scalar_one_or_none()
        if conversation:
            conversation.status = "RESOLVED"
            conversation.resolution_type = resolution_type
            conversation.outcome = outcome
            conversation.resolved_at = datetime.utcnow()
            conversation.closed_at = datetime.utcnow()
            await self.db.commit()
