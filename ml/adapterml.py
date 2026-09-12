"""Adapter layer: Convert between mainml.py and downstream SectionD pipeline schemas.

This module handles bidirectional conversion between:
  - SocialMediaEventRequest (mainml.py input)
  - NLPOutputContract (downstream pipeline input)
  - SocialMediaEventResponse (mainml.py output)
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
from uuid import UUID

from ml.mainml import (
    SocialMediaEventRequest,
    SocialMediaEventResponse,
    Engagement,
    Metadata
)
from src.contracts.nlp_input import (
    NLPOutputContract,
    Platform,
    SentimentBlock,
    MetricsBlock
)


class NLPAdapter:
    """
    Bidirectional adapter between mainml.py schemas and src.contracts.nlp_input schemas.
    Handles platform mapping, sentiment/emotion conversion, and engagement aggregation.
    """

    # Platform mapping: mainml source -> downstream Platform enum
    # Dynamically fall back to Platform.X if a specific platform key isn't in Platform enum
    PLATFORM_MAP = {
        "x": getattr(Platform, "X", Platform.X),
        "telegram": getattr(Platform, "TELEGRAM", Platform.X),
        "reddit": getattr(Platform, "REDDIT", Platform.X),
        "instagram": getattr(Platform, "INSTAGRAM", Platform.X),
        "other": getattr(Platform, "OTHER", Platform.X),
    }

    @staticmethod
    def social_media_event_to_nlp_contract(
        request: SocialMediaEventRequest,
        response: SocialMediaEventResponse
    ) -> NLPOutputContract:
        """
        Convert mainml SocialMediaEventRequest + SocialMediaEventResponse to NLPOutputContract.
        Primary conversion path: mainml output -> downstream pipeline input.
        """
        platform = NLPAdapter.PLATFORM_MAP.get(
            request.source.lower(),
            Platform.X
        )

        return NLPOutputContract(
            event_id=str(request.event_id),
            timestamp=request.timestamp_utc,
            platform=platform,
            embedding_ref=response.embedding_ref or str(request.event_id),
            author_id=request.author_id_hash,
            likes=request.engagement.likes,
            shares=request.engagement.shares,
            comments=request.engagement.comments,
            raw_text=request.text,
            sentiment=SentimentBlock(
                label=response.sentiment.label,
                score=response.sentiment.confidence
            ),
            metrics=MetricsBlock(
                engagement=(
                    request.engagement.likes
                    + request.engagement.shares
                    + request.engagement.comments
                ),
                likes=request.engagement.likes,
                shares=request.engagement.shares,
                comments=request.engagement.comments,
            )
        )

    @staticmethod
    def nlp_contract_to_social_media_event(
        payload: NLPOutputContract
    ) -> SocialMediaEventRequest:
        """
        Convert NLPOutputContract back to SocialMediaEventRequest.
        Reverse path: downstream -> mainml (if needed for re-processing).
        """
        platform_reverse_map = {
            Platform.X: "x",
            getattr(Platform, "TELEGRAM", None): "telegram",
            getattr(Platform, "REDDIT", None): "reddit",
            getattr(Platform, "INSTAGRAM", None): "instagram",
        }

        source_str = platform_reverse_map.get(payload.platform, "other")

        # Guarantee source_str is one of the allowed literals
        if source_str not in {"x", "telegram", "reddit", "instagram", "other"}:
            source_str = "other"

        return SocialMediaEventRequest(
            event_id=UUID(payload.event_id) if isinstance(payload.event_id, str) else payload.event_id,
            source=source_str,  # type: ignore
            source_post_id=str(payload.event_id),
            author_id_hash=payload.author_id,
            timestamp_utc=payload.timestamp,
            text=payload.raw_text or "",
            language="en",
            engagement=Engagement(
                likes=payload.likes,
                shares=payload.shares,
                comments=payload.comments,
                views=0
            ),
            metadata=Metadata(
                source_version="1.0.0",
                collected_at_utc=datetime.now(timezone.utc)  # Timezone-aware fix!
            )
        )

    @staticmethod
    def extract_emotion_metadata(response: SocialMediaEventResponse) -> Dict[str, Any]:
        """
        Extract emotion and stance metadata from SocialMediaEventResponse.
        Used by downstream pipeline for enrichment beyond basic sentiment label.
        """
        return {
            "emotion_label": response.emotion.label,
            "emotion_confidence": response.emotion.confidence,
            "stance_label": response.stance.label,
            "stance_target": response.stance.target,
            "stance_confidence": response.stance.confidence,
            "language_detected": response.language.label,
            "language_confidence": response.language.confidence,
        }
