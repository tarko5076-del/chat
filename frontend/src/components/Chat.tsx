import { useState, useRef, useEffect, useCallback } from "react";
import { useAppSelector } from "../hooks";
import { Message as MessageComponent } from "./Message";
import { ChatInput } from "./ChatInput";
import { ChatHistory } from "./ChatHistory";
import { Sidebar } from "./Sidebar";
import { sendMessageStream } from "../services/api";
import type { Conversation, Message, ChatHistoryMessage } from "../types/chat";
import "./Chat.css";
import "./ChatResponsive.css";

const suggestions = [
  "Vegetarian under $15",
  "Book a table for 5",
  "Show today's menu",
  "Split my bill",
];

const legacyStorageKey = "resto-chat-history";
const conversationsStorageKey = "resto-chat-conversations";
const activeConversationStorageKey = "resto-active-conversation";
const maxStoredMessages = 120;

const toolDisplayNames: Record<string, string> = {
  list_menu_items: "Looking up menu",
  manage_reservation: "Checking reservation",
  manage_order: "Managing order",
  calculate_bill: "Calculating bill",
  answer_faq: "Looking up information",
  process_payment: "Processing payment",
};

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
    title:
      typeof candidate.title === "string" && candidate.title.trim() !== ""
        ? candidate.title
        : getConversationTitle(messages),
    messages,
    createdAt: Number.isNaN(createdAt.getTime()) ? new Date() : createdAt,
    updatedAt: Number.isNaN(updatedAt.getTime()) ? new Date() : updatedAt,
  };
}

function loadConversations(): Conversation[] {
  try {
    const saved = localStorage.getItem(conversationsStorageKey);
    if (!saved) {
      return loadLegacyMessages();
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

function loadLegacyMessages(): Conversation[] {
  try {
    const saved = localStorage.getItem(legacyStorageKey);
    if (!saved) {
      return [];
    }

    const parsed = JSON.parse(saved);
    const messages = Array.isArray(parsed)
      ? parsed.map(reviveMessage).filter((message): message is Message => Boolean(message))
      : [];

    return messages.length > 0 ? [createConversation(messages)] : [];
  } catch {
    return [];
  }
}

function initializeChatState(): ChatState {
  const conversations = loadConversations();
  const usableConversations = conversations.length > 0 ? conversations : [createConversation()];
  const savedActiveId = localStorage.getItem(activeConversationStorageKey);
  const hasSavedActive = usableConversations.some(
    (conversation) => conversation.id === savedActiveId,
  );

  return {
    conversations: usableConversations,
    activeConversationId: hasSavedActive && savedActiveId ? savedActiveId : usableConversations[0].id,
  };
}

export function Chat() {
  const [{ conversations, activeConversationId }, setChatState] =
    useState<ChatState>(initializeChatState);
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
  const user = useAppSelector((s) => s.auth.user);
  const activeConversation =
    conversations.find((conversation) => conversation.id === activeConversationId) ??
    conversations[0];
  const messages = activeConversation?.messages ?? [];

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming.content]);

  useEffect(() => {
    const conversationsForStorage = conversations.map((conversation) => ({
      ...conversation,
      messages: conversation.messages.slice(-maxStoredMessages),
    }));
    localStorage.setItem(conversationsStorageKey, JSON.stringify(conversationsForStorage));
    localStorage.setItem(activeConversationStorageKey, activeConversationId);
  }, [activeConversationId, conversations]);

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

    const conversation = createConversation();
    setError(null);
    setStreaming({ isStreaming: false, content: "", status: "", abort: null });
    setChatState({
      conversations: [conversation],
      activeConversationId: conversation.id,
    });
    localStorage.removeItem(legacyStorageKey);
  }

  const handleSend = useCallback(
    function handleSend(userMessage: string) {
      if (!activeConversation) {
        return;
      }

      const conversationId = activeConversation.id;
      const historySource = activeConversation.messages;
      setError(null);
      setIsHistoryOpen(false);

      const userMsg: Message = {
        id: crypto.randomUUID(),
        role: "user",
        content: userMessage,
        timestamp: new Date(),
      };

      updateConversationMessages(conversationId, [...historySource, userMsg]);
      setIsLoading(true);
      setStreaming({ isStreaming: true, content: "", status: "Thinking...", abort: null });

      const history: ChatHistoryMessage[] = historySource.map((msg) => ({
        role: msg.role,
        content: msg.content,
      }));

      const abort = sendMessageStream(userMessage, history, conversationId, {
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
        onDone(response, convId) {
          const assistantMsg: Message = {
            id: crypto.randomUUID(),
            role: "assistant",
            content: response,
            timestamp: new Date(),
          };

          if (convId && convId !== conversationId) {
            setChatState((current) => ({
              ...current,
              activeConversationId: convId,
            }));
          }

          updateConversationMessages(
            convId || conversationId,
            [...historySource, userMsg, assistantMsg],
          );
          setStreaming({ isStreaming: false, content: "", status: "", abort: null });
          setIsLoading(false);
        },
        onError(detail) {
          setError(detail);
          setStreaming({ isStreaming: false, content: "", status: "", abort: null });
          setIsLoading(false);
        },
      });

      setStreaming((prev) => ({ ...prev, abort }));
    },
    [activeConversation],
  );

  const isStreamActive = streaming.isStreaming && streaming.content.length > 0;
  const isStreamThinking = streaming.isStreaming && streaming.content.length === 0;

  return (
    <div className="chat">
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
      <Sidebar open={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} />
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

      <div className="chat__messages">
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
          <MessageComponent key={msg.id} message={msg} />
        ))}

        {isStreamThinking && (
          <div className="message message--assistant">
            <div className="message__stack">
              <div className="message__meta">
                <span className="message__label">RESTO CORE</span>
              </div>
              <div className="message__bubble message__bubble--thinking">
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
          <div className="chat__error">
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
