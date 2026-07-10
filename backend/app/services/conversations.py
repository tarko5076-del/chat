import json
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.agent.memory import ConversationMemory
from app.models.conversation import Conversation, ConversationMessage


class ConversationStore:
    def get_or_create(self, db: Session, conversation_id: str | None) -> Conversation:
        if conversation_id:
            conversation = db.get(Conversation, conversation_id)
            if conversation:
                return conversation

        conversation = Conversation(id=conversation_id or str(uuid4()))
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return conversation

    def import_history(
        self,
        db: Session,
        conversation: Conversation,
        history: list[dict],
    ) -> None:
        if self.has_messages(db, conversation.id):
            return
        for item in history:
            role = item.get("role")
            content = item.get("content")
            if role in {"user", "assistant"} and isinstance(content, str) and content:
                db.add(
                    ConversationMessage(
                        conversation_id=conversation.id,
                        role=role,
                        content=content,
                    )
                )
        conversation.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(conversation)

    def append_message(
        self,
        db: Session,
        conversation: Conversation,
        role: str,
        content: str,
    ) -> None:
        db.add(
            ConversationMessage(
                conversation_id=conversation.id,
                role=role,
                content=content,
            )
        )
        if role == "user" and conversation.title == "New chat":
            conversation.title = self._title_from_content(content)
        conversation.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(conversation)

    def has_messages(self, db: Session, conversation_id: str) -> bool:
        return (
            db.query(ConversationMessage.id)
            .filter(ConversationMessage.conversation_id == conversation_id)
            .first()
            is not None
        )

    def history(
        self,
        db: Session,
        conversation: Conversation,
        limit: int = 30,
    ) -> list[dict[str, str]]:
        messages = (
            db.query(ConversationMessage)
            .filter(ConversationMessage.conversation_id == conversation.id)
            .order_by(ConversationMessage.created_at.desc(), ConversationMessage.id.desc())
            .limit(limit)
            .all()
        )
        messages.reverse()
        return [{"role": message.role, "content": message.content} for message in messages]

    def memory(self, db: Session, conversation: Conversation) -> ConversationMemory:
        state = {
            "customer_id": conversation.customer_id,
            "customer_name": conversation.customer_name,
            "phone": conversation.phone,
            "email": conversation.email,
            "reservation_id": conversation.reservation_id,
            "reservation_date": conversation.reservation_date,
            "reservation_time": conversation.reservation_time,
            "party_size": conversation.party_size,
            "order_id": conversation.order_id,
            "order_state": self._loads(conversation.order_state),
            "order_status": conversation.order_status,
            "payment_method": conversation.payment_method,
            "payment_status": conversation.payment_status,
            "payment_id": conversation.payment_id,
        }
        memory = ConversationMemory.from_state(state)
        messages = (
            db.query(ConversationMessage)
            .filter(ConversationMessage.conversation_id == conversation.id)
            .order_by(ConversationMessage.created_at, ConversationMessage.id)
            .all()
        )
        for message in messages:
            memory.remember_message(message.content)
        return memory

    def update_memory(
        self,
        db: Session,
        conversation: Conversation,
        memory: ConversationMemory,
    ) -> None:
        state = memory.to_state()
        conversation.customer_name = state["customer_name"]
        conversation.customer_id = state["customer_id"]
        conversation.phone = state["phone"]
        conversation.email = state["email"]
        conversation.reservation_id = state["reservation_id"]
        conversation.reservation_date = state["reservation_date"]
        conversation.reservation_time = state["reservation_time"]
        conversation.party_size = state["party_size"]
        conversation.order_id = state["order_id"]
        conversation.order_state = self._dumps(state["order_state"])
        conversation.order_status = state["order_status"]
        conversation.payment_method = state["payment_method"]
        conversation.payment_status = state["payment_status"]
        conversation.payment_id = state["payment_id"]
        conversation.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(conversation)

    def _title_from_content(self, content: str) -> str:
        clean = " ".join(content.split())
        return f"{clean[:57]}..." if len(clean) > 60 else clean

    def _loads(self, value: str | None) -> dict:
        if not value:
            return {"items": []}
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {"items": []}
        return parsed if isinstance(parsed, dict) else {"items": []}

    def _dumps(self, value: dict | None) -> str:
        return json.dumps(value or {"items": []})


conversation_store = ConversationStore()
