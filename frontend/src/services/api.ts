import {
  BaseQueryFn,
  FetchArgs,
  FetchBaseQueryError,
  createApi,
  fetchBaseQuery,
} from "@reduxjs/toolkit/query/react";
import type {
  ChatRequest,
  StreamEvent,
} from "../types/chat";
import { refreshAccessToken } from "./authRefresh";
import { logout } from "../slices/authSlice";

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

/**
 * Custom baseQuery that transparently refreshes expired access tokens.
 *
 * On a 401 response it attempts to refresh the token via `/users/token/refresh/`.
 * If the refresh succeeds, the original request is retried once with the new token.
 * If the refresh fails, the user is logged out.
 */
const baseQuery = fetchBaseQuery({
  baseUrl: API_BASE_URL,
  prepareHeaders: (headers) => {
    const token = localStorage.getItem("access_token");
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    return headers;
  },
});

const baseQueryWithReauth: BaseQueryFn<
  string | FetchArgs,
  unknown,
  FetchBaseQueryError
> = async (args, api, extraOptions) => {
  let result = await baseQuery(args, api, extraOptions);

  if (result.error && result.error.status === 401) {
    // Token might be expired — try to refresh it (at most once)
    const newToken = await refreshAccessToken();
    if (newToken) {
      // Retry the original request with the fresh token
      result = await baseQuery(args, api, extraOptions);
      // If the retry ALSO gives 401 the new token is broken → fall through
      if (result.error && result.error.status === 401) {
        api.dispatch(logout());
      }
    } else {
      // Refresh failed — force logout via RTK's dispatch
      api.dispatch(logout());
    }
  }

  return result;
};

export const chatApi = createApi({
  reducerPath: "chatApi",
  baseQuery: baseQueryWithReauth,
  tagTypes: ["Menu", "Order", "Reservation", "Payment", "Memory", "StaffNotification", "ToolLog", "Session", "_USER"],
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

    getMemoryFacts: builder.query<{ count: number; results: Array<{ id: number; category: string; fact_key: string; fact_value: string; confidence: number; observation_count: number; created_at: string }> }, { category?: string } | void>({
      query: (params) => ({
        url: "/agent/memory/facts/",
        params: params?.category ? { category: params.category } : undefined,
      }),
      providesTags: ["Memory"],
    }),

    deleteMemoryFact: builder.mutation<{ detail: string }, { fact_id: number }>({
      query: ({ fact_id }) => ({
        url: "/agent/memory/facts/",
        method: "DELETE",
        body: { fact_id },
      }),
      invalidatesTags: ["Memory"],
    }),

    deleteAllMemoryFacts: builder.mutation<{ detail: string }, void>({
      query: () => ({
        url: "/agent/memory/facts/?all=true",
        method: "DELETE",
      }),
      invalidatesTags: ["Memory"],
    }),

    getCustomerProfile: builder.query({
      query: () => "/agent/memory/profile/",
      providesTags: ["Memory"],
    }),

    getEpisodicHistory: builder.query<{ count: number; results: Array<{ id: number; event_type: string; tool_name: string; outcome: string; created_at: string }> }, { limit?: number } | void>({
      query: (params) => ({
        url: "/agent/memory/history/",
        params: params?.limit ? { limit: params.limit } : undefined,
      }),
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

    getMetrics: builder.query({
      query: () => "/metrics/",
      providesTags: [],
    }),

    getHealth: builder.query({
      query: () => "/health/",
      providesTags: [],
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
  useGetMemoryFactsQuery,
  useDeleteMemoryFactMutation,
  useDeleteAllMemoryFactsMutation,
  useGetCustomerProfileQuery,
  useGetEpisodicHistoryQuery,
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
  useGetMetricsQuery,
  useGetHealthQuery,
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
  /** Called when the access token could not be refreshed and the user must re-authenticate. */
  onAuthExpired?: () => void;
}

/**
 * Wraps `fetch` with automatic token refresh on 401 responses.
 *
 * If the server returns 401, the function attempts to refresh the access token.
 * On success the request is retried exactly once with the new token.
 * On failure the user is logged out and the original 401 is returned.
 */
/**
 * Wraps `fetch` with automatic token refresh on 401 responses.
 *
 * If the server returns 401, attempts to refresh the access token.
 * On success the request is retried exactly once with the new token.
 * On failure `onAuthExpired` is called (if provided) so the caller can
 * immediately redirect to login instead of waiting for the next RTK Query
 * call to trigger the logout.
 */
async function fetchWithRefresh(
  url: string,
  options: RequestInit,
  onAuthExpired?: () => void,
  retried = false,
): Promise<Response> {
  const response = await fetch(url, options);

  if (response.status === 401 && !retried) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      const newHeaders = { ...(options.headers as Record<string, string>) };
      newHeaders["Authorization"] = `Bearer ${newToken}`;
      return fetchWithRefresh(url, { ...options, headers: newHeaders }, onAuthExpired, true);
    }
    // Refresh failed — notify caller so they can force logout immediately
    onAuthExpired?.();
  }

  return response;
}

export function sendMessageStream(
  message: string,
  sessionId?: string,
  customerId?: string,
  customerName?: string,
  callbacks?: StreamCallbacks,
): () => void {
  const controller = new AbortController();

  async function attemptRequest() {
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

      const onAuthExpired = () => callbacks?.onAuthExpired?.();

      // Try the streaming endpoint first
      const streamResponse = await fetchWithRefresh(
        `${API_BASE_URL}/agent/chat/stream/`,
        {
          method: "POST",
          headers,
          body: JSON.stringify(body),
          signal: controller.signal,
        },
        onAuthExpired,
      );

      if (streamResponse.status === 401) {
        // onAuthExpired already fired via fetchWithRefresh — user is logged out
        return;
      }

      if (streamResponse.ok) {
        // Streaming works - parse SSE events
        const reader = streamResponse.body?.getReader();
        if (reader) {
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
          return;
        }
      }

      // Streaming failed (or no reader) - fall back to non-streaming endpoint
      callbacks?.onThinking("Processing...");

      const jsonResponse = await fetchWithRefresh(
        `${API_BASE_URL}/agent/chat/`,
        {
          method: "POST",
          headers,
          body: JSON.stringify(body),
          signal: controller.signal,
        },
        onAuthExpired,
      );

      if (!jsonResponse.ok) {
        const errorBody = await jsonResponse.json().catch(() => null);
        const detail =
          errorBody?.detail ?? `Request failed with status ${jsonResponse.status}`;
        callbacks?.onError(detail);
        return;
      }

      const result = await jsonResponse.json();
      const responseText = result.response ?? "";
      const responseSessionId = result.session_id;
      const responseConvId = result.conversation_id;

      // Simulate token streaming with the full response
      if (responseText) {
        callbacks?.onToken(responseText);
      }
      if (responseSessionId) {
        callbacks?.onSessionId?.(responseSessionId);
      }
      callbacks?.onDone(responseText, responseConvId ?? responseSessionId ?? "");
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        return;
      }

      const message = err instanceof Error ? err.message : "Request failed";
      callbacks?.onError(message);
    }
  }

  attemptRequest();

  return () => controller.abort();
}
