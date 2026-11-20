from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from app.core.base_module import TaskStatus

class SocialConnector(ABC):
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Name of the social platform."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Checks if active API credentials exist in environment or config."""
        pass

    @abstractmethod
    def sync_media(self, max_items: int = 10) -> Dict[str, Any]:
        """
        Fetches accessible media from authorized platform account
        and pushes image bytes/metadata into the shared indexing database.
        """
        pass
