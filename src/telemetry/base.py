from abc import ABC, abstractmethod
from typing import Callable, Optional
from ..core.models import ProcessEvent

class BaseTelemetry(ABC):
    @abstractmethod
    def start(self, callback: Callable[[ProcessEvent], None]):
        """Start listening for process events and invoke callback on every detected launch."""
        pass

    @abstractmethod
    def stop(self):
        """Stop telemetry monitoring."""
        pass
