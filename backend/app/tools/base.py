from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import json
from typing import Any


@dataclass
class ToolResult:
    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    memory_updates: dict[str, Any] = field(default_factory=dict)
    next_action: str | None = None

    def to_text(self) -> str:
        return self.message

    def to_llm_content(self) -> str:
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
    name: str = ""
    description: str = ""
    parameters: dict = {}

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        ...

    def to_openai_tool(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
