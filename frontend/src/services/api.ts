import type { ChatRequest, ChatResponse, ChatHistoryMessage } from "../types/chat";

const API_BASE_URL = "http://localhost:8000/api";

/**
 * Send a user message to the backend and get an AI response.
 *
 * @param message - The user's message.
 * @param history - Optional conversation history.
 * @returns The assistant's response text.
 * @throws If the network request fails or the API returns an error.
 */
export async function sendMessage(message: string, history?: ChatHistoryMessage[]): Promise<string> {
  const body: ChatRequest = { message, history };

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
  return data.response;
}
