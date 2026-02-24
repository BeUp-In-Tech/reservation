"""
Regex-based message parser for the booking chatbot.
No AI/LLM calls - purely rule-based.
"""

import re
from datetime import datetime, timedelta


def parse_message(message: str, context: dict = None) -> dict:
    context = context or {}
    msg = message.strip()
    msg_lower = msg.lower()

    result = {
        "intent": "other",
        "service_mentioned": None,
        "date": None,
        "time": None,
        "slot_start": None,
        "contact": {"name": None, "phone": None, "email": None},
        "booking_id": None,
        "wants_human": False,
    }

    # === Extract booking ID (BK-XXXXXX) ===
    booking_id_match = re.search(r'BK-[A-Fa-f0-9]{6}', msg, re.IGNORECASE)
    if booking_id_match:
        result["booking_id"] = booking_id_match.group(0).upper()

    # === Extract email ===
    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', msg)
    if email_match:
        result["contact"]["email"] = email_match.group(0).lower()

    # === Extract phone ===
    # "phone- 123456789", "phone: +880123", "mobile - 017..."
    phone_label_match = re.search(
        r'(?:phone|mobile|cell|tel|contact)\s*[-:=]?\s*(\+?\d[\d\s\-().]{7,})',
        msg, re.IGNORECASE
    )
    if phone_label_match:
        phone = re.sub(r'[^\d+]', '', phone_label_match.group(1))
        if len(phone) >= 8:
            result["contact"]["phone"] = phone
    else:
        phone_match = re.search(r'(\+?\d[\d\s\-().]{7,}\d)', msg)
        if phone_match:
            phone = re.sub(r'[^\d+]', '', phone_match.group(1))
            if len(phone) >= 8:
                result["contact"]["phone"] = phone

    # === Extract name (case-insensitive) ===
    ci_name_patterns = [
        r'(?:my\s+)?(?:full\s+)?name\s*(?:is|:|-|=)?\s*(.+?)(?:\s*,\s*|\s*\.\s*|\s+phone|\s+email|\s+mobile|\s+cell|$)',
        r"(?:i'?m|i\s+am)\s+(.+?)(?:\s*,\s*|\s*\.\s*|\s+phone|\s+email|$)",
        r'(?:this\s+is)\s+(.+?)(?:\s*,\s*|\s*\.\s*|\s+phone|\s+email|$)',
    ]
    for pattern in ci_name_patterns:
        ci_match = re.search(pattern, msg, re.IGNORECASE)
        if ci_match:
            candidate = ci_match.group(1).strip()
            candidate = re.sub(r'[\s,]+$', '', candidate)
            if (len(candidate) >= 2
                    and '@' not in candidate
                    and not re.match(r'^\+?\d{6,}', candidate)
                    and candidate.lower() not in ('is', 'am', 'the')):
                result["contact"]["name"] = candidate.title()
                break

    # Fallback: if awaiting contact, try capitalized words
    current_step = context.get("current_step", "")
    if current_step == "awaiting_contact" and not result["contact"]["name"]:
        skip_words = {
            'yes', 'no', 'ok', 'sure', 'hi', 'hello', 'hey', 'the', 'my', 'i',
            'please', 'thanks', 'thank', 'it', 'is', 'at', 'on', 'for', 'to',
            'full', 'name', 'phone', 'email', 'number', 'mobile', 'cell',
        }
        words = msg.split()
        name_words = []
        for w in words:
            clean = re.sub(r'[^\w]', '', w)
            if (clean and clean[0].isupper() and clean.lower() not in skip_words
                    and not re.match(r'^BK-', clean) and '@' not in w
                    and not re.match(r'^\+?\d', w)):
                name_words.append(clean)
            elif name_words:
                break
        if name_words:
            result["contact"]["name"] = ' '.join(name_words)

    # === Extract date ===
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    parsed_date = None

    if re.search(r'\btoday\b', msg_lower):
        parsed_date = today.date()
    elif re.search(r'\btomorrow\b', msg_lower):
        parsed_date = tomorrow.date()
    elif re.search(r'\bday after tomorrow\b', msg_lower):
        parsed_date = (today + timedelta(days=2)).date()

    days_map = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
        'friday': 4, 'saturday': 5, 'sunday': 6
    }

    if not parsed_date:
        next_day_match = re.search(r'\bnext\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', msg_lower)
        if next_day_match:
            target_day = days_map[next_day_match.group(1)]
            days_ahead = (target_day - today.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            parsed_date = (today + timedelta(days=days_ahead)).date()

    if not parsed_date:
        this_day_match = re.search(r'\bthis\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', msg_lower)
        if this_day_match:
            target_day = days_map[this_day_match.group(1)]
            days_ahead = (target_day - today.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            parsed_date = (today + timedelta(days=days_ahead)).date()

    if not parsed_date:
        bare_day_match = re.search(r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', msg_lower)
        if bare_day_match:
            target_day = days_map[bare_day_match.group(1)]
            days_ahead = (target_day - today.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            parsed_date = (today + timedelta(days=days_ahead)).date()

    if not parsed_date:
        iso_match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', msg)
        if iso_match:
            try:
                parsed_date = datetime(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))).date()
            except ValueError:
                pass

    if not parsed_date:
        slash_match = re.search(r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})', msg)
        if slash_match:
            d, m, y = int(slash_match.group(1)), int(slash_match.group(2)), int(slash_match.group(3))
            try:
                if d > 12:
                    parsed_date = datetime(y, m, d).date()
                else:
                    parsed_date = datetime(y, d, m).date()
            except ValueError:
                pass

    if not parsed_date:
        months_map = {
            'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3,
            'april': 4, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6,
            'july': 7, 'jul': 7, 'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'sept': 9,
            'october': 10, 'oct': 10, 'november': 11, 'nov': 11, 'december': 12, 'dec': 12,
        }
        day_month_match = re.search(
            r'(\d{1,2})(?:st|nd|rd|th)?\s+(january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sep|sept|october|oct|november|nov|december|dec)',
            msg_lower
        )
        if day_month_match:
            day = int(day_month_match.group(1))
            month = months_map.get(day_month_match.group(2))
            if month:
                year = today.year
                try:
                    candidate = datetime(year, month, day).date()
                    if candidate < today.date():
                        candidate = datetime(year + 1, month, day).date()
                    parsed_date = candidate
                except ValueError:
                    pass

        if not parsed_date:
            month_day_match = re.search(
                r'(january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sep|sept|october|oct|november|nov|december|dec)\s+(\d{1,2})(?:st|nd|rd|th)?',
                msg_lower
            )
            if month_day_match:
                month = months_map.get(month_day_match.group(1))
                day = int(month_day_match.group(2))
                if month:
                    year = today.year
                    try:
                        candidate = datetime(year, month, day).date()
                        if candidate < today.date():
                            candidate = datetime(year + 1, month, day).date()
                        parsed_date = candidate
                    except ValueError:
                        pass

    if parsed_date:
        result["date"] = parsed_date.isoformat()

    # === Extract time ===
    parsed_time = None

    time_match = re.search(r'(\d{1,2}):(\d{2})\s*(am|pm)', msg, re.IGNORECASE)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
        period = time_match.group(3).lower()
        if period == 'pm' and hour != 12:
            hour += 12
        elif period == 'am' and hour == 12:
            hour = 0
        parsed_time = f"{hour:02d}:{minute:02d}"

    if not parsed_time:
        time_match2 = re.search(r'(\d{1,2})\s*(am|pm)', msg, re.IGNORECASE)
        if time_match2:
            hour = int(time_match2.group(1))
            period = time_match2.group(2).lower()
            if period == 'pm' and hour != 12:
                hour += 12
            elif period == 'am' and hour == 12:
                hour = 0
            parsed_time = f"{hour:02d}:00"

    if not parsed_time:
        time_24_match = re.search(r'\b(\d{2}):(\d{2})\b', msg)
        if time_24_match:
            hour = int(time_24_match.group(1))
            minute = int(time_24_match.group(2))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                parsed_time = f"{hour:02d}:{minute:02d}"

    if parsed_time:
        result["time"] = parsed_time

    if result["date"] and result["time"]:
        result["slot_start"] = f"{result['date']}T{result['time']}:00"

    # === Determine intent ===

    if re.match(r'^(hi|hello|hey|good\s+(morning|afternoon|evening)|greetings|howdy|hola|assalamu|salam)\b', msg_lower):
        result["intent"] = "greet"
        return result

    if re.search(r'\bcancel\b', msg_lower) and (result["booking_id"] or re.search(r'\b(book|reservation|appointment)\b', msg_lower)):
        result["intent"] = "cancel_booking"
        return result

    if current_step == "awaiting_cancel_confirm" and re.search(r'\b(yes|yeah|yep|confirm|sure|go ahead|do it|ok|okay)\b', msg_lower):
        result["intent"] = "confirm_cancel"
        return result

    if current_step == "awaiting_cancel_confirm" and re.search(r'\b(no|nah|nope|never)\b', msg_lower):
        result["intent"] = "decline"
        return result

    if re.search(r'\b(reschedule|change\s+time|move\s+(my\s+)?booking|change\s+(my\s+)?(booking|appointment|date|time))\b', msg_lower):
        result["intent"] = "reschedule"
        return result

    if re.search(r'\b(status|check|track)\b', msg_lower) and (result["booking_id"] or re.search(r'\b(book|reservation|appointment)\b', msg_lower)):
        result["intent"] = "check_status"
        return result

    if re.search(r'\b(human|agent|person|representative|speak\s+to|talk\s+to|real\s+person|support)\b', msg_lower):
        result["wants_human"] = True
        result["intent"] = "escalate"
        return result

    if re.search(r'\b(services?|what\s+(do\s+you|can\s+you)|list|available|options?|menu|offerings?|what\s+you\s+have)\b', msg_lower):
        result["intent"] = "list_services"
        return result

    if current_step == "awaiting_confirm" and re.search(r'\b(yes|yeah|yep|confirm|sure|go ahead|book\s+it|proceed|correct|right|ok|okay|looks?\s+good|perfect)\b', msg_lower):
        result["intent"] = "confirm_booking"
        return result

    if current_step == "awaiting_confirm" and re.search(r'\b(no|nah|nope|wrong|incorrect|change|wait)\b', msg_lower):
        result["intent"] = "decline"
        return result

    available_services = context.get("available_services", [])
    for svc in available_services:
        svc_name = svc.get("service_name", "")
        if svc_name and svc_name.lower() in msg_lower:
            result["intent"] = "select_service"
            result["service_mentioned"] = svc_name
            return result

    if result["slot_start"] or result["date"] or result["time"]:
        result["intent"] = "select_slot"
        return result

    has_any_contact = any([result["contact"]["name"], result["contact"]["phone"], result["contact"]["email"]])
    if has_any_contact:
        result["intent"] = "provide_contact"
        return result

    result["intent"] = "other"
    return result