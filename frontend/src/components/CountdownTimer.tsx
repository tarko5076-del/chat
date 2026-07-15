import { useState, useEffect } from "react";
import "./CountdownTimer.css";

interface CountdownTimerProps {
  expiresAt: string | Date;
  onExpired?: () => void;
}

export function CountdownTimer({ expiresAt, onExpired }: CountdownTimerProps) {
  const [remaining, setRemaining] = useState(0);

  useEffect(() => {
    const target = new Date(expiresAt).getTime();

    function tick() {
      const now = Date.now();
      const diff = Math.max(0, Math.floor((target - now) / 1000));
      setRemaining(diff);
      if (diff === 0) {
        onExpired?.();
      }
    }

    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [expiresAt, onExpired]);

  if (remaining <= 0) {
    return <span className="countdown countdown--expired" role="status">Expired</span>;
  }

  const minutes = Math.floor(remaining / 60);
  const seconds = remaining % 60;
  const isUrgent = remaining <= 180;

  return (
    <span className={`countdown ${isUrgent ? "countdown--urgent" : ""}`} role="timer" aria-live="polite" aria-label={`${minutes} minutes ${seconds} seconds remaining`}>
      {minutes}:{seconds.toString().padStart(2, "0")}
    </span>
  );
}
