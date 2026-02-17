from app.services.chat_state import BookingState
from app.services.llm import extract_json_from_llm, call_llm_with_history

# ============== NODE 1: Parse user message ==============

async def parse_message_node(state: BookingState) -> BookingState:
    """
    Extract intent and entities from the user's message.
    This node runs first for every user message.
    """
    from datetime import datetime, timedelta
    
    # Get current date info for proper date parsing
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    
    # Calculate next week days
    days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    current_day_name = days_of_week[today.weekday()]
    
    date_context = f"""
Current date/time information (USE THIS FOR DATE PARSING):
- Today is: {current_day_name}, {today.strftime('%B %d, %Y')}
- Today's date: {today.strftime('%Y-%m-%d')}
- Tomorrow's date: {tomorrow.strftime('%Y-%m-%d')}
- Current time: {today.strftime('%H:%M')}

When user says:
- "today" = {today.strftime('%Y-%m-%d')}
- "tomorrow" = {tomorrow.strftime('%Y-%m-%d')}
- "next Monday" = calculate from today's date
- "this weekend" = the upcoming Saturday/Sunday
"""

    services_list = state.get("available_services", [])
    services_names = [s["service_name"] for s in services_list] if services_list else []

    system_prompt = f"""
You are an intent and entity extractor for a booking chatbot.

{date_context}

Available services at this business: {services_names}

Analyze the user's message and extract:
1. intent: What does the user want to do?
   (Example intents: "greet", "list_services", "select_service", "ask_service_details", "select_slot", "provide_contact", "confirm_booking", "complete_booking", "check_status", "cancel_booking", "confirm_cancel", "reschedule", "escalate", "cancel", "other")
   
2. entities: What specific information did they provide?
   (Example entities: "service_name", "date_mentioned", "time_mentioned", "contact_info")

Respond with JSON only:
{{
    "intent": "greet" | "list_services" | "select_service" | "ask_service_details" | "select_slot" | "provide_contact" | "confirm_booking" | "complete_booking" | "check_status" | "cancel_booking" | "confirm_cancel" | "reschedule" | "escalate" | "cancel" | "book_business" | "other",
    "business_name": "business name if mentioned, or null",
    "business_slug": "business slug if mentioned, or null",
    "service_mentioned": "service name if mentioned, or null",
    "date_mentioned": "date if mentioned (YYYY-MM-DD format based on current date above), or null",
    "time_mentioned": "time if mentioned (HH:MM 24hr format), or null",
    "contact_info": {{
        "name": "name if provided, or null",
        "phone": "phone if provided, or null",
        "email": "email if provided, or null"
    }},
    "wants_human": true if user wants to talk to a human/agent/person, false otherwise,
    "booking_id_mentioned": "booking/tracking ID if mentioned (like BK-XXXXXX), or null"
}}

Intent definitions:
- greet: "hello", "hi", "good morning", etc.
- list_services: User wants to see what services are available.
- select_service: User is choosing/mentioning a specific service to book.
- ask_service_details: User wants more info about a service (price, duration, etc.).
- select_slot: User is choosing a date/time for booking.
- provide_contact: User is giving their name, phone, or email.
- confirm_booking: User says "yes", "confirm", "book it", "proceed", "go ahead", "that's correct" to finalize a booking.
- complete_booking: User provides ALL booking info at once (service + date/time + contact info in one message).
- check_status: User asks "what's my booking status" or "check booking BK-XXXXXX" (MUST mention status/tracking ID).
- cancel_booking: User EXPLICITLY says "cancel my booking", "I want to cancel".
- confirm_cancel: User confirms cancellation AFTER being asked "are you sure you want to cancel?".
- reschedule: User wants to CHANGE their existing booking time.
- escalate: User wants to talk to a human/agent/real person.
- other: Doesn't fit above categories.
- book_business: User mentions they want to book a business by name or slug.
"""

    current_msg = state.get("current_message", "")

    extracted = await extract_json_from_llm(system_prompt, current_msg)

    # Update state with extracted information
    state["parsed_intent"] = extracted.get("intent", "other")
    
    # Check if the user is trying to book a business
    if extracted.get("intent") == "book_business":
        # If intent is "book_business", capture the business mentioned
        state["business_name"] = extracted.get("business_name")
    
    if extracted.get("service_mentioned"):
        # Find service ID from name
        service_found = False
        for svc in services_list:
            if svc["service_name"].lower() == extracted["service_mentioned"].lower():
                state["selected_service_id"] = svc["id"]
                state["selected_service_name"] = svc["service_name"]
                service_found = True
                break
        
        if not service_found:
            # Store the unmatched service name so AI can respond appropriately
            state["service_not_found"] = extracted["service_mentioned"]
            available_names = [s["service_name"] for s in services_list]
            state["available_service_names"] = available_names

    if extracted.get("date_mentioned") and extracted.get("time_mentioned"):
        state["selected_slot_start"] = f"{extracted['date_mentioned']}T{extracted['time_mentioned']}:00"
        state["selected_slot_end"] = None  # will be calculated in service
    elif extracted.get("date_mentioned"):
        # ✅ IMPORTANT: do NOT auto-set a time
        # store date only so the bot asks for time
        state["selected_slot_start"] = None
        state["selected_slot_end"] = None
        state["selected_slot_date"] = extracted["date_mentioned"]  # ✅ add this key

    contact = extracted.get("contact_info", {})
    if contact.get("name"):
        state["customer_name"] = contact["name"]
    if contact.get("phone"):
        state["customer_phone"] = contact["phone"]
    if contact.get("email"):
        state["customer_email"] = contact["email"]

    if extracted.get("wants_human"):
        state["needs_escalation"] = True
    
    # Store booking ID if mentioned (for status check, cancel, reschedule)
    if extracted.get("booking_id_mentioned"):
        state["mentioned_booking_id"] = extracted["booking_id_mentioned"]

    return state


