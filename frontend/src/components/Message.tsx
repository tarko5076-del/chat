import type { Message as MessageType } from "../types/chat";
import { ActionButtons } from "./ActionButtons";
import "./Message.css";

interface MessageProps {
  message: MessageType;
  onSend?: (message: string) => void;
  streaming?: boolean;
}

export function Message({ message, onSend, streaming }: MessageProps) {
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
        {!isUser && message.actionRequired && onSend && (
          <ActionButtons
            action={message.actionRequired}
            onSend={onSend}
            disabled={streaming}
          />
        )}
      </div>
    </div>
  );
}
