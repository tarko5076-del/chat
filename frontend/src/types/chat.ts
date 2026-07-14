/** Represents a single chat message in the conversation. */
export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  actionRequired?: ActionRequired;
}

/** Action metadata when the agent requires user confirmation. */
export interface ActionRequired {
  action: "confirm_order" | "confirm_payment" | "confirm_reservation";
  description: string;
  params: Record<string, unknown>;
}

/** A locally managed conversation in the browser. */
export interface Conversation {
  id: string;
  sessionId: string | null;
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
  session_id?: string;
  customer_id?: string;
  customer_name?: string;
  email?: string;
  phone?: string;
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

/** Represents a goal in the agent's goal stack. */
export interface GoalState {
  description: string;
  status: "pending" | "in_progress" | "completed" | "failed";
  priority: string;
  result: string;
}

/** SSE streaming event types from the backend. */
export type StreamEvent =
  | { type: "token"; content: string }
  | { type: "thinking"; content: string }
  | { type: "tool_start"; tool: string; args: Record<string, unknown> }
  | { type: "tool_result"; tool: string; success: boolean; message: string }
  | {
      type: "action_required";
      action: ActionRequired["action"];
      description: string;
      params: Record<string, unknown>;
    }
  | { type: "done"; response: string; steps: number; goals?: GoalState[] }
  | { type: "conversation_id"; conversation_id: string }
  | { type: "session_id"; session_id: string }
  | { type: "error"; detail: string };