# ============== NODE 2: Router (decides next step) ==============
def route_after_parse(state: BookingState) -> str:
    """
    Conditional edge function - decides which node to go to next.
    Returns the name of the next node.
    """
    
    intent = state.get("parsed_intent", "other")
    
    # Check for escalation first
    if state.get("needs_escalation"):
        return "escalate_node"
    
    # Route based on intent
    if intent == "greet":
        return "greet_node"
    
    if intent == "list_services":
        return "list_services_node"
    
    if intent == "select_service":
        return "handle_service_selection_node"
    
    if intent == "ask_service_details":
        return "show_service_details_node"
    
    if intent == "select_slot":
        return "handle_slot_selection_node"
    
    if intent == "provide_contact":
        return "handle_contact_node"
    
    if intent == "confirm_booking":
        return "confirm_booking_node"
    
    if intent == "complete_booking":
        return "confirm_booking_node"
    
    if intent == "check_status":
        return "check_status_node"
    
    if intent == "cancel_booking":
        return "cancel_booking_node"
    
    if intent == "confirm_cancel":
        return "confirm_cancel_node"
    
    if intent == "reschedule":
        return "reschedule_node"
    
    if intent == "escalate":
        return "escalate_node"
    
    # Default: generate a helpful response
    return "general_response_node"


# ============== NODE 3: Greet ==============

async def greet_node(state: BookingState) -> BookingState:
    """Handle greetings and introduce the assistant."""
    
    agent_name = state.get("ai_agent_name", "Assistant")
    business_name = state.get("business_name", "our business")
    tone = state.get("ai_tone", "friendly and professional")
    
    system_prompt = f"""You are {agent_name}, a {tone} booking assistant for {business_name}.
    
The user just greeted you. Respond with a warm greeting and ask how you can help them today.
Mention that you can help them book services, check availability, or answer questions.

Keep your response brief (2-3 sentences max)."""
    
    messages = state.get("messages", [])
    response = await call_llm_with_history(system_prompt, messages)
    
    state["response"] = response
    return state


# ============== NODE 4: List Services ==============

