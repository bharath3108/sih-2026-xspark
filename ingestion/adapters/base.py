from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from contracts.canonical_event import CanonicalEvent

class SourceAdapter(ABC):
    
    @abstractmethod
    def source_name(self) -> str:
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def fetch(self, query: str, limit: int = 100) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def normalize(self, raw_post: Dict[str, Any]) -> CanonicalEvent:
        pass