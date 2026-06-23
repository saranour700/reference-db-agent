"""
Playwright extractor.

Used for JavaScript-rendered pages where static HTTP requests
don't return product data.
"""

from __future__ import annotations

import re
from typing import Any

import orjson
import structlog

from src.models.intelligence import ExtractionAttempt
from src.models.product import RawProduct
from src.extractors.base import BaseExtractor

logger = structlog.get_logger(__name__)


class PlaywrightExtractor(BaseExtractor):
    """
    Extracts products from JS-rendered pages using Playwright.

    Also intercepts network requests to discover hidden API endpoints.
    """

    name = "playwright"

    def __init__(self, base_url: str, headless: bool = True):
        super().__init__(base_url)
        self.headless = headless
        self._intercepted_requests: list[dict[str, Any]] = []

    async def extract(self, urls: list[str]) -> tuple[list[RawProduct], ExtractionAttempt]:
        """Extract products from JS-rendered pages."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return [], self.make_attempt(
                urls=urls,
                status="failed",
                failure_reason="Playwright not installed. Run: playwright install chromium",
            )

        products: list[RawProduct] = []
        intercepted: list[dict[str, Any]] = []
        all_fields: set[str] = set()

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
                )
            )

            for url in urls:
                page = await context.new_page()
                page_requests: list[dict] = []

                async def on_request(request) -> None:
                    if any(
                        k in request.url
                        for k in ("api", "graphql", "json", "products", "search")
                    ):
                        page_requests.append(
                            {"url": request.url, "method": request.method}
                        )

                async def on_response(response) -> None:
                    content_type = response.headers.get("content-type", "")
                    if "json" in content_type:
                        try:
                            body = await response.json()
                            page_requests.append(
                                {
                                    "url": response.url,
                                    "status": response.status,
                                    "content_type": content_type,
                                    "data_keys": list(body.keys())[:10]
                                    if isinstance(body, dict)
                                    else "array",
                                }
                            )
                        except Exception:
                            pass

                page.on("request", on_request)
                page.on("response", on_response)

                try:
                    await page.goto(url, wait_until="networkidle", timeout=30000)

                    # Extract JSON-LD from rendered page
                    json_ld_blocks = await page.evaluate("""
                        () => {
                            const scripts = document.querySelectorAll(
                                'script[type="application/ld+json"]'
                            );
                            return Array.from(scripts).map(s => {
                                try { return JSON.parse(s.textContent); }
                                catch { return null; }
                            }).filter(Boolean);
                        }
                    """)

                    for block in json_ld_blocks:
                        if isinstance(block, dict) and block.get("@type") == "Product":
                            products.append(
                                self.make_product(
                                    source_url=url,
                                    product_name=block.get("name"),
                                    brand=block.get("brand", {}).get("name")
                                    if isinstance(block.get("brand"), dict)
                                    else block.get("brand"),
                                    raw_json_ld=block,
                                )
                            )

                    # Also extract embedded app state
                    app_state = await page.evaluate("""
                        () => {
                            const candidates = [
                                window.__NEXT_DATA__,
                                window.__STATE__,
                                window.__INITIAL_STATE__,
                                window.__APP_STATE__,
                            ];
                            return candidates.filter(Boolean)[0] || null;
                        }
                    """)

                    if app_state:
                        self.log.info(
                            "playwright.app_state_found",
                            url=url,
                            keys=list(app_state.keys())[:10]
                            if isinstance(app_state, dict)
                            else "array",
                        )

                    intercepted.extend(page_requests)

                except Exception as exc:
                    self.log.warning("playwright.page_error", url=url, error=str(exc))
                finally:
                    await page.close()

            await browser.close()

        self._intercepted_requests = intercepted

        for p in products:
            all_fields.update(p.model_fields_set)

        status = "success" if products else "partial"
        attempt = self.make_attempt(
            urls=urls,
            status=status,
            fields=list(all_fields),
            products_extracted=len(products),
            observations=f"Intercepted {len(intercepted)} network requests",
        )
        return products, attempt

    def get_intercepted_requests(self) -> list[dict[str, Any]]:
        """Return all intercepted network requests (useful for API discovery)."""
        return self._intercepted_requests
