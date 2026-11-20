from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from enum import Enum
from pydantic import BaseModel, Field

class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"

class ModuleResult(BaseModel):
    module_name: str
    status: TaskStatus
    result: Dict[str, Any] = Field(default_factory=dict)
    evidence_found: bool = False
    confidence: Optional[float] = None
    execution_time_ms: float = 0.0
    error_message: Optional[str] = None
    limitations: List[str] = Field(default_factory=list)

class ForensicModule(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier of the module."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name for dashboard display."""
        pass

    @abstractmethod
    def analyze(self, image_path: str, context: Dict[str, Any]) -> ModuleResult:
        """Execute real analysis on the given image path."""
        pass
