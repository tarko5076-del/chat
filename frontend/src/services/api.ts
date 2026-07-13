import type {
  ChatRequest,
  ChatResponse,
  ChatHistoryMessage,
  StreamEvent,
} from "../types/chat";

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

/**
 * Callback interface for streaming chat responses.
 */
export interface StreamCallbacks {
  onToken: (content: string) => void;
  onThinking: (content: string) => void;
  onToolStart: (tool: string, args: Record<string, unknown>) => void;
  onToolResult: (tool: string, success: boolean, message: string) => void;
  onDone: (response: string, conversationId: string) => void;
  onError: (detail: string) => void;
}

/**
 * Send a user message and stream the response via SSE.
 *
 * @param message - The user's message.
 * @param history - Optional conversation history.
 * @param conversationId - Server-side conversation identifier.
 * @param callbacks - Callbacks for streaming events.
 * @returns Cleanup function to abort the stream.
 */
export function sendMessageStream(
  message: string,
  history?: ChatHistoryMessage[],
  conversationId?: string,
  callbacks?: StreamCallbacks,
): () => void {
  const body: ChatRequest = {
    message,
    history,
    conversation_id: conversationId,
  };

  const controller = new AbortController();

  (async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "text/event-stream",
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!response.ok) {
        const errorBody = await response.json().catch(() => null);
        const detail = errorBody?.detail ?? `Request failed with status ${response.status}`;
        callbacks?.onError(detail);
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        callbacks?.onError("No response body");
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";
      let conversationIdFromStream = conversationId ?? "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const data = line.slice(6).trim();
          if (data === "[DONE]") continue;

          try {
            const event: StreamEvent = JSON.parse(data);

            switch (event.type) {
              case "token":
                callbacks?.onToken(event.content);
                break;
              case "thinking":
                callbacks?.onThinking(event.content);
                break;
              case "tool_start":
                callbacks?.onToolStart(event.tool, event.args);
                break;
              case "tool_result":
                callbacks?.onToolResult(event.tool, event.success, event.message);
                break;
              case "conversation_id":
                conversationIdFromStream = event.conversation_id;
                break;
              case "done":
                callbacks?.onDone(event.response, conversationIdFromStream);
                break;
              case "error":
                callbacks?.onError(event.detail);
                break;
            }
          } catch {
            // Skip malformed JSON lines
          }
        }
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        return;
      }
      const message = err instanceof Error ? err.message : "Stream failed";
      callbacks?.onError(message);
    }
  })();

  return () => controller.abort();
}
