import os
from pathlib import Path

from dotenv import load_dotenv

dotenv_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=dotenv_path)


TAX_RATE: float = 0.0825
DELIVERY_FEE: float = 4.99
MAX_RESERVATIONS_PER_SLOT: int = 10
MAX_PARTY_SIZE: int = 12
OPENING_HOUR: int = 11
CLOSING_HOUR: int = 22
MAX_HISTORY_MESSAGES: int = 12
MAX_MENU_ITEMS: int = 8


class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "")
    hf_token: str = os.getenv("HF_TOKEN", "")
    hf_model: str = os.getenv("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
    hf_base_url: str = os.getenv("HF_BASE_URL", "https://router.huggingface.co/v1")
    app_name: str = "Restaurant AI Assistant"
    restaurant_payment_phone: str = os.getenv("RESTAURANT_PAYMENT_PHONE", "+254 700 123 456")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    cors_origins: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if origin.strip()
    ]
    database_url: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{Path(__file__).resolve().parent.parent.parent / 'restaurant.db'}",
    )

    @property
    def sqlalchemy_database_url(self) -> str:
        """Return a SQLAlchemy 2 compatible database URL.

        PostgreSQL deployments sometimes provide postgres:// URLs. SQLAlchemy
        expects postgresql+psycopg:// when using the psycopg v3 driver.
        """
        if self.database_url.startswith("postgres://"):
            return self.database_url.replace("postgres://", "postgresql+psycopg://", 1)
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.database_url

    @property
    def using_postgres(self) -> bool:
        return self.sqlalchemy_database_url.startswith("postgresql")

    @property
    def llm_api_key(self) -> str:
        return self.openai_api_key or self.hf_token

    @property
    def llm_model(self) -> str:
        return self.openai_model if self.openai_api_key else self.hf_model

    @property
    def llm_base_url(self) -> str | None:
        if self.openai_base_url:
            return self.openai_base_url
        return self.hf_base_url if self.hf_token and not self.openai_api_key else None


settings = Settings()
