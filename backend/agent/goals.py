from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class GoalStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Goal:
    description: str
    priority: int = 0
    status: GoalStatus = GoalStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    result: str | None = None
    blocked_by: str | None = None

    def complete(self, result: str = "") -> None:
        self.status = GoalStatus.COMPLETED
        self.result = result
        self.completed_at = datetime.now(timezone.utc)

    def fail(self, reason: str = "") -> None:
        self.status = GoalStatus.FAILED
        self.result = reason
        self.completed_at = datetime.now(timezone.utc)

    def start(self) -> None:
        self.status = GoalStatus.IN_PROGRESS

    def __str__(self) -> str:
        icon = {
            GoalStatus.PENDING: "[ ]",
            GoalStatus.IN_PROGRESS: "[>]",
            GoalStatus.COMPLETED: "[x]",
            GoalStatus.FAILED: "[!]",
        }[self.status]
        return f"{icon} {self.description}"


class GoalStack:
    """Manages a prioritized stack of goals the agent is working toward.

    Goals are processed in priority order (highest first), with FIFO
    breaking ties. The agent completes one goal before moving to the next.
    """

    def __init__(self) -> None:
        self._goals: list[Goal] = []

    def push(self, description: str, priority: int = 0) -> Goal:
        goal = Goal(description=description, priority=priority)
        self._goals.append(goal)
        logger.info("Goal pushed: %s", goal)
        return goal

    def current(self) -> Goal | None:
        for goal in self._goals:
            if goal.status in (GoalStatus.PENDING, GoalStatus.IN_PROGRESS):
                return goal
        return None

    def complete_current(self, result: str = "") -> Goal | None:
        goal = self.current()
        if goal:
            goal.complete(result)
            logger.info("Goal completed: %s", goal)
        return goal

    def fail_current(self, reason: str = "") -> Goal | None:
        goal = self.current()
        if goal:
            goal.fail(reason)
            logger.info("Goal failed: %s", goal)
        return goal

    def all_completed(self) -> bool:
        return all(
            g.status in (GoalStatus.COMPLETED, GoalStatus.FAILED)
            for g in self._goals
        )

    def as_context(self) -> str:
        if not self._goals:
            return "No active goals."
        lines = [f"  {i + 1}. {g}" for i, g in enumerate(self._goals)]
        return "Goal stack:\n" + "\n".join(lines)

    def as_dicts(self) -> list[dict[str, str]]:
        return [
            {
                "description": g.description,
                "status": g.status.value,
                "priority": str(g.priority),
                "result": g.result or "",
            }
            for g in self._goals
        ]

    def __len__(self) -> int:
        return len(self._goals)

    def __iter__(self):
        return iter(self._goals)
