import type { ChatRequest, ChatResponse, ChatHistoryMessage } from "../types/chat";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

/**
 * Send a user message to the backend and get an AI response.
 *
 * @param message - The user's message.
 * @param history - Optional conversation history.
 * @param conversationId - Server-side conversation identifier.
 * @returns The assistant's response text.
 * @throws If the network request fails or the API returns an error.
 */
export async function sendMessage(
  message: string,
  history?: ChatHistoryMessage[],
  conversationId?: string,
): Promise<ChatResponse> {
  const body: ChatRequest = {
    message,
    history,
    conversation_id: conversationId,
  };

  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const detail = errorBody?.detail ?? `Request failed with status ${response.status}`;
    throw new Error(detail);
  }

  const data: ChatResponse = await response.json();
  return data;
}
