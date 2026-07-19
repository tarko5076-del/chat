import logging
from dataclasses import dataclass

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

CHAPA_API_BASE = "https://api.chapa.co/v1"


@dataclass
class ChapaInitResponse:
    success: bool
    checkout_url: str | None = None
    tx_ref: str | None = None
    error: str | None = None


@dataclass
class ChapaVerifyResponse:
    success: bool
    status: str | None = None
    amount: float | None = None
    currency: str | None = None
    tx_ref: str | None = None
    error: str | None = None


class ChapaClient:
    def __init__(self) -> None:
        self.secret_key = getattr(settings, "CHAPA_SECRET_KEY", "")
        self.enabled = bool(self.secret_key)
        self.demo_mode = not self.enabled and getattr(settings, "PAYMENT_DEMO_MODE", True)
        self.base_url = CHAPA_API_BASE

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    def initialize_payment(
        self,
        amount: float,
        email: str,
        first_name: str,
        last_name: str,
        tx_ref: str,
        callback_url: str,
        return_url: str = "",
        currency: str = "ETB",
        description: str = "Restaurant payment",
    ) -> ChapaInitResponse:
        if not self.enabled:
            if self.demo_mode:
                logger.info(
                    "chapa_demo tx_ref=%s amount=%.2f currency=%s status=simulated",
                    tx_ref, amount, currency,
                )
                return ChapaInitResponse(
                    success=True,
                    checkout_url=f"https://demo.chapa.co/checkout/{tx_ref}",
                    tx_ref=tx_ref,
                )
            return ChapaInitResponse(
                success=False,
                error="Chapa secret key not configured. Set CHAPA_SECRET_KEY or enable PAYMENT_DEMO_MODE.",
            )

        payload = {
            "amount": str(amount),
            "currency": currency,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "tx_ref": tx_ref,
            "callback_url": callback_url,
            "description": description,
        }
        if return_url:
            payload["return_url"] = return_url

        try:
            response = httpx.post(
                f"{self.base_url}/transaction/initialize",
                json=payload,
                headers=self._headers(),
                timeout=30,
            )
            data = response.json()

            if response.status_code == 200 and data.get("status") == "success":
                logger.info("chapa_init tx_ref=%s amount=%.2f currency=%s status=success", tx_ref, amount, currency)
                return ChapaInitResponse(
                    success=True,
                    checkout_url=data["data"]["checkout_url"],
                    tx_ref=tx_ref,
                )
            else:
                error_msg = data.get("message", "Unknown error")
                logger.error("Chapa init failed: %s", error_msg)
                return ChapaInitResponse(success=False, error=error_msg)

        except httpx.HTTPError as exc:
            logger.error("Chapa HTTP error: %s", exc)
            return ChapaInitResponse(success=False, error=str(exc))

    def verify_payment(self, tx_ref: str) -> ChapaVerifyResponse:
        if not self.enabled:
            if self.demo_mode:
                logger.info("chapa_demo_verify tx_ref=%s status=success (simulated)", tx_ref)
                return ChapaVerifyResponse(
                    success=True,
                    status="success",
                )
            return ChapaVerifyResponse(
                success=False,
                error="Chapa secret key not configured.",
            )

        try:
            response = httpx.get(
                f"{self.base_url}/transaction/verify/{tx_ref}",
                headers=self._headers(),
                timeout=30,
            )
            data = response.json()

            if response.status_code == 200 and data.get("status") == "success":
                tx_data = data.get("data", {})
                logger.info("chapa_verify tx_ref=%s status=%s amount=%.2f", tx_ref, tx_data.get("status"), float(tx_data.get("amount", 0)))
                return ChapaVerifyResponse(
                    success=True,
                    status=tx_data.get("status"),
                    amount=float(tx_data.get("amount", 0)),
                    currency=tx_data.get("currency"),
                    tx_ref=tx_data.get("tx_ref"),
                )
            else:
                error_msg = data.get("message", "Verification failed")
                return ChapaVerifyResponse(success=False, error=error_msg)

        except httpx.HTTPError as exc:
            logger.error("Chapa verify error: %s", exc)
            return ChapaVerifyResponse(success=False, error=str(exc))


chapa_client = ChapaClient()
