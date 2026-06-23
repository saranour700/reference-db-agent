"""
RawProduct model.

Stored in products.jsonl — no nutrition data here.
Nutrition goes to nutrition.jsonl linked by identifier.

Preserves data exactly as found on the source website.
No normalization. No enrichment. No inference.
"""

from typing import Any
from pydantic import BaseModel, Field
import re


def _make_natural_key(brand: str | None, product_name: str | None, package_size: str | None) -> str | None:
    """
    Deterministic natural key when no barcode/gtin/upc exists.
    Format: brand_productname_size (slugified, lowercase).
    Never random.
    """
    parts = [p for p in (brand, product_name, package_size) if p]
    if not parts:
        return None
    raw = "_".join(parts).lower()
    return re.sub(r"[^a-z0-9_]", "_", raw)


class RawProduct(BaseModel):
    """
    Raw product data extracted from a source website.

    All fields optional except source_url, extracted_at, extraction_method.
    Missing values stay missing — never filled with null or empty string.
    """

    # --- Source metadata ---
    source_url: str = Field(..., description="URL where this product was found")
    source: str | None = Field(None, description="Domain e.g. voila.ca")
    extracted_at: str = Field(..., description="ISO timestamp of extraction")
    extraction_method: str = Field(..., description="Method used to extract")

    # --- Identifiers (priority order) ---
    barcode: str | None = None
    gtin: str | None = None
    upc: str | None = None
    ean: str | None = None
    external_id: str | None = None
    source_product_id: str | None = None
    natural_key: str | None = Field(None, description="Deterministic fallback. Never random.")

    # --- Core product info ---
    product_name: str | None = None
    brand: str | None = None
    category: str | None = None
    categories: list[str] = Field(default_factory=list)
    description: str | None = None

    # --- Packaging ---
    package_size: str | None = None
    package_unit: str | None = None

    # --- Ingredients ---
    ingredients: str | None = Field(None, description="Exactly as found on website")

    # --- Images ---
    image_url: str | None = Field(None, description="Primary product image")
    image_urls: list[str] = Field(default_factory=list)

    # --- Certifications & Claims ---
    certifications: list[str] = Field(default_factory=list)
    marketing_claims: list[str] = Field(default_factory=list)

    # --- Manufacturer ---
    manufacturer: str | None = None
    manufacturer_address: str | None = None
    country_of_origin: str | None = None

    # --- Pricing ---
    price: str | None = None
    price_currency: str | None = None

    # --- Raw structured data ---
    raw_json_ld: dict[str, Any] | None = Field(None, description="Raw JSON-LD block — never discard")

    # --- Extra discoverable fields ---
    extra_fields: dict[str, Any] = Field(default_factory=dict)

    def get_identifier(self) -> tuple[str, str] | None:
        """Return (field_name, value) for strongest available identifier."""
        for field in ("barcode", "gtin", "upc", "ean", "external_id", "source_product_id", "natural_key"):
            val = getattr(self, field)
            if val:
                return (field, val)
        return None

    def ensure_natural_key(self) -> None:
        """Generate deterministic natural key if no stable identifier exists."""
        if self.get_identifier() is None:
            self.natural_key = _make_natural_key(self.brand, self.product_name, self.package_size)

    model_config = {"extra": "allow"}