async def list_services_node(state: BookingState) -> BookingState:
    """Show available services to the user."""
    
    agent_name = state.get("ai_agent_name", "Assistant")
    business_name = state.get("business_name", "our business")
    tone = state.get("ai_tone", "friendly and professional")
    services = state.get("available_services", [])
    
    services_text = "\n".join([
        f"- {s['service_name']}: {s.get('description', 'No description')} - {s.get('base_price', 'Price varies')} {s.get('currency', '')}"
        for s in services
    ]) if services else "No services currently available."
    
    system_prompt = f"""You are {agent_name}, a {tone} booking assistant for {business_name}.

The user wants to see available services. Here are the services:

{services_text}

Present these services in a friendly way and ask which one they'd like to book.
Keep your response concise but informative."""
    
    messages = state.get("messages", [])
    response = await call_llm_with_history(system_prompt, messages)
    
    state["response"] = response
    return state


# ============== NODE 5: Handle Service Selection ==============

async def handle_service_selection_node(state: BookingState) -> BookingState:
    """User has selected a service - ask for the preferred date and time."""
    
    agent_name = state.get("ai_agent_name", "Assistant")
    tone = state.get("ai_tone", "friendly and professional")
    business_name = state.get("business_name")
    service_name = state.get("selected_service_name")
    
    # Check if the user has selected a valid service
    if not service_name:
        # If no service is selected, prompt user to select one
        services = state.get("available_services", [])
        service_names = [service["service_name"] for service in services]
        state["response"] = f"Sorry, that service is not available. The available services are: {', '.join(service_names)}. Which one would you like to book?"
        return state

    # If a service is selected, ask the user for their preferred date and time
    system_prompt = f"""You are {agent_name}, a {tone} booking assistant for {business_name}.
    
The user has selected the service: {service_name}

Ask the user when they would like to book this service.
Provide the available time slots and let them pick one."""
    
    # Retrieve the conversation history and prompt the assistant
    messages = state.get("messages", [])
    response = await call_llm_with_history(system_prompt, messages)
    
    # Set the AI response and the next action in the flow
    state["response"] = response
    state["next_action"] = "await_slot_selection"  # Move to the next node to select a time slot
    return state


# ============== NODE 6: Handle Slot Selection ==============

async def handle_slot_selection_node(state: BookingState) -> BookingState:
    """User provided time preference - acknowledge and ask for contact info."""
    
    agent_name = state.get("ai_agent_name", "Assistant")
    tone = state.get("ai_tone", "friendly and professional")
    slot = state.get("selected_slot_start", "the selected time")
    service_name = state.get("selected_service_name", "the service")
    
    # Check if we have service selected
    if not state.get("selected_service_id"):
        system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user mentioned a time but hasn't selected a service yet.
Politely ask them which service they'd like to book first."""
        
        messages = state.get("messages", [])
        response = await call_llm_with_history(system_prompt, messages)
        state["response"] = response
        return state
    
    system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user wants to book {service_name} at {slot}.

Confirm the time and ask for their contact information:
- Full name
- Phone number
- Email address

Keep your response brief and friendly."""
    
    messages = state.get("messages", [])
    response = await call_llm_with_history(system_prompt, messages)
    
    state["response"] = response
    state["next_action"] = "await_contact_info"
    return state


# ============== NODE 7: Handle Contact Info ==============

async def handle_contact_node(state: BookingState) -> BookingState:
    """User provided contact info - check if complete and proceed to confirmation."""
    
    agent_name = state.get("ai_agent_name", "Assistant")
    tone = state.get("ai_tone", "friendly and professional")
    
    name = state.get("customer_name")
    phone = state.get("customer_phone")
    email = state.get("customer_email")
    
    missing = []
    if not name:
        missing.append("name")
    if not phone:
        missing.append("phone number")
    if not email:
        missing.append("email address")
    
    if missing:
        system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user provided some contact information, but we still need: {', '.join(missing)}.

Politely ask for the missing information.
Keep your response brief."""
        
        messages = state.get("messages", [])
        response = await call_llm_with_history(system_prompt, messages)
        state["response"] = response
        return state
    
    # All contact info collected - summarize and ask for confirmation
    service_name = state.get("selected_service_name", "the service")
    slot = state.get("selected_slot_start", "the selected time")
    
    system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user has provided all information for their booking:
