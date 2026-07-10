import type { Message as MessageType } from "../types/chat";
import "./Message.css";

interface MessageProps {
  message: MessageType;
}

/**
 * Renders a single chat message bubble.
 * User messages appear on the right, assistant messages on the left.
 */
export function Message({ message }: MessageProps) {
  const isUser = message.role === "user";
  const sentAt = new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(message.timestamp);

  return (
    <div className={`message ${isUser ? "message--user" : "message--assistant"}`}>
      <div className="message__stack">
        <div className="message__meta">
          <span className="message__label">{isUser ? "YOU" : "NEXUS CORE"}</span>
          <time dateTime={message.timestamp.toISOString()}>{sentAt}</time>
        </div>
        <div className="message__bubble">
          <p className="message__text">{message.content}</p>
        </div>
      </div>
    </div>
  );
}
