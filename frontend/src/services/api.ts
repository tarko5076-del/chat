import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import type {
  ChatRequest,
  StreamEvent,
} from "../types/chat";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

export interface Session {
  id: string;
  user_id: string;
  title: string;
  metadata: Record<string, unknown>;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface SessionMessage {
  id: number;
  session_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface SessionDetail extends Session {
  messages: SessionMessage[];
}

export const chatApi = createApi({
  reducerPath: "chatApi",
  baseQuery: fetchBaseQuery({
    baseUrl: API_BASE_URL,
    prepareHeaders: (headers) => {
      const token = localStorage.getItem("access_token");
      if (token) {
        headers.set("Authorization", `Bearer ${token}`);
      }
      return headers;
    },
  }),
  tagTypes: ["Menu", "Order", "Reservation", "Payment", "Memory", "StaffNotification", "ToolLog", "Session"],
  endpoints: (builder) => ({
    getMenuItems: builder.query({
      query: () => "/menu/items/",
      providesTags: ["Menu"],
    }),

    getOrders: builder.query({
      query: (params?: { customer_id?: string; status?: string }) => ({
        url: "/orders/",
        params,
      }),
      providesTags: ["Order"],
    }),

    getOrder: builder.query({
      query: (id: number) => `/orders/${id}/`,
      providesTags: (_result, _error, id) => [{ type: "Order", id }],
    }),

    createOrder: builder.mutation({
      query: (body) => ({
        url: "/orders/",
        method: "POST",
        body,
      }),
      invalidatesTags: ["Order"],
    }),

    getReservations: builder.query({
      query: (params?: { customer_id?: string; status?: string }) => ({
        url: "/reservations/",
        params,
      }),
      providesTags: ["Reservation"],
    }),

    createReservation: builder.mutation({
      query: (body) => ({
        url: "/reservations/",
        method: "POST",
        body,
      }),
      invalidatesTags: ["Reservation"],
    }),

    getPayments: builder.query({
      query: (params?: { order_id?: number; status?: string; tx_ref?: string }) => ({
        url: "/payments/",
        params,
      }),
      providesTags: ["Payment"],
    }),

    checkPaymentStatus: builder.query({
      query: (id: number) => `/payments/${id}/check_status/`,
      providesTags: (_result, _error, id) => [{ type: "Payment", id }],
    }),

    createPayment: builder.mutation({
      query: (body) => ({
        url: "/payments/",
        method: "POST",
        body,
      }),
      invalidatesTags: ["Payment"],
    }),

    getCustomerMemory: builder.query({
      query: (customerId: string) => `/agent/memory/${customerId}/`,
      providesTags: ["Memory"],
    }),

    register: builder.mutation({
      query: (body: {
        username: string;
        email: string;
        password: string;
        phone?: string;
      }) => ({
        url: "/users/register/",
        method: "POST",
        body,
      }),
    }),

    login: builder.mutation({
      query: (body: { email: string; password: string }) => ({
        url: "/users/login/",
        method: "POST",
        body,
      }),
    }),

    getProfile: builder.query({
      query: () => "/users/me/",
    }),

    getStaffNotifications: builder.query({
      query: (params?: { status?: string }) => ({
        url: "/agent/staff-notifications/",
        params,
      }),
      providesTags: ["StaffNotification"],
    }),

    updateStaffNotification: builder.mutation({
      query: ({ id, ...body }: { id: number; status: string; staff_notes?: string }) => ({
        url: `/agent/staff-notifications/${id}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: ["StaffNotification"],
    }),

    getToolLogs: builder.query({
      query: (params?: { customer_id?: string; limit?: number }) => ({
        url: "/agent/tool-logs/",
        params,
      }),
      providesTags: ["ToolLog"],
    }),

    getSessions: builder.query({
      query: (params?: { user_id?: string; include_archived?: boolean }) => ({
        url: "/agent/sessions/",
        params,
      }),
      providesTags: ["Session"],
    }),

    getSessionDetail: builder.query({
      query: (sessionId: string) => `/agent/sessions/${sessionId}/`,
      providesTags: ["Session"],
    }),

    createSession: builder.mutation({
      query: (body: { user_id?: string; title?: string }) => ({
        url: "/agent/sessions/",
        method: "POST",
        body,
      }),
      invalidatesTags: ["Session"],
    }),

    updateSession: builder.mutation({
      query: ({ id, ...body }: { id: string; title?: string; is_archived?: boolean }) => ({
        url: `/agent/sessions/${id}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: ["Session"],
    }),

    deleteSession: builder.mutation({
      query: (id: string) => ({
        url: `/agent/sessions/${id}/`,
        method: "DELETE",
      }),
      invalidatesTags: ["Session"],
    }),
  }),
});

export const {
  useGetMenuItemsQuery,
  useGetOrdersQuery,
  useGetOrderQuery,
  useCreateOrderMutation,
  useGetReservationsQuery,
  useCreateReservationMutation,
  useGetPaymentsQuery,
  useCheckPaymentStatusQuery,
  useCreatePaymentMutation,
  useGetCustomerMemoryQuery,
  useRegisterMutation,
  useLoginMutation,
  useGetProfileQuery,
  useGetStaffNotificationsQuery,
  useUpdateStaffNotificationMutation,
  useGetToolLogsQuery,
  useGetSessionsQuery,
  useGetSessionDetailQuery,
  useCreateSessionMutation,
  useUpdateSessionMutation,
  useDeleteSessionMutation,
} = chatApi;

export interface StreamCallbacks {
  onToken: (content: string) => void;
  onThinking: (content: string) => void;
  onToolStart: (tool: string, args: Record<string, unknown>) => void;
  onToolResult: (tool: string, success: boolean, message: string) => void;
  onActionRequired: (
    action: string,
    description: string,
    params: Record<string, unknown>,
  ) => void;
  onDone: (response: string, conversationId: string) => void;
  onError: (detail: string) => void;
  onSessionId?: (sessionId: string) => void;
}

const MAX_STREAM_RETRIES = 2;
const STREAM_RETRY_DELAY_MS = 1500;

export function sendMessageStream(
  message: string,
  sessionId?: string,
  customerId?: string,
  customerName?: string,
  callbacks?: StreamCallbacks,
): () => void {
  const controller = new AbortController();
  let retryCount = 0;

  async function attemptStream() {
    const body: ChatRequest = {
      message,
      session_id: sessionId,
      customer_id: customerId,
      customer_name: customerName,
    };

    const token = localStorage.getItem("access_token");

    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const response = await fetch(`${API_BASE_URL}/agent/chat/stream/`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!response.ok) {
        const errorBody = await response.json().catch(() => null);
        const detail =
          errorBody?.detail ?? `Request failed with status ${response.status}`;
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
      let conversationIdFromStream = sessionId ?? "";

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
              case "action_required":
                callbacks?.onActionRequired(event.action, event.description, event.params);
                break;
              case "conversation_id":
                conversationIdFromStream = event.conversation_id;
                break;
              case "session_id":
                callbacks?.onSessionId?.(event.session_id);
                break;
              case "done":
                callbacks?.onDone(event.response, conversationIdFromStream);
                return;
              case "error":
                callbacks?.onError(event.detail);
                return;
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

      const isNetworkError =
        err instanceof TypeError ||
        (err instanceof DOMException && err.name === "NetworkError") ||
        (err instanceof Error && err.message.includes("fetch"));

      if (isNetworkError && retryCount < MAX_STREAM_RETRIES) {
        retryCount++;
        callbacks?.onThinking(`Reconnecting... (attempt ${retryCount})`);
        await new Promise((r) => setTimeout(r, STREAM_RETRY_DELAY_MS * retryCount));
        if (!controller.signal.aborted) {
          return attemptStream();
        }
      }

      const message = err instanceof Error ? err.message : "Stream failed";
      callbacks?.onError(message);
    }
  }

  attemptStream();

  return () => controller.abort();
}
