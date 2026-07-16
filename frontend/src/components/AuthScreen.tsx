import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAppDispatch } from "../hooks";
import { setCredentials } from "../slices/authSlice";
import { useLoginMutation, useRegisterMutation } from "../services/api";
import "./AuthScreen.css";

/**
 * Extract a human-readable error message from a DRF error response.
 * Handles multiple response shapes:
 *   { "detail": "..." }                       — single message
 *   { "field": ["err1", "err2"] }            — field-level
 *   { "non_field_errors": ["..."] }           — non-field errors
 *   { "error": "..." }                        — generic error string
 */
function extractErrorMessage(err: unknown): string {
  if (!err || typeof err !== "object") return "Authentication failed. Please try again.";

  const apiErr = err as Record<string, unknown>;
  const data = apiErr["data"] as Record<string, unknown> | undefined;

  // 1) drf detail message (e.g. LoginView returning 401)
  if (data && typeof data["detail"] === "string") {
    return data["detail"];
  }

  // 2) drf non_field_errors (e.g. model-level validation)
  if (
    data &&
    Array.isArray(data["non_field_errors"]) &&
    (data["non_field_errors"] as string[]).length > 0
  ) {
    return (data["non_field_errors"] as string[])[0];
  }

  // 3) drf field-level validation errors
  if (data && typeof data === "object" && !Array.isArray(data)) {
    const fieldEntries = Object.entries(data).filter(
      ([key]) => key !== "detail" && key !== "non_field_errors",
    );
    if (fieldEntries.length > 0) {
      const messages: string[] = [];
      for (const [field, msgs] of fieldEntries) {
        if (Array.isArray(msgs) && msgs.length > 0) {
          messages.push(`${field}: ${msgs[0]}`);
        }
      }
      if (messages.length > 0) return messages.join("; ");
    }
  }

  // 4) plain error string (network error, etc.)
  if (typeof apiErr["error"] === "string") {
    return apiErr["error"];
  }

  return "Authentication failed. Please try again.";
}

export function AuthScreen() {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState<string | null>(null);

  const [login, { isLoading: isLoginLoading }] = useLoginMutation();
  const [register, { isLoading: isRegisterLoading }] = useRegisterMutation();
  const isLoading = isLoginLoading || isRegisterLoading;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);

    try {
      if (isRegister) {
        const result = await register({
          username,
          email,
          password,
          phone: phone || undefined,
        }).unwrap();
        dispatch(
          setCredentials({
            access: result.access ?? result.tokens?.access ?? "",
            refresh: result.refresh ?? result.tokens?.refresh,
            user: result.user,
          }),
        );
        navigate("/", { replace: true });
      } else {
        const result = await login({ email, password }).unwrap();
        dispatch(
          setCredentials({
            access: result.access ?? result.tokens?.access ?? "",
            refresh: result.refresh ?? result.tokens?.refresh,
            user: result.user,
          }),
        );
        navigate("/", { replace: true });
      }
    } catch (err: unknown) {
      setError(extractErrorMessage(err));
    }
  }

  return (
    <div className="auth">
      <div className="auth__card">
        <div className="auth__brand">
          <div className="auth__brand-mark" aria-hidden="true" />
          <h1 className="auth__title">Resto AI</h1>
          <p className="auth__subtitle">
            {isRegister ? "Create your account" : "Sign in to continue"}
          </p>
        </div>

        <form className="auth__form" onSubmit={handleSubmit}>
          {isRegister && (
            <label className="auth__field">
              <span className="auth__label">Username</span>
              <input
                className="auth__input"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Your name"
                required
                autoFocus
              />
            </label>
          )}

          <label className="auth__field">
            <span className="auth__label">Email</span>
            <input
              className="auth__input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              autoFocus={!isRegister}
            />
          </label>

          <label className="auth__field">
            <span className="auth__label">Password</span>
            <input
              className="auth__input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Min 8 characters"
              required
              minLength={8}
            />
          </label>

          {isRegister && (
            <label className="auth__field">
              <span className="auth__label">Phone (optional)</span>
              <input
                className="auth__input"
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+1234567890"
              />
            </label>
          )}

          {error && <div className="auth__error">{error}</div>}

          <button className="auth__submit" type="submit" disabled={isLoading}>
            {isLoading
              ? "Please wait..."
              : isRegister
                ? "Create account"
                : "Sign in"}
          </button>
        </form>

        <button
          className="auth__toggle"
          type="button"
          onClick={() => {
            setIsRegister(!isRegister);
            setError(null);
          }}
          disabled={isLoading}
        >
          {isRegister
            ? "Already have an account? Sign in"
            : "Don't have an account? Create one"}
        </button>
      </div>
    </div>
  );
}
