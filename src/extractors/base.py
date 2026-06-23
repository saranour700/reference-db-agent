"""
Base extractor class.

All extractors inherit from BaseExtractor and implement extract().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

import structlog

from src.models.intelligence import ExtractionAttempt
from src.models.product import RawProduct

logger = structlog.get_logger(__name__)


class BaseExtractor(ABC):
    """
    Base class for all product extractors.

    Subclasses implement extract() and return products + attempt log.
    """

    name: str = "base"

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.log = structlog.get_logger(self.__class__.__name__)

    @abstractmethod
    async def extract(self, urls: list[str]) -> tuple[list[RawProduct], ExtractionAttempt]:
        """
        Extract products from the given URLs.

        Returns:
            products: List of raw products extracted.
            attempt: Log of what was attempted.
        """
        ...

    def now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def make_product(self, source_url: str, **kwargs) -> RawProduct:
        """Convenience factory for RawProduct."""
        return RawProduct(
            source_url=source_url,
            extracted_at=self.now_iso(),
            extraction_method=self.name,
            **kwargs,
        )

    def make_attempt(
        self,
        urls: list[str],
        status: str = "failed",
        fields: list[str] | None = None,
        products_extracted: int = 0,
        failure_reason: str | None = None,
        observations: str | None = None,
    ) -> ExtractionAttempt:
        """Build an ExtractionAttempt record."""
        return ExtractionAttempt(
            method=self.name,
            tool=self.__class__.__name__,
            urls_processed=urls,
            fields_extracted=fields or [],
            status=status,
            failure_reason=failure_reason,
            products_extracted=products_extracted,
            observations=observations,
        )
