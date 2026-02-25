"""
Rule-based voice flow service for Twilio voice calls.
No AI/LLM - all responses driven by database and predefined flow.

Flow:
1. Greeting with service name
2. "Would you like to hear details about this service?"
3. YES -> read details -> "anything else?" -> book (press 0) / human (press 1) / goodbye
4. NO -> "how can I help?" -> if unclear -> "speak to a person?" -> press 1 / goodbye
"""

import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Business, Service, BusinessAISettings


class VoiceFlowService:
    """Database-driven voice flow - no AI."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_business(self, business_id: str) -> dict | None:
        result = await self.db.execute(
            select(Business).where(Business.id == uuid.UUID(business_id))
        )
        business = result.scalar_one_or_none()
        if not business:
            return None
        return {
            "id": str(business.id),
            "business_name": business.business_name,
            "phone": business.phone,
            "slug": business.slug,
        }

    async def get_service(self, service_id: str) -> dict | None:
        result = await self.db.execute(
            select(Service).where(Service.id == uuid.UUID(service_id), Service.is_active == True)
        )
        service = result.scalar_one_or_none()
        if not service:
            return None
        return {
            "id": str(service.id),
            "service_name": service.service_name,
            "description": service.description or "No description available",
            "base_price": float(service.base_price) if service.base_price else None,
            "currency": service.currency or "BDT",
            "duration_minutes": service.duration_minutes,
            "business_id": str(service.business_id),
        }

    async def get_service_details_text(self, service_id: str) -> str:
        """Build a spoken description of the service."""
        svc = await self.get_service(service_id)
        if not svc:
            return "Sorry, I could not find details for this service."

        parts = [f"{svc['service_name']}."]

        if svc["description"] and svc["description"] != "No description available":
            parts.append(svc["description"])

        if svc["base_price"]:
            parts.append(f"The price is {svc['base_price']} {svc['currency']}.")

        if svc["duration_minutes"]:
            hours = svc["duration_minutes"] // 60
            mins = svc["duration_minutes"] % 60
            if hours and mins:
                parts.append(f"Duration is {hours} hour{'s' if hours > 1 else ''} and {mins} minutes.")
            elif hours:
                parts.append(f"Duration is {hours} hour{'s' if hours > 1 else ''}.")
            else:
                parts.append(f"Duration is {mins} minutes.")

        return " ".join(parts)

    async def get_greeting(self, business_id: str, service_id: str) -> str:
        """Build the initial greeting."""
        biz = await self.get_business(business_id)
        svc = await self.get_service(service_id)

        biz_name = biz["business_name"] if biz else "our business"
        svc_name = svc["service_name"] if svc else "our service"

        return (
            f"Hello! Thank you for calling {biz_name}. "
            f"You've selected {svc_name}. "
            f"Would you like to hear the details about this service? "
            f"Press 1 for yes, or press 2 for no."
        )

    async def get_after_details_prompt(self) -> str:
        return (
            "Is there anything else I can help you with? "
            "Press 1 to hear the service details again. "
            "Press 0 to proceed to booking via chat. "
            "Press 9 to speak with a person. "
            "Or press 8 to end the call."
        )

    async def get_how_can_help_prompt(self) -> str:
        return (
            "How can I help you? "
            "Press 1 to hear the service details. "
            "Press 0 to proceed to booking via chat. "
            "Press 9 to speak with a person. "
            "Or press 8 to end the call."
        )

    async def get_escalation_message(self) -> str:
        return "Thank you. A team member will be in touch with you shortly. Goodbye!"

    async def get_goodbye_message(self) -> str:
        return "Thank you for calling. Have a great day! Goodbye!"

    async def get_booking_redirect_message(self) -> str:
        return (
            "Great! You will receive a text message with a link to complete your booking. "
            "Thank you for calling. Goodbye!"
        )

    async def get_not_understood_message(self) -> str:
        return (
            "Sorry, I didn't understand that. "
            "Press 1 to hear service details. "
            "Press 0 to book via chat. "
            "Press 9 to speak with a person. "
            "Press 8 to end the call."
        )