import type { ActionRequired } from "../types/chat";
import "./ActionButtons.css";

interface ActionButtonsProps {
  action: ActionRequired;
  onSend: (message: string) => void;
  disabled?: boolean;
}

export function ActionButtons({ action, onSend, disabled }: ActionButtonsProps) {
  if (action.action === "confirm_order") {
    return (
      <div className="action-buttons">
        <button
          className="action-buttons__btn action-buttons__btn--confirm"
          disabled={disabled}
          onClick={() => onSend("Yes, place the order.")}
        >
          Place Order
        </button>
        <button
          className="action-buttons__btn action-buttons__btn--cancel"
          disabled={disabled}
          onClick={() => onSend("No, cancel the order.")}
        >
          Cancel
        </button>
      </div>
    );
  }

  if (action.action === "confirm_payment") {
    const checkoutUrl = action.params.checkout_url as string | undefined;
    const method = (action.params.payment_method as string) ?? "chapa";

    if (checkoutUrl) {
      return (
        <div className="action-buttons">
          <button
            className="action-buttons__btn action-buttons__btn--pay"
            onClick={() => window.open(checkoutUrl, "_blank", "noopener,noreferrer")}
          >
            Pay Now
          </button>
          <button
            className="action-buttons__btn action-buttons__btn--cancel"
            disabled={disabled}
            onClick={() => onSend("Cancel the payment.")}
          >
            Cancel
          </button>
        </div>
      );
    }

    return (
      <div className="action-buttons">
        <button
          className="action-buttons__btn action-buttons__btn--confirm"
          disabled={disabled}
          onClick={() => onSend(`Yes, confirm payment with ${method}.`)}
        >
          Confirm Payment
        </button>
        <button
          className="action-buttons__btn action-buttons__btn--cancel"
          disabled={disabled}
          onClick={() => onSend("No, I'll pay differently.")}
        >
          Change Method
        </button>
      </div>
    );
  }

  if (action.action === "confirm_reservation") {
    return (
      <div className="action-buttons">
        <button
          className="action-buttons__btn action-buttons__btn--confirm"
          disabled={disabled}
          onClick={() => onSend("Yes, confirm the reservation.")}
        >
          Confirm Table
        </button>
        <button
          className="action-buttons__btn action-buttons__btn--cancel"
          disabled={disabled}
          onClick={() => onSend("No, cancel the reservation.")}
        >
          Cancel
        </button>
      </div>
    );
  }

  return null;
}
