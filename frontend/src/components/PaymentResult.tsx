import { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useGetPaymentsQuery } from "../services/api";
import "./PaymentResult.css";

type PaymentStatus = "checking" | "completed" | "failed" | "error";

export function PaymentResult() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const txRef = searchParams.get("tx_ref") ?? searchParams.get("reference");

  const [status, setStatus] = useState<PaymentStatus>("checking");
  const [attempts, setAttempts] = useState(0);
  const MAX_ATTEMPTS = 30;
  const POLL_INTERVAL = 3000;

  const { data: payments } = useGetPaymentsQuery(
    txRef ? { status: undefined } : undefined,
    { skip: !txRef },
  );

  useEffect(() => {
    if (!txRef) {
      setStatus("error");
      return;
    }

    const interval = setInterval(async () => {
      setAttempts((prev) => {
        if (prev >= MAX_ATTEMPTS) {
          clearInterval(interval);
          return prev;
        }
        return prev + 1;
      });

      try {
        const token = localStorage.getItem("access_token");
        const headers: Record<string, string> = {};
        if (token) headers["Authorization"] = `Bearer ${token}`;

        const res = await fetch(`/api/payments/?tx_ref=${txRef}`, { headers });
        if (!res.ok) return;

        const data = await res.json();
        const payment = data.results?.[0];
        if (!payment) return;

        if (payment.status === "completed") {
          setStatus("completed");
          clearInterval(interval);
        } else if (payment.status === "failed") {
          setStatus("failed");
          clearInterval(interval);
        }
      } catch {
        // retry on network error
      }
    }, POLL_INTERVAL);

    return () => clearInterval(interval);
  }, [txRef]);

  if (!txRef) {
    return (
      <div className="payment-result">
        <div className="payment-result__card payment-result__card--error">
          <h2>Invalid Payment Link</h2>
          <p>No payment reference found. Please return to the chat and try again.</p>
          <button className="payment-result__btn" onClick={() => navigate("/")}>
            Back to Chat
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="payment-result" role="main" aria-label="Payment result">
      <div className={`payment-result__card payment-result__card--${status}`} role="status" aria-live="polite">
        {status === "checking" && (
          <>
            <div className="payment-result__spinner" aria-hidden="true" />
            <h2>Verifying Payment...</h2>
            <p>Reference: {txRef}</p>
            <p className="payment-result__muted">
              Please wait while we confirm your payment. This may take a moment.
            </p>
            {attempts > 5 && (
              <p className="payment-result__muted">
                Taking longer than usual... ({attempts}/{MAX_ATTEMPTS})
              </p>
            )}
          </>
        )}

        {status === "completed" && (
          <>
            <div className="payment-result__icon" aria-hidden="true">&#10003;</div>
            <h2>Payment Successful</h2>
            <p>Your payment has been confirmed.</p>
            <p className="payment-result__muted">Reference: {txRef}</p>
            <button className="payment-result__btn payment-result__btn--success" onClick={() => navigate("/")}>
              Back to Chat
            </button>
          </>
        )}

        {status === "failed" && (
          <>
            <div className="payment-result__icon payment-result__icon--fail" aria-hidden="true">&#10007;</div>
            <h2>Payment Failed</h2>
            <p>Your payment could not be processed.</p>
            <p className="payment-result__muted">Reference: {txRef}</p>
            <button className="payment-result__btn" onClick={() => navigate("/")}>
              Back to Chat
            </button>
          </>
        )}

        {status === "error" && (
          <>
            <div className="payment-result__icon payment-result__icon--fail" aria-hidden="true">&#10007;</div>
            <h2>Something Went Wrong</h2>
            <p>Could not verify your payment. Please contact support.</p>
            <button className="payment-result__btn" onClick={() => navigate("/")}>
              Back to Chat
            </button>
          </>
        )}
      </div>
    </div>
  );
}
