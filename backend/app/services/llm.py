"""Service layer for interacting with the Hugging Face Inference API."""

from openai import AsyncOpenAI, RateLimitError, APIConnectionError
import logging

from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = "You are a helpful assistant."

# Recommended Hugging Face headers
APP_URL = "http://localhost:8000"
APP_NAME = "AI Chatbot"

# Timeout for the API call: 30 seconds for the overall operation
REQUEST_TIMEOUT = 30.0


async def get_chat_response(user_message: str, history: list[dict] | None = None) -> str:
    """Send a user message to Hugging Face and return the assistant's response.

    Args:
        user_message: The message from the user.
        history: Optional conversation history as a list of message dicts with 'role' and 'content'.

    Returns:
        The assistant's reply as a string.

    Raises:
        ValueError: If the API key is missing or the message is empty.
        openai.OpenAIError: If the API call fails.
    """
    if not settings.hf_token:
        raise ValueError(
            "Hugging Face token is missing. "
            "Set the HF_TOKEN environment variable in your .env file."
        )

    if not user_message or not user_message.strip():
        raise ValueError("Message cannot be empty.")

    client = AsyncOpenAI(
        api_key=settings.hf_token,
        base_url=settings.hf_base_url,
    )

    # Build messages array with history
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Add conversation history if provided
    if history:
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
    
    # Add current user message
    messages.append({"role": "user", "content": user_message})

    try:
        response = await client.chat.completions.create(
            model=settings.hf_model,
            max_tokens=1024,
            temperature=0.7,
            timeout=REQUEST_TIMEOUT,
            messages=messages,
        )
    except RateLimitError as error:
        logger.error(f"Rate limit exceeded: {error}")
        raise ValueError("Rate limit exceeded. Please try again later.")
    except APIConnectionError as error:
        logger.error(f"Connection error: {error}")
        raise ValueError("Failed to connect to Hugging Face API. Please check your internet connection.")
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        raise ValueError(f"An unexpected error occurred: {str(error)}")
    finally:
        await client.close()

    # Safely handle empty choices (e.g., content filter refusal)
    if not response.choices:
        logger.warning("No choices returned from the model")
        return "I'm sorry, the model did not return any choices. This may be due to content filtering."

    response_text = response.choices[0].message.content
    return response_text or "I'm sorry, I couldn't generate a response."
