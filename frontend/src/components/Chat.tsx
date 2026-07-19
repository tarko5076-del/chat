import { useState, useRef, useEffect, useCallback } from "react";
import { useAppDispatch, useAppSelector } from "../hooks";
import { Message as MessageComponent } from "./Message";
import { ChatInput } from "./ChatInput";
import { ChatHistory } from "./ChatHistory";
import { Sidebar } from "./Sidebar";
import { sendMessageStream, chatApi } from "../services/api";
import { logout } from "../slices/authSlice";
import type { Conversation, Message, ActionRequired } from "../types/chat";
import "./Chat.css";
import "./ChatResponsive.css";

const suggestions = [
  "Vegetarian under $15",
  "Book a table for 5",
  "Show today's menu",
  "Split my bill",
];

const legacyStorageKey = "resto-chat-history";
const maxStoredMessages = 120;

function getStorageKeys(userId: string | null | undefined) {
  if (userId) {
    return {
      conversations: `resto-chat-conversations-${userId}`,
      activeConversation: `resto-active-conversation-${userId}`,
    };
  }
  // Fallback for anonymous users
  return {
    conversations: "resto-chat-conversations-anonymous",
    activeConversation: "resto-active-conversation-anonymous",
  };
}

const toolDisplayNames: Record<string, string> = {
  list_menu_items: "Looking up menu",
  manage_reservation: "Checking reservation",
  manage_order: "Managing order",
  calculate_bill: "Calculating bill",
  answer_faq: "Looking up information",
  process_payment: "Processing payment",
  search_knowledge: "Searching knowledge base",
  request_human_staff: "Contacting staff",
};

interface ChatProps {
  userId: string;
}

interface ChatState {
  conversations: Conversation[];
  activeConversationId: string;
}

interface StreamingState {
  isStreaming: boolean;
  content: string;
  status: string;
  abort: (() => void) | null;
}

function createConversation(messages: Message[] = []): Conversation {
  const now = new Date();
  return {
    id: crypto.randomUUID(),
    sessionId: null,
    title: getConversationTitle(messages),
    messages,
    createdAt: now,
    updatedAt: now,
  };
}

function getConversationTitle(messages: Message[]): string {
  const firstUserMessage = messages.find((message) => message.role === "user");

  if (!firstUserMessage) {
    return "New chat";
  }

  const cleanTitle = firstUserMessage.content.replace(/\s+/g, " ").trim();
  return cleanTitle.length > 44 ? `${cleanTitle.slice(0, 44)}...` : cleanTitle;
}

function reviveMessage(message: unknown): Message | null {
  if (!message || typeof message !== "object") {
    return null;
  }

  const candidate = message as Partial<Message>;

  if (
    (candidate.role !== "user" && candidate.role !== "assistant") ||
    typeof candidate.content !== "string"
  ) {
    return null;
  }

  const timestamp = new Date(candidate.timestamp ?? Date.now());

  return {
    id: typeof candidate.id === "string" ? candidate.id : crypto.randomUUID(),
    role: candidate.role,
    content: candidate.content,
    timestamp: Number.isNaN(timestamp.getTime()) ? new Date() : timestamp,
  };
}

function reviveConversation(conversation: unknown): Conversation | null {
  if (!conversation || typeof conversation !== "object") {
    return null;
  }

  const candidate = conversation as Partial<Conversation>;

  if (typeof candidate.id !== "string") {
    return null;
  }

  const messages = Array.isArray(candidate.messages)
    ? candidate.messages
        .map(reviveMessage)
        .filter((message): message is Message => Boolean(message))
    : [];
  const createdAt = new Date(candidate.createdAt ?? Date.now());
  const updatedAt = new Date(candidate.updatedAt ?? Date.now());

  return {
    id: candidate.id,
    sessionId: typeof candidate.sessionId === "string" ? candidate.sessionId : null,
    title:
      typeof candidate.title === "string" && candidate.title.trim() !== ""
        ? candidate.title
        : getConversationTitle(messages),
    messages,
    createdAt: Number.isNaN(createdAt.getTime()) ? new Date() : createdAt,
    updatedAt: Number.isNaN(updatedAt.getTime()) ? new Date() : updatedAt,
  };
}

