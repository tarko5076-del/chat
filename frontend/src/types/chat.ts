/** Represents a single chat message in the conversation. */
export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

/** A locally managed conversation in the browser. */
export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
}

/** Represents a message in the conversation history (simplified for API). */
export interface ChatHistoryMessage {
  role: "user" | "assistant";
  content: string;
}

/** Request payload sent to the POST /chat endpoint. */
export interface ChatRequest {
  message: string;
  customer_id?: string;
  customer_name?: string;
  email?: string;
  phone?: string;
  conversation_id?: string;
  history?: ChatHistoryMessage[];
}

/** Response payload returned from the POST /chat endpoint. */
export interface ChatResponse {
  response: string;
  conversation_id: string;
}

/** Error response from the API. */
export interface ApiError {
  detail: string;
}
