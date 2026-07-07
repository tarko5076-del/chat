import type { Message as MessageType } from "../types/chat";

interface MessageProps {
  message: MessageType;
}

/**
 * Renders a single chat message bubble.
 * User messages appear on the right, assistant messages on the left.
 */
export function Message({ message }: MessageProps) {
  const isUser = message.role === "user";

  return (
    <div className={`message ${isUser ? "message--user" : "message--assistant"}`}>
      <div className="message__avatar">
        {isUser ? "U" : "A"}
      </div>
      <div className="message__bubble">
        <p className="message__text">{message.content}</p>
      </div>
    </div>
  );
}
