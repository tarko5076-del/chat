import { Component, type ReactNode } from "react";
import "./ErrorBoundary.css";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info.componentStack);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  handleClearAndReset = () => {
    try {
      localStorage.removeItem("resto-chat-conversations");
      localStorage.removeItem("resto-active-conversation");
      localStorage.removeItem("resto-chat-history");
    } catch {
      // ignore
    }
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary" role="alert" aria-label="Application error">
          <div className="error-boundary__card">
            <div className="error-boundary__icon" aria-hidden="true">&#9888;</div>
            <h1>Something went wrong</h1>
            <p className="error-boundary__message">
              {this.state.error?.message ?? "An unexpected error occurred."}
            </p>
            <div className="error-boundary__actions">
              <button className="error-boundary__btn" onClick={this.handleReset}>
                Try Again
              </button>
              <button
                className="error-boundary__btn error-boundary__btn--secondary"
                onClick={this.handleClearAndReset}
              >
                Clear Data & Reload
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
