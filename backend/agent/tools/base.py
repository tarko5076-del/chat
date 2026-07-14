from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import json

TAX_RATE = 0.0825
DELIVERY_FEE = 4.99


@dataclass
class ToolResult:
    success: bool
    message: str
    data: dict = field(default_factory=dict)
    missing_fields: list = field(default_factory=list)
    memory_updates: dict = field(default_factory=dict)
    next_action: str | None = None

    def to_text(self):
        return self.message

    def to_llm_content(self):
        return json.dumps(
            {
                "success": self.success,
                "message": self.message,
                "data": self.data,
                "missing_fields": self.missing_fields,
                "memory_updates": self.memory_updates,
                "next_action": self.next_action,
            },
            default=str,
        )


class BaseTool(ABC):
    name = ""
    description = ""
    parameters = {}

    @abstractmethod
    def execute(self, **kwargs):
        ...

    def to_openai_tool(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