function loadConversations(userId: string | null | undefined): Conversation[] {
  try {
    const { conversations: storageKey } = getStorageKeys(userId);
    const saved = localStorage.getItem(storageKey);
    if (!saved) {
      return [];
    }

    const parsed = JSON.parse(saved);
    return Array.isArray(parsed)
      ? parsed
          .map(reviveConversation)
          .filter((conversation): conversation is Conversation => Boolean(conversation))
          .sort((first, second) => second.updatedAt.getTime() - first.updatedAt.getTime())
      : [];
  } catch {
    return [];
  }
}

function initializeChatState(userId: string | null | undefined): ChatState {
  const conversations = loadConversations(userId);
  const usableConversations = conversations.length > 0 ? conversations : [createConversation()];
  const { activeConversation: activeKey } = getStorageKeys(userId);
  const savedActiveId = localStorage.getItem(activeKey);
  const hasSavedActive = usableConversations.some(
    (conversation) => conversation.id === savedActiveId,
  );

  return {
    conversations: usableConversations,
    activeConversationId: hasSavedActive && savedActiveId ? savedActiveId : usableConversations[0].id,
  };
}

export function Chat({ userId }: ChatProps) {
  const dispatch = useAppDispatch();
  const user = useAppSelector((s) => s.auth.user);
  const [{ conversations, activeConversationId }, setChatState] =
    useState<ChatState>({ conversations: [createConversation()], activeConversationId: "" });
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streaming, setStreaming] = useState<StreamingState>({
    isStreaming: false,
    content: "",
    status: "",
    abort: null,
  });
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const pendingActionRef = useRef<ActionRequired | null>(null);
  const activeConversation =
    conversations.find((conversation) => conversation.id === activeConversationId) ??
    conversations[0];
  const messages = activeConversation?.messages ?? [];

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming.content]);

  // Initialize chat state after cleanup
  useEffect(() => {
    // Clear ALL chat-related localStorage keys to prevent data leakage
    const allKeys = Object.keys(localStorage);
    allKeys.forEach(key => {
      if (key.startsWith('resto-chat') || key.startsWith('resto-active-conversation')) {
        localStorage.removeItem(key);
      }
    });
    // Invalidate RTK Query cache to prevent cross-user data leakage
    dispatch(chatApi.util.invalidateTags(['Session', 'Order', 'Reservation']));
    setChatState(initializeChatState(userId));
  }, [userId, dispatch]);

  useEffect(() => {
    const { conversations: conversationsKey, activeConversation: activeKey } = getStorageKeys(userId);
    const conversationsForStorage = conversations.map((conversation) => ({
      ...conversation,
      messages: conversation.messages.slice(-maxStoredMessages),
    }));
    localStorage.setItem(conversationsKey, JSON.stringify(conversationsForStorage));
    localStorage.setItem(activeKey, activeConversationId);
  }, [activeConversationId, conversations, userId]);

  function updateConversationMessages(conversationId: string, nextMessages: Message[]) {
    setChatState((current) => ({
      ...current,
      conversations: current.conversations
        .map((conversation) =>
          conversation.id === conversationId
            ? {
                ...conversation,
                title: getConversationTitle(nextMessages),
                messages: nextMessages,
                updatedAt: new Date(),
              }
            : conversation,
        )
        .sort((first, second) => second.updatedAt.getTime() - first.updatedAt.getTime()),
    }));
  }

  function startNewConversation() {
    const conversation = createConversation();
    setError(null);
    setIsHistoryOpen(false);
    setStreaming({ isStreaming: false, content: "", status: "", abort: null });
    setChatState((current) => ({
      conversations: [conversation, ...current.conversations],
      activeConversationId: conversation.id,
    }));
  }

  function selectConversation(conversationId: string) {
    setError(null);
    setIsHistoryOpen(false);
    setStreaming({ isStreaming: false, content: "", status: "", abort: null });
    setChatState((current) => ({
      ...current,
      activeConversationId: conversationId,
    }));
  }

  function deleteConversation(conversationId: string) {
    setError(null);
    setStreaming({ isStreaming: false, content: "", status: "", abort: null });
    setChatState((current) => {
      const remainingConversations = current.conversations.filter(
        (conversation) => conversation.id !== conversationId,
      );

      if (remainingConversations.length === 0) {
        const conversation = createConversation();
        return {
          conversations: [conversation],
          activeConversationId: conversation.id,
        };
      }

      return {
        conversations: remainingConversations,
        activeConversationId:
          current.activeConversationId === conversationId
            ? remainingConversations[0].id
            : current.activeConversationId,
      };
    });
  }

  function clearAllConversations() {
    const confirmed = window.confirm("Clear every saved conversation?");
    if (!confirmed) {
      return;
    }

    const { conversations: conversationsKey } = getStorageKeys(userId);
    const conversation = createConversation();
    setError(null);
    setStreaming({ isStreaming: false, content: "", status: "", abort: null });
    setChatState({
      conversations: [conversation],
      activeConversationId: conversation.id,
    });
    localStorage.removeItem(legacyStorageKey);
    localStorage.removeItem(conversationsKey);
  }

  function handleSelectSession(sessionId: string) {
    setError(null);
    setIsSidebarOpen(false);
    setStreaming({ isStreaming: false, content: "", status: "", abort: null });

    const existing = conversations.find((c) => c.sessionId === sessionId);
    if (existing) {
      setChatState((current) => ({ ...current, activeConversationId: existing.id }));
      return;
    }

    const conversation = createConversation();
    conversation.sessionId = sessionId;
    setChatState((current) => ({
      conversations: [conversation, ...current.conversations],
      activeConversationId: conversation.id,
    }));
  }

  const handleSend = useCallback(
    function handleSend(userMessage: string) {
      if (!activeConversation) {
        return;
      }

      const conversationId = activeConversation.id;
      const sessionId = activeConversation.sessionId;
      setError(null);
      setIsHistoryOpen(false);
      pendingActionRef.current = null;

      const userMsg: Message = {
        id: crypto.randomUUID(),
        role: "user",
        content: userMessage,
        timestamp: new Date(),
      };

      updateConversationMessages(conversationId, [...activeConversation.messages, userMsg]);
      setIsLoading(true);
      setStreaming({ isStreaming: true, content: "", status: "Thinking...", abort: null });

      const customerId = user?.id?.toString();

      const abort = sendMessageStream(
        userMessage,
        sessionId ?? undefined,
        customerId,
        user?.username,
        {
          onToken(content) {
            setStreaming((prev) => ({
              ...prev,
              content: prev.content + content,
              status: "",
            }));
          },
          onThinking(content) {
            setStreaming((prev) => ({
              ...prev,
              status: content,
            }));
          },
          onToolStart(tool) {
            const displayName = toolDisplayNames[tool] ?? "Processing";
            setStreaming((prev) => ({
              ...prev,
              status: `${displayName}...`,
            }));
          },
          onToolResult(_tool, _success, _message) {
            setStreaming((prev) => ({
              ...prev,
              status: "",
            }));
          },
          onActionRequired(action, description, params) {
            pendingActionRef.current = { action: action as ActionRequired["action"], description, params };
          },
          onSessionId(newSessionId) {
            setChatState((current) => ({
              ...current,
              conversations: current.conversations.map((c) =>
                c.id === conversationId ? { ...c, sessionId: newSessionId } : c,
              ),
            }));
          },
          onDone(response, _convId) {
            const assistantMsg: Message = {
              id: crypto.randomUUID(),
              role: "assistant",
              content: response,
              timestamp: new Date(),
              actionRequired: pendingActionRef.current ?? undefined,
            };
            pendingActionRef.current = null;

            updateConversationMessages(
              conversationId,
              [...activeConversation.messages, userMsg, assistantMsg],
            );
            setStreaming({ isStreaming: false, content: "", status: "", abort: null });
            setIsLoading(false);
          },
          onError(detail) {
            setError(detail);
            setStreaming({ isStreaming: false, content: "", status: "", abort: null });
            setIsLoading(false);
          },
          onAuthExpired() {
            dispatch(logout());
          },
        },
      );

      setStreaming((prev) => ({ ...prev, abort }));
    },
    [activeConversation, user],
  );

  const isStreamActive = streaming.isStreaming && streaming.content.length > 0;
  const isStreamThinking = streaming.isStreaming && streaming.content.length === 0;

  return (
    <div className="chat">
      <a href="#chat-input-field" className="skip-link">
        Skip to chat input
      </a>
      <ChatHistory
        isOpen={isHistoryOpen}
        conversations={conversations}
        activeConversationId={activeConversationId}
        activeMessages={messages}
        onClose={() => setIsHistoryOpen(false)}
        onNewConversation={startNewConversation}
        onSelectConversation={selectConversation}
        onDeleteConversation={deleteConversation}
        onClearAll={clearAllConversations}
        onReplay={handleSend}
      />
      <Sidebar
        open={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        onSelectSession={handleSelectSession}
        activeSessionId={activeConversation?.sessionId ?? undefined}
      />
      <header className="chat__header">
        <button
          className="chat__icon-button"
          type="button"
          aria-label="Open history"
          onClick={() => setIsHistoryOpen(true)}
        >
          <span className="chat__hamburger" aria-hidden="true"></span>
        </button>
        <div className={`chat__brand-mark ${isLoading ? "chat__brand-mark--thinking" : ""}`} aria-hidden="true"></div>
        <h1 className="chat__title">Resto AI</h1>
        <button
          className="chat__icon-button chat__avatar-button"
          type="button"
          aria-label="Open menu & orders"
          onClick={() => setIsSidebarOpen(true)}
          title={user?.username ?? "Menu"}
        >
          <span className="chat__avatar-initial">{user?.username?.[0]?.toUpperCase() ?? "?"}</span>
        </button>
      </header>

      <div className="chat__messages" role="log" aria-label="Chat messages" aria-live="polite">
        {messages.length === 0 && !isStreamActive && !isStreamThinking && (
          <div className="chat__welcome">
            <div className="chat__welcome-label">RESTO CORE</div>
            <div className="chat__welcome-bubble">
              Hello. I can help with menu recommendations, reservations, orders,
              bills, and restaurant questions.
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <MessageComponent
            key={msg.id}
            message={msg}
          />
        ))}

        {isStreamThinking && (
          <div className="message message--assistant">
            <div className="message__stack">
              <div className="message__meta">
                <span className="message__label">RESTO CORE</span>
              </div>
              <div className="message__bubble message__bubble--thinking" role="status" aria-label="Assistant is typing">
                <div className="chat__typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                {streaming.status && (
                  <div className="message__status">{streaming.status}</div>
                )}
              </div>
            </div>
          </div>
        )}

        {isStreamActive && (
          <div className="message message--assistant">
            <div className="message__stack">
              <div className="message__meta">
                <span className="message__label">RESTO CORE</span>
                <time>now</time>
              </div>
              <div className="message__bubble">
                <p className="message__text">{streaming.content}</p>
                {streaming.status && (
                  <div className="message__status message__status--inline">
                    {streaming.status}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="chat__error" role="alert">
            <p>{error}</p>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="chat__suggestions" aria-label="Suggested prompts">
        {suggestions.map((suggestion) => (
          <button
            className="chat__chip"
            key={suggestion}
            type="button"
            disabled={isLoading}
            onClick={() => handleSend(suggestion)}
          >
            {suggestion}
          </button>
        ))}
      </div>

      <ChatInput onSend={handleSend} disabled={isLoading} />
    </div>
  );
}
