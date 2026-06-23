"""
Run configuration and context models.
"""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class RunConfig(BaseModel):
    """User-provided configuration for a single agent run."""

    target_url: str = Field(..., description="Primary URL to scrape")
    target_fields: list[str] = Field(
        default_factory=list,
        description="Specific fields to extract. Empty = extract everything.",
    )
    max_products: int | None = Field(
        None, description="Max products to extract. None = no limit."
    )
    use_bright_data: bool = Field(
        False, description="Allow Bright Data MCP as fallback"
    )
    extra: dict[str, Any] = Field(
        default_factory=dict, description="Any extra run-specific settings"
    )


class RunContext(BaseModel):
    """Live state accumulated during a run."""

    run_id: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    config: RunConfig

    # Counters
    pages_visited: int = 0
    products_discovered: int = 0
    products_extracted: int = 0
    extraction_errors: int = 0

    # Paths
    run_dir: str = ""
    products_file: str = ""
    log_file: str = ""

    model_config = {"arbitrary_types_allowed": True}