- Service: {service_name}
- Time: {slot}
- Name: {name}
- Phone: {phone}
- Email: {email}

Summarize the booking details and ask them to confirm.
Tell them clearly: the booking will be CONFIRMED only after payment is completed.

Keep your response clear and professional."""
    
    messages = state.get("messages", [])
    response = await call_llm_with_history(system_prompt, messages)
    
    state["response"] = response
    state["next_action"] = "await_confirmation"
    return state


# ============== NODE 8: Confirm Booking ==============

async def confirm_booking_node(state: BookingState) -> BookingState:
    """User confirmed - create booking and provide tracking ID."""

    agent_name = state.get("ai_agent_name", "Assistant")
    tone = state.get("ai_tone", "friendly and professional")
    services = state.get("available_services", [])

    # Check if user mentioned a service that doesn't exist
    has_service = state.get("selected_service_id")
    
    if not has_service:
        # Check if user mentioned something that wasn't matched
        current_msg = state.get("current_message", "").lower()
        service_keywords = ["room", "suite", "massage", "spa", "service", "book"]
        mentioned_service = any(kw in current_msg for kw in service_keywords)
        
        if mentioned_service:
            available_names = [s["service_name"] for s in services]
            state["response"] = f"Sorry, that service is not available here. Our available services are: {', '.join(available_names)}. Which one would you like to book?"
            return state
    
    has_slot = state.get("selected_slot_start")
    has_name = state.get("customer_name")
    has_phone = state.get("customer_phone")
    has_email = state.get("customer_email")

    missing = []
    if not has_service:
        missing.append("service selection")
    if not has_slot:
        missing.append("preferred date and time")
    if not has_name:
        missing.append("your name")
    if not has_phone:
        missing.append("your phone number")
    if not has_email:
        missing.append("your email address")

    if missing:
        # Ask for missing info instead of failing
        missing_text = ", ".join(missing)
        system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user wants to confirm their booking, but we still need: {missing_text}

Politely ask for the missing information. Be brief (1-2 sentences).
Do NOT say you cannot book - just ask for what's missing."""

        messages = state.get("messages", [])
        response = await call_llm_with_history(system_prompt, messages)
        state["response"] = response
        return state

    # All info present - booking will be created by chat_service
    service_name = state.get("selected_service_name", "the service")
    slot = state.get("selected_slot_start") or state.get("selected_slot_date") or ""
    customer_name = state.get("customer_name", "")

    # Format slot nicely if possible
    slot_display = slot
    try:
        from datetime import datetime
        if slot and "T" in slot:
            dt = datetime.fromisoformat(slot.replace("Z", "+00:00"))
            slot_display = dt.strftime("%B %d, %Y at %I:%M %p")
    except:
        pass

    response = (
        f"Thanks {customer_name}! I've recorded your booking request for {service_name} on {slot_display}. "
        f"Your booking will be confirmed once payment is completed."
    )

    state["response"] = response
    state["booking_status"] = "PENDING_PAYMENT"

    return state


# ============== NODE 9: Escalate to Human ==============

async def escalate_node(state: BookingState) -> BookingState:
    """User wants to talk to a human."""
    
    agent_name = state.get("ai_agent_name", "Assistant")
    tone = state.get("ai_tone", "friendly and professional")
    
    system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user wants to speak with a human team member.

Let them know:
1. You understand they'd prefer to speak with a person
2. Ask for their contact information (name, phone, email) if not already provided
3. A team member will reach out to them shortly
4. They will receive a ticket ID for reference

