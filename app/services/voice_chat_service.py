from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Service, Business
from app.models.other_models import BusinessAISettings
from app.services.llm import call_llm_with_history


class VoiceChatService:
    """
    Voice-specific chat service - INFO ONLY, NO BOOKING.
    Only provides service info, prices, availability.
    When user confirms, directs to press 00 to proceed to chat.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_voice_message(
        self,
        business_id: str,
        user_message: str,
        conversation_history: list = None
    ) -> dict:
        """Process voice message - INFO ONLY, no booking."""
        
        import uuid
        business_uuid = uuid.UUID(business_id)

        # Get business info
        result = await self.db.execute(
            select(Business).where(Business.id == business_uuid)
        )
        business = result.scalar_one_or_none()
        
        if not business:
            return {
                "response": "Sorry, I couldn't find the business information.",
                "ready_to_book": False,
                "press_00": False
            }

        # Get AI settings
        result = await self.db.execute(
            select(BusinessAISettings).where(BusinessAISettings.business_id == business_uuid)
        )
        ai_settings = result.scalar_one_or_none()

        # Get services
        result = await self.db.execute(
            select(Service).where(Service.business_id == business_uuid, Service.is_active == True)
        )
        services = result.scalars().all()

        service_list = "\n".join([
            f"- {s.service_name}: {s.base_price} {s.currency or 'USD'} ({s.duration_minutes} minutes)"
            for s in services
        ])

        # Check if user wants to book
        user_lower = user_message.lower()
        booking_phrases = ["yes", "confirm", "book", "proceed", "i want to book", "let's do it", 
                          "okay", "sure", "go ahead", "yes please", "book it", "i'll take it"]
        
        wants_to_book = any(phrase in user_lower for phrase in booking_phrases)

        if wants_to_book:
            return {
                "response": "Great! To complete your booking, please press 00. You'll be redirected to provide your details and complete the payment.",
                "ready_to_book": True,
                "press_00": True
            }

        # System prompt for INFO ONLY
        system_prompt = f"""You are {ai_settings.agent_name if ai_settings else 'a helpful assistant'} for {business.business_name}.
Your tone is {ai_settings.tone_of_voice if ai_settings else 'friendly and professional'}.

CRITICAL RULES - YOU MUST FOLLOW:
1. You ONLY provide information about services, prices, and availability
2. You DO NOT collect any personal information (no name, email, phone)
3. You DO NOT create bookings or confirm reservations
4. You DO NOT ask for payment details
5. Keep responses SHORT (1-2 sentences max for voice)
6. When user shows interest in booking, ask: "Would you like to proceed with the booking?"
7. If they say yes, respond EXACTLY: "Great! Please press 00 to proceed. You'll provide your details in the next step."

Available Services:
{service_list}

Remember: NEVER collect contact details. NEVER create bookings. Only provide information."""

        # Build messages for LLM
        messages = conversation_history or []
        messages.append({"role": "user", "content": user_message})

        # Call LLM
        response = await call_llm_with_history(
            system_prompt=system_prompt,
            messages=messages
        )

        # Shorten for voice
        response = self._shorten_for_voice(response)

        # Check if response mentions press 00
        press_00 = "press 00" in response.lower() or "press zero zero" in response.lower()

        return {
            "response": response,
            "ready_to_book": press_00,
            "press_00": press_00
        }

    def _shorten_for_voice(self, text: str) -> str:
        """Make response suitable for voice."""
        text = text.replace("**", "").replace("*", "")
        text = text.replace("\n\n", ". ").replace("\n", ". ")

        lines = text.split(". ")
        cleaned = [l.strip().lstrip("- ") for l in lines if l.strip()]
        text = ". ".join(cleaned)

        if len(text) > 250:
            sentences = text.split(". ")
            short = ""
            for s in sentences:
                if len(short) + len(s) < 200:
                    short += s + ". "
                else:
                    break
            text = short.strip()

        return text

