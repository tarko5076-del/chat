import type { Conversation, Message } from "../types/chat";
import "./ChatHistory.css";

interface ChatHistoryProps {
  isOpen: boolean;
  conversations: Conversation[];
  activeConversationId: string;
  activeMessages: Message[];
  onClose: () => void;
  onNewConversation: () => void;
  onSelectConversation: (conversationId: string) => void;
  onDeleteConversation: (conversationId: string) => void;
  onClearAll: () => void;
  onReplay: (message: string) => void;
}

export function ChatHistory({
  isOpen,
  conversations,
  activeConversationId,
  activeMessages,
  onClose,
  onNewConversation,
  onSelectConversation,
  onDeleteConversation,
  onClearAll,
  onReplay,
}: ChatHistoryProps) {
  const entries = activeMessages.slice().reverse();

  function formatConversationDate(date: Date) {
    return new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(date);
  }

  return (
    <>
      <button
        className={`history-backdrop ${isOpen ? "history-backdrop--open" : ""}`}
        type="button"
        aria-label="Close history"
        onClick={onClose}
      />
      <aside className={`history-panel ${isOpen ? "history-panel--open" : ""}`}>
        <div className="history-panel__header">
          <div>
            <p className="history-panel__eyebrow">CHAT LOG</p>
            <h2 className="history-panel__title">History</h2>
          </div>
          <button className="history-panel__close" type="button" onClick={onClose}>
            Close
          </button>
        </div>

        <button className="history-panel__new" type="button" onClick={onNewConversation}>
          New chat
        </button>

        <section className="history-panel__section" aria-label="Conversations">
          <div className="history-panel__section-header">
            <h3>Conversations</h3>
            <span>{conversations.length}</span>
          </div>
          <div className="history-panel__conversation-list">
            {conversations.map((conversation) => (
              <div
                className={`history-panel__conversation ${
                  conversation.id === activeConversationId
                    ? "history-panel__conversation--active"
                    : ""
                }`}
                key={conversation.id}
              >
                <button
                  className="history-panel__conversation-main"
                  type="button"
                  onClick={() => onSelectConversation(conversation.id)}
                >
                  <span className="history-panel__conversation-title">
                    {conversation.title}
                  </span>
                  <span className="history-panel__conversation-meta">
                    {conversation.messages.length} messages -{" "}
                    {formatConversationDate(conversation.updatedAt)}
                  </span>
                </button>
                <button
                  className="history-panel__delete"
                  type="button"
                  aria-label={`Delete ${conversation.title}`}
                  onClick={() => onDeleteConversation(conversation.id)}
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
        </section>

        <section
          className="history-panel__section history-panel__section--messages"
          aria-label="Recent messages"
        >
          <div className="history-panel__section-header">
            <h3>Active chat</h3>
            <span>{activeMessages.length}</span>
          </div>

          <div className="history-panel__list">
            {entries.length === 0 ? (
              <p className="history-panel__empty">No messages yet.</p>
            ) : (
              entries.map((message) => (
                <div
                  className={`history-panel__item history-panel__item--${message.role}`}
                  key={message.id}
                >
                  <span>{message.role === "user" ? "YOU" : "NEXUS"}</span>
                  <p>{message.content}</p>
                  {message.role === "user" && (
                    <button
                      className="history-panel__replay"
                      type="button"
                      onClick={() => onReplay(message.content)}
                    >
                      Resend
                    </button>
                  )}
                </div>
              ))
            )}
          </div>
        </section>

        <button className="history-panel__clear" type="button" onClick={onClearAll}>
          Clear all history
        </button>
      </aside>
    </>
  );
}
