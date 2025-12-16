from dataclasses import dataclass
from datetime import datetime, UTC
from enum import Enum, auto
from typing import List, Optional


class HealthLevel(Enum):
    OK = auto()
    WARNING = auto()
    ERROR = auto()


class HealthCode(Enum):
    CAMERA_NOT_DETECTED = auto()
    CAMERA_DISCONNECTED = auto()
    UNKNOWN_ERROR = auto()


@dataclass(frozen=True)
class HealthStatus:
    level: HealthLevel
    code: Optional[HealthCode] = None
    message: Optional[str] = None
    instructions: List[str] | None = None
    recoverable: bool = True
    last_updated: datetime = datetime.now(UTC)

    @staticmethod
    def ok() -> "HealthStatus":
        return HealthStatus(level=HealthLevel.OK)

    @staticmethod
    def error(
            *,
            code: HealthCode,
            message: str,
            instructions: List[str],
            recoverable: bool = True,
    ) -> "HealthStatus":
        return HealthStatus(
            level=HealthLevel.ERROR,
            code=code,
            message=message,
            instructions=instructions,
            recoverable=recoverable,
        )

    def to_dict(self) -> dict:
        if self.level == HealthLevel.OK:
            return {"level": "OK"}

        return {
            "level": self.level.name,
            "code": self.code.name if self.code else None,
            "message": self.message,
            "instructions": self.instructions,
            "recoverable": self.recoverable,
        }
