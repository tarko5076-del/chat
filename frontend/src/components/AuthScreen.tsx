import { useState, type FormEvent } from "react";
import { useAppDispatch } from "../hooks";
import { setCredentials } from "../slices/authSlice";
import { useLoginMutation, useRegisterMutation } from "../services/api";
import "./AuthScreen.css";

export function AuthScreen() {
  const dispatch = useAppDispatch();
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
      } else {
        const result = await login({ email, password }).unwrap();
        dispatch(
          setCredentials({
            access: result.access ?? result.tokens?.access ?? "",
            refresh: result.refresh ?? result.tokens?.refresh,
            user: result.user,
          }),
        );
      }
    } catch (err: unknown) {
      const apiErr = err as { data?: { detail?: string }; error?: string };
      setError(
        apiErr?.data?.detail ?? apiErr?.error ?? "Authentication failed. Please try again.",
      );
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
