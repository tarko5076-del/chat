import { useState, useRef, useEffect } from "react";
import { Message as MessageComponent } from "./Message";
import { ChatInput } from "./ChatInput";
import { sendMessage } from "../services/api";
import type { Message, ChatHistoryMessage } from "../types/chat";

/**
 * Main chat container that holds the message history and manages
 * communication with the backend API.
 */
export function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  /** Auto-scroll to the latest message. */
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(userMessage: string) {
    setError(null);

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: userMessage,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      // Convert current messages to history format (excluding the current user message we just added)
      const history: ChatHistoryMessage[] = messages.map((msg) => ({
        role: msg.role,
        content: msg.content,
      }));

      const responseText = await sendMessage(userMessage, history);

      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: responseText,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const message = err instanceof Error ? err.message : "An unexpected error occurred.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="chat">
      <header className="chat__header">
        <h1 className="chat__title">AI Chatbot</h1>
      </header>

      <div className="chat__messages">
        {messages.length === 0 && (
          <div className="chat__empty">
            <p>Send a message to start chatting with the AI.</p>
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

      <ChatInput onSend={handleSend} disabled={isLoading} />
    </div>
  );
}
