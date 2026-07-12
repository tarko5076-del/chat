import { useState, useRef, useEffect } from "react";
import { Message as MessageComponent } from "./Message";
import { ChatInput } from "./ChatInput";
import { ChatHistory } from "./ChatHistory";
import { sendMessage } from "../services/api";
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

interface ChatState {
  conversations: Conversation[];
  activeConversationId: string;
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

/**
 * Main chat container that holds the message history and manages
 * communication with the backend API.
 */
export function Chat() {
  const [{ conversations, activeConversationId }, setChatState] =
    useState<ChatState>(initializeChatState);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const activeConversation =
    conversations.find((conversation) => conversation.id === activeConversationId) ??
    conversations[0];
  const messages = activeConversation?.messages ?? [];

  /** Auto-scroll to the latest message. */
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

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
    setChatState((current) => ({
      conversations: [conversation, ...current.conversations],
      activeConversationId: conversation.id,
    }));
  }

  function selectConversation(conversationId: string) {
    setError(null);
    setIsHistoryOpen(false);
    setChatState((current) => ({
      ...current,
      activeConversationId: conversationId,
    }));
  }

  function clearCurrentConversation() {
    if (!activeConversation) {
      return;
    }

    setError(null);
    updateConversationMessages(activeConversation.id, []);
  }

  function deleteConversation(conversationId: string) {
    setError(null);
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
    setChatState({
      conversations: [conversation],
      activeConversationId: conversation.id,
    });
    localStorage.removeItem(legacyStorageKey);
  }

  async function handleSend(userMessage: string) {
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

    try {
      const history: ChatHistoryMessage[] = historySource.map((msg) => ({
        role: msg.role,
        content: msg.content,
      }));

      const response = await sendMessage(userMessage, history, conversationId);

      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: response.response,
        timestamp: new Date(),
      };

      updateConversationMessages(conversationId, [...historySource, userMsg, assistantMsg]);
    } catch (err) {
      const message = err instanceof Error ? err.message : "An unexpected error occurred.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }

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
          className="chat__icon-button"
          type="button"
          aria-label="Clear chat"
          onClick={clearCurrentConversation}
          disabled={messages.length === 0}
        >
          <span className="chat__kebab" aria-hidden="true"></span>
        </button>
      </header>

      <div className="chat__messages">
        {messages.length === 0 && (
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

        {isLoading && (
          <div className="chat__loading">
            <div className="chat__typing-indicator">
              <span></span>
              <span></span>
              <span></span>
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
