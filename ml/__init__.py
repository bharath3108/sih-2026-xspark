"""Person 2 NLP Pipeline Module.

Provides:
  - mainml: FastAPI-based transformer inference service
  - adapters: Schema conversion for downstream integration
"""

from ml.mainml import (
    app,
    SocialMediaEventRequest,
    SocialMediaEventResponse,
)
from ml.adapterml import NLPAdapter

__all__ = [
    "app",
    "SocialMediaEventRequest",
    "SocialMediaEventResponse",
    "NLPAdapter",
]
