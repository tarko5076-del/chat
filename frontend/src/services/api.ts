import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import type {
  ChatRequest,
  ChatHistoryMessage,
  StreamEvent,
} from "../types/chat";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

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
  tagTypes: ["Menu", "Order", "Reservation", "Payment", "Memory"],
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
      query: (params?: { order_id?: number; status?: string }) => ({
        url: "/payments/",
        params,
      }),
      providesTags: ["Payment"],
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
      query: (customerId: string) => `/memory/${customerId}/`,
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
  useCreatePaymentMutation,
  useGetCustomerMemoryQuery,
  useRegisterMutation,
  useLoginMutation,
  useGetProfileQuery,
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
}

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
  const token = localStorage.getItem("access_token");

  (async () => {
    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      };
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const response = await fetch(`${API_BASE_URL}/chat/stream`, {
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
              case "action_required":
                callbacks?.onActionRequired(event.action, event.description, event.params);
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
