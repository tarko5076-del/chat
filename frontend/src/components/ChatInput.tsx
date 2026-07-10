import { useState, type FormEvent } from "react";
import "./ChatInput.css";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled: boolean;
}

/**
 * Text input and send button for composing chat messages.
 */
export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [inputValue, setInputValue] = useState("");

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = inputValue.trim();
    if (trimmed === "" || disabled) {
      return;
    }
    onSend(trimmed);
    setInputValue("");
  }

  return (
    <form className="chat-input" onSubmit={handleSubmit}>
      <input
        className="chat-input__field"
        type="text"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        placeholder="Ask about menus, reservations, or bills"
        disabled={disabled}
        autoFocus
      />
      <button
        className="chat-input__button"
        type="submit"
        disabled={disabled || inputValue.trim() === ""}
      >
        <span aria-hidden="true"></span>
      </button>
    </form>
  );
}
