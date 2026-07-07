/** Represents a single chat message in the conversation. */
export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

/** Represents a message in the conversation history (simplified for API). */
export interface ChatHistoryMessage {
  role: "user" | "assistant";
  content: string;
}

/** Request payload sent to the POST /chat endpoint. */
export interface ChatRequest {
  message: string;
  history?: ChatHistoryMessage[];
}

/** Response payload returned from the POST /chat endpoint. */
export interface ChatResponse {
  response: string;
}

/** Error response from the API. */
export interface ApiError {
  detail: string;
}
