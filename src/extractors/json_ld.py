"""
JSON-LD extractor.

Extracts product data from JSON-LD blocks embedded in HTML.
This is the highest-priority structured extraction method.
"""

from __future__ import annotations

import re

import httpx
import orjson
import structlog
from bs4 import BeautifulSoup

from src.models.intelligence import ExtractionAttempt
from src.models.product import RawProduct
from src.extractors.base import BaseExtractor

logger = structlog.get_logger(__name__)


class JsonLdExtractor(BaseExtractor):
    """Extracts products from JSON-LD <script> blocks."""

    name = "json-ld"

    def __init__(self, base_url: str, client: httpx.AsyncClient | None = None):
        super().__init__(base_url)
        self.client = client or httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
                )
            },
        )

    async def extract(self, urls: list[str]) -> tuple[list[RawProduct], ExtractionAttempt]:
        """Extract JSON-LD product data from a list of URLs."""
        products: list[RawProduct] = []
        all_fields: set[str] = set()

        for url in urls:
            try:
                r = await self.client.get(url)
                if r.status_code != 200:
                    self.log.warning("json_ld.skip", url=url, status=r.status_code)
                    continue

                page_products = self._parse_page(url, r.text)
                for p in page_products:
                    all_fields.update(p.model_fields_set)
                products.extend(page_products)

            except Exception as exc:
                self.log.warning("json_ld.error", url=url, error=str(exc))

        status = "success" if products else "failed"
        attempt = self.make_attempt(
            urls=urls,
            status=status,
            fields=list(all_fields),
            products_extracted=len(products),
            failure_reason="No JSON-LD Product blocks found" if not products else None,
        )

        self.log.info("json_ld.complete", products=len(products), urls=len(urls))
        return products, attempt

    def _parse_page(self, url: str, html: str) -> list[RawProduct]:
        """Parse all JSON-LD blocks from a page and extract Product schemas."""
        soup = BeautifulSoup(html, "lxml")
        scripts = soup.find_all("script", type="application/ld+json")
        products: list[RawProduct] = []

        for script in scripts:
            try:
                raw = orjson.loads(script.string or "")
                blocks = raw if isinstance(raw, list) else [raw]
                for block in blocks:
                    if self._is_product(block):
                        product = self._map_to_product(url, block)
                        if product:
                            products.append(product)
            except Exception as exc:
                self.log.debug("json_ld.parse_error", url=url, error=str(exc))

        return products

    def _is_product(self, block: dict) -> bool:
        schema_type = block.get("@type", "")
        if isinstance(schema_type, list):
            return "Product" in schema_type
        return schema_type == "Product"

    def _map_to_product(self, source_url: str, block: dict) -> RawProduct | None:
        """Map a JSON-LD Product block to a RawProduct."""
        try:
            offers = block.get("offers", {})
            if isinstance(offers, list):
                offers = offers[0] if offers else {}

            # Extract barcode from identifier fields
            barcode = self._extract_barcode(block)

            # Nutrition
            nutrition_raw = None
            nutrition_structured = None
            nutrition_info = block.get("nutrition")
            if nutrition_info and isinstance(nutrition_info, dict):
                nutrition_raw = str(nutrition_info)
                nutrition_structured = nutrition_info

            return RawProduct(
                source_url=source_url,
                extracted_at=self.now_iso(),
                extraction_method=self.name,
                product_name=block.get("name"),
                brand=self._extract_brand(block),
                description=block.get("description"),
                barcode=barcode,
                image_urls=self._extract_images(block),
                price=str(offers.get("price")) if offers.get("price") else None,
                price_currency=offers.get("priceCurrency"),
                nutrition_raw=nutrition_raw,
                nutrition_structured=nutrition_structured,
                raw_json_ld=block,
                extra_fields={
                    k: v
                    for k, v in block.items()
                    if k
                    not in {
                        "@context", "@type", "name", "brand", "description",
                        "image", "offers", "nutrition", "identifier",
                        "gtin13", "gtin12", "gtin8", "sku", "mpn",
                    }
                },
            )
        except Exception as exc:
            self.log.warning("json_ld.map_error", error=str(exc))
            return None

    def _extract_barcode(self, block: dict) -> str | None:
        for field in ("gtin13", "gtin12", "gtin8", "gtin", "isbn"):
            if val := block.get(field):
                return str(val)
        identifiers = block.get("identifier", [])
        if isinstance(identifiers, list):
            for ident in identifiers:
                if isinstance(ident, dict) and "value" in ident:
                    return str(ident["value"])
        return None

    def _extract_brand(self, block: dict) -> str | None:
        brand = block.get("brand")
        if isinstance(brand, dict):
            return brand.get("name")
        return str(brand) if brand else None

    def _extract_images(self, block: dict) -> list[str]:
        image = block.get("image", [])
        if isinstance(image, str):
            return [image]
        if isinstance(image, list):
            return [str(i) for i in image if i]
        return []

    async def close(self) -> None:
        await self.client.aclose()
