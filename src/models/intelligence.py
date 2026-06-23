"""
Website intelligence models.

Captures everything discovered about a website's structure,
APIs, protections, and extraction methods.
"""

from typing import Any, Literal
from pydantic import BaseModel, Field


class ProtectionReport(BaseModel):
    """Documents a detected protection mechanism."""

    name: str  # e.g. "Cloudflare", "CAPTCHA", "Rate Limiting"
    detected: bool
    detection_method: str | None = None
    impact: str | None = None
    workaround_attempted: str | None = None
    result: Literal["success", "failed", "partial", "not_attempted"] = "not_attempted"
    notes: str | None = None


class SitemapEntry(BaseModel):
    """A discovered sitemap URL."""

    url: str
    type: Literal["index", "products", "categories", "general", "unknown"] = "unknown"
    discovered_at: str
    url_count: int | None = None
    sample_urls: list[str] = Field(default_factory=list)


class ApiEndpoint(BaseModel):
    """A discovered API, GraphQL, or JSON endpoint."""

    url: str
    type: Literal["rest", "graphql", "json", "search", "unknown"] = "unknown"
    method: Literal["GET", "POST", "unknown"] = "unknown"
    discovered_via: str | None = None  # e.g. "network_intercept", "source_scan"
    requires_auth: bool = False
    sample_response_keys: list[str] = Field(default_factory=list)
    notes: str | None = None


class ExtractionAttempt(BaseModel):
    """Records one extraction method attempt."""

    method: str  # e.g. "json-ld", "graphql", "playwright", "crawl4ai"
    tool: str | None = None
    urls_processed: list[str] = Field(default_factory=list)
    fields_extracted: list[str] = Field(default_factory=list)
    status: Literal["success", "failed", "partial"] = "failed"
    failure_reason: str | None = None
    products_extracted: int = 0
    observations: str | None = None


class WebsiteIntelligence(BaseModel):
    """
    Complete intelligence gathered about a website.

    Preserved as a reusable artifact so future runs
    skip the discovery phase.
    """

    target_url: str
    discovered_at: str

    # Structure
    robots_txt: str | None = None
    robots_txt_url: str | None = None
    sitemaps: list[SitemapEntry] = Field(default_factory=list)

    # Endpoints
    api_endpoints: list[ApiEndpoint] = Field(default_factory=list)
    graphql_endpoints: list[ApiEndpoint] = Field(default_factory=list)
    json_endpoints: list[ApiEndpoint] = Field(default_factory=list)
    search_endpoints: list[ApiEndpoint] = Field(default_factory=list)

    # Structure
    category_hierarchy: dict[str, Any] = Field(default_factory=dict)
    product_url_patterns: list[str] = Field(default_factory=list)
    pagination_pattern: str | None = None

    # Protections
    protections: list[ProtectionReport] = Field(default_factory=list)

    # Extraction history
    extraction_attempts: list[ExtractionAttempt] = Field(default_factory=list)

    # Raw discoveries
    network_requests: list[dict[str, Any]] = Field(default_factory=list)
    embedded_state_keys: list[str] = Field(default_factory=list)
    json_ld_schemas: list[str] = Field(default_factory=list)

    # Notes
    notes: str | None = None
