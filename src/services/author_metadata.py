"""Author metadata source for Section D demographics — dual-mode, swappable
like `person2_qdrant_url` (see src/person2/vector_client.py).

Returns per-author {language, profession, geography}; any field may be
missing. Callers must treat a missing author or missing field as unknown —
never fabricate a value.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from src.config import PipelineConfig, DEFAULT_CONFIG


class AuthorMetadataSource(Protocol):
    def get_metadata(self, author_ids: list[str]) -> dict[str, dict]:
        """Return {author_id: {"language"?, "profession"?, "geography"?}}
        for the subset of author_ids that are known. Authors not present in
        the result are unknown for every category."""
        ...


class StaticAuthorMetadataSource:
    """Reads author -> {language, profession, geography} from a local JSON
    fixture keyed by author_id. Missing file or missing authors degrade to
    unknown rather than raising."""

    def __init__(self, path: str | Path | None = None, config: PipelineConfig = DEFAULT_CONFIG):
        self.path = Path(path or config.author_metadata_static_path)
        self._cache: dict[str, dict] | None = None

    def _load(self) -> dict[str, dict]:
        if self._cache is None:
            if self.path.exists():
                self._cache = json.loads(self.path.read_text(encoding="utf-8"))
            else:
                self._cache = {}
        return self._cache

    def get_metadata(self, author_ids: list[str]) -> dict[str, dict]:
        data = self._load()
        return {aid: data[aid] for aid in author_ids if aid in data}


class LiveAuthorMetadataSource:
    """
    WIRE LATER: Point this at Person 1 / infra's live author-metadata
    endpoint or DB.

    Required from Person 1 / infra:
      - author_metadata_live_url (config.author_metadata_live_url)
      - response schema: {author_id: {language?, profession?, geography?}}

    Until wired: with no URL configured this returns empty metadata (every
    author unknown) rather than fabricating data. Once a URL is set but the
    call is still unimplemented, it raises NotImplementedError so callers
    don't mistake "not wired" for "no data available".
    """

    def __init__(self, url: str | None = None, config: PipelineConfig = DEFAULT_CONFIG):
        self.url = url if url is not None else config.author_metadata_live_url
        self.config = config

    def get_metadata(self, author_ids: list[str]) -> dict[str, dict]:
        if not self.url:
            return {}
        raise NotImplementedError(
            "LiveAuthorMetadataSource is configured with "
            f"author_metadata_live_url={self.url!r} but the live call is not "
            "implemented yet. Wire the HTTP/DB call here, or set "
            "config.author_metadata_source='static' to use the fixture source."
        )


def build_author_metadata_source(config: PipelineConfig = DEFAULT_CONFIG) -> AuthorMetadataSource:
    if config.author_metadata_source == "live":
        return LiveAuthorMetadataSource(config=config)
    return StaticAuthorMetadataSource(config=config)
