"""
NutritionRecord model.

Always stored separate from product data.
Always has both raw + parsed versions.
Linked to products.jsonl via identifier.
"""

from pydantic import BaseModel, Field


class NutritionRecord(BaseModel):
    """
    Nutrition data extracted from a source website.

    Stored in nutrition.jsonl — separate from products.jsonl.
    Linked to its product via the strongest available identifier.
    """

    # --- Link to product ---
    # One of these must exist — use the strongest available
    barcode: str | None = None
    gtin: str | None = None
    upc: str | None = None
    ean: str | None = None
    external_id: str | None = None
    source_product_id: str | None = None
    natural_key: str | None = Field(
        None,
        description="Deterministic fallback: slugify(brand_productname_size)"
    )

    # --- Source ---
    product_url: str = Field(..., description="URL where nutrition was found")
    source: str = Field(..., description="Domain of source website")
    extracted_at: str = Field(..., description="ISO timestamp")
    extraction_method: str = Field(..., description="Method used")

    # --- Raw (never modify) ---
    nutrition_raw: str | None = Field(
        None,
        description="Nutrition table exactly as found on the website"
    )

    # --- Parsed (best effort) ---
    calories: str | None = None
    protein: str | None = None
    carbohydrates: str | None = None
    sugars: str | None = None
    fat: str | None = None
    saturated_fat: str | None = None
    trans_fat: str | None = None
    fiber: str | None = None
    sodium: str | None = None
    cholesterol: str | None = None
    potassium: str | None = None
    calcium: str | None = None
    iron: str | None = None

    # --- Extra fields ---
    extra_nutrients: dict[str, str] = Field(
        default_factory=dict,
        description="Any nutrients not in the list above"
    )

    def get_identifier(self) -> tuple[str, str]:
        """
        Return (field_name, value) for the strongest available identifier.
        Used to link nutrition records to product records.
        """
        for field in ("barcode", "gtin", "upc", "ean", "external_id", "source_product_id", "natural_key"):
            val = getattr(self, field)
            if val:
                return (field, val)
        raise ValueError(f"NutritionRecord has no identifier: {self.product_url}")