Be empathetic and helpful."""
    
    messages = state.get("messages", [])
    response = await call_llm_with_history(system_prompt, messages)
    
    state["response"] = response
    state["needs_escalation"] = True
    return state


# ============== NODE 10: General Response ==============

async def general_response_node(state: BookingState) -> BookingState:
    """Handle general queries or unclear intents."""
    
    # Check if user mentioned a service that doesn't exist
    if state.get("service_not_found"):
        not_found = state.get("service_not_found")
        available = state.get("available_service_names", [])
        state["response"] = f"Sorry, '{not_found}' is not available here. Our services are: {', '.join(available)}. Which one would you like to book?"
        return state

    agent_name = state.get("ai_agent_name", "Assistant")
    business_name = state.get("business_name", "our business")
    tone = state.get("ai_tone", "friendly and professional")
    services = state.get("available_services", [])

    services_info = "\n".join([
        f"- {s['service_name']}: {s.get('base_price', 'Price varies')} {s.get('currency', 'BDT')}"
        for s in services
    ]) if services else "No services available."

    # Check what info we already have
    has_service = state.get("selected_service_name")
    has_slot = state.get("selected_slot_start")
    has_contact = all([
        state.get("customer_name"),
        state.get("customer_phone"),
        state.get("customer_email")
    ])

    missing_info = []
    if not has_service:
        missing_info.append("which service they want")
    if not has_slot:
        missing_info.append("their preferred date and time")
    if not has_contact:
        missing_info.append("their contact information (name, phone, email)")

    system_prompt = f"""You are {agent_name}, a {tone} booking assistant for {business_name}.

IMPORTANT: You CAN and SHOULD help customers book directly. You have FULL booking capability.

Available services:
{services_info}

Current booking progress:
- Service selected: {has_service or 'Not yet'}
- Date/time selected: {has_slot or 'Not yet'}
- Contact info provided: {'Yes' if has_contact else 'Not yet'}

Missing information: {', '.join(missing_info) if missing_info else 'None - ready to confirm!'}

RULES:
1. NEVER say "I can't book" or "I can't finalize" - YOU CAN BOOK DIRECTLY
2. If user wants to book, ask for the missing information ONE STEP AT A TIME
3. Keep responses SHORT (2-3 sentences max for voice)
4. Be helpful and guide them through the booking process

If the user's intent is unclear, ask a clarifying question.
If they want to book, ask for the FIRST missing piece of information."""

    messages = state.get("messages", [])
    response = await call_llm_with_history(system_prompt, messages)

    state["response"] = response
    return state


# ============== NODE 11: Show Service Details ==============

async def show_service_details_node(state: BookingState) -> BookingState:
    """Show detailed information about a service."""
    
    agent_name = state.get("ai_agent_name", "Assistant")
    tone = state.get("ai_tone", "friendly and professional")
    services = state.get("available_services", [])
    service_name = state.get("selected_service_name")
    
    # Find the service details
    service_details = None
    for s in services:
        if s.get("service_name", "").lower() == (service_name or "").lower():
            service_details = s
            break
    
    if service_details:
        details_text = f"""
Service: {service_details.get('service_name')}
Description: {service_details.get('description', 'No description available')}
Price: {service_details.get('base_price', 'Price varies')} {service_details.get('currency', '')}
Duration: {service_details.get('duration_minutes', 'Varies')} minutes
"""
    else:
        details_text = "I couldn't find details for that service."
    
    system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

Here are the service details:
{details_text}

Present this information in a friendly way and ask if they'd like to book this service.
Keep your response informative but concise."""
    
    messages = state.get("messages", [])
    response = await call_llm_with_history(system_prompt, messages)
    
    state["response"] = response
    return state


# ============== NODE 12: Check Booking Status ==============

async def check_status_node(state: BookingState) -> BookingState:
    """Handle booking status check requests."""
    
    agent_name = state.get("ai_agent_name", "Assistant")
    tone = state.get("ai_tone", "friendly and professional")
    mentioned_booking_id = state.get("mentioned_booking_id")
    
    # If user provided a booking ID, we'll look it up
    if mentioned_booking_id:
        # The actual lookup will happen in chat_service
        # For now, just acknowledge we have the ID
        system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user wants to check their booking status and provided tracking ID: {mentioned_booking_id}

