import json
from datetime import datetime
from openai import AsyncOpenAI
from app.core.config import settings

# Initialize OpenAI client
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


def get_date_context() -> str:
    """Get current date context string."""
    today = datetime.now()
    return f"Current date: {today.strftime('%B %d, %Y')} ({today.strftime('%A')}). Current time: {today.strftime('%I:%M %p')}."


async def call_llm(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.7,
    model: str = "gpt-4o-mini"
) -> str:
    """
    Call OpenAI API and return the response text.
    """
    # Add date context to system prompt
    full_system_prompt = f"{get_date_context()}\n\n{system_prompt}"
    
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": full_system_prompt},
            {"role": "user", "content": user_message}
        ],
        temperature=temperature
    )
    return response.choices[0].message.content


async def call_llm_with_history(
    system_prompt: str,
    messages: list[dict],
    temperature: float = 0.7,
    model: str = "gpt-4o-mini"
) -> str:
    """
    Call OpenAI API with full conversation history.
    """
    # Add date context to system prompt
    full_system_prompt = f"{get_date_context()}\n\n{system_prompt}"
    
    full_messages = [{"role": "system", "content": full_system_prompt}] + messages
    response = await client.chat.completions.create(
        model=model,
        messages=full_messages,
        temperature=temperature
    )
    return response.choices[0].message.content


async def extract_json_from_llm(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.0,
    model: str = "gpt-4o-mini"
) -> dict:
    """
    Call OpenAI API and parse the response as JSON.
    Used for structured extraction (intents, entities, etc.)
    """
    # Add date context to system prompt
    full_system_prompt = f"{get_date_context()}\n\n{system_prompt}"
    
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": full_system_prompt},
            {"role": "user", "content": user_message}
        ],
        temperature=temperature,
        response_format={"type": "json_object"}
    )
    
    content = response.choices[0].message.content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"error": "Failed to parse JSON", "raw": content}
