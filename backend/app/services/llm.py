"""Compatibility wrapper around the restaurant agent."""

from app.agent.controller import agent


async def get_chat_response(user_message: str, history: list[dict] | None = None) -> str:
    """Return the agent response for older imports."""
    return await agent.run(user_message, history)