Let them know you're looking up their booking and will provide the details shortly.
Keep your response brief."""
    else:
        system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user wants to check their booking status but hasn't provided a tracking ID.

Ask them for their booking tracking ID (it looks like BK-XXXXXX).
Let them know you'll look up their booking once they provide the ID.

Keep your response brief."""
    
    messages = state.get("messages", [])
    response = await call_llm_with_history(system_prompt, messages)
    
    state["response"] = response
    return state


# ============== NODE 13: Cancel Booking ==============

async def cancel_booking_node(state: BookingState) -> BookingState:
    """Handle booking cancellation requests."""
    
    agent_name = state.get("ai_agent_name", "Assistant")
    tone = state.get("ai_tone", "friendly and professional")
    mentioned_booking_id = state.get("mentioned_booking_id")
    current_booking_id = state.get("public_tracking_id")
    
    # Check if we have a booking to cancel
    booking_id = mentioned_booking_id or current_booking_id
    
    if booking_id:
        system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user wants to cancel their booking (ID: {booking_id}).

Ask them to confirm they want to cancel this booking.
Let them know that cancellation cannot be undone.

Keep your response brief and empathetic."""
    else:
        system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user wants to cancel a booking but hasn't specified which one.

Ask them for their booking tracking ID (it looks like BK-XXXXXX).

Keep your response brief."""
    
    messages = state.get("messages", [])
    response = await call_llm_with_history(system_prompt, messages)
    
    state["response"] = response
    state["next_action"] = "await_cancel_confirmation"
    return state


# ============== NODE 14: Reschedule Booking ==============

async def reschedule_node(state: BookingState) -> BookingState:
    """Handle booking rescheduling requests."""
    
    agent_name = state.get("ai_agent_name", "Assistant")
    tone = state.get("ai_tone", "friendly and professional")
    mentioned_booking_id = state.get("mentioned_booking_id")
    current_booking_id = state.get("public_tracking_id")
    current_slot = state.get("selected_slot_start")
    
    # Check if we have a booking to reschedule
    booking_id = mentioned_booking_id or current_booking_id
    
    if booking_id:
        if current_slot:
            system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user wants to reschedule their booking (ID: {booking_id}).
Current appointment time: {current_slot}

Ask them when they would like to reschedule to.
Request their preferred new date and time.

Keep your response brief and helpful."""
        else:
            system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user wants to reschedule their booking (ID: {booking_id}).

Ask them when they would like to reschedule to.
Request their preferred new date and time.

Keep your response brief and helpful."""
    else:
        system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user wants to reschedule a booking but hasn't specified which one.

Ask them for their booking tracking ID (it looks like BK-XXXXXX).

Keep your response brief."""
    
    messages = state.get("messages", [])
    response = await call_llm_with_history(system_prompt, messages)
    
    state["response"] = response
    state["next_action"] = "await_new_slot"
    return state


# ============== NODE 15: Confirm Cancel ==============

async def confirm_cancel_node(state: BookingState) -> BookingState:
    """Handle confirmed booking cancellation."""
    
    agent_name = state.get("ai_agent_name", "Assistant")
    tone = state.get("ai_tone", "friendly and professional")
    mentioned_booking_id = state.get("mentioned_booking_id")
    current_booking_id = state.get("public_tracking_id")
    
    booking_id = mentioned_booking_id or current_booking_id
    
    if booking_id:
        # The actual cancellation will happen in chat_service._handle_special_intents
        state["cancel_confirmed"] = True
        state["booking_to_cancel"] = booking_id
        
        system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user has confirmed they want to cancel booking {booking_id}.
Acknowledge that the booking is being cancelled.

Keep your response brief and empathetic."""
    else:
        system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user confirmed cancellation but we don't have a booking ID.
Ask them for the booking tracking ID.

Keep your response brief."""
    
    messages = state.get("messages", [])
    response = await call_llm_with_history(system_prompt, messages)
    
    state["response"] = response
    return state