"""
Run manager.

Orchestrates the full agent pipeline:
1. Setup run directory
2. Protection analysis
3. Website discovery
4. Extraction (priority order)
5. Save artifacts
6. Generate report
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import orjson
import structlog

from src.discovery.discoverer import WebsiteDiscoverer
from src.extractors.json_ld import JsonLdExtractor
from src.extractors.playwright_extractor import PlaywrightExtractor
from src.models.intelligence import ExtractionAttempt, WebsiteIntelligence
from src.models.product import RawProduct
from src.models.run import RunConfig, RunContext
from src.protection.analyzer import ProtectionAnalyzer
from src.reports.generator import ReportGenerator

logger = structlog.get_logger(__name__)

RUNS_DIR = Path("runs")


class RunManager:
    """
    Manages a single agent run from start to finish.

    Preserves all artifacts. Generates final report.
    """

    def __init__(self, config: RunConfig):
        self.config = config
        self.run_id = datetime.now(timezone.utc).strftime("%Y-%m-%d") + f"_{uuid.uuid4().hex[:6]}"
        self.run_dir = RUNS_DIR / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

        self.context = RunContext(
            run_id=self.run_id,
            config=config,
            run_dir=str(self.run_dir),
            products_file=str(self.run_dir / "raw_products.jsonl"),
            log_file=str(self.run_dir / "logs.json"),
        )

        self._products: list[RawProduct] = []
        self._attempts: list[ExtractionAttempt] = []
        self._intelligence: WebsiteIntelligence | None = None
        self._logs: list[dict[str, Any]] = []

        logger.info("run.start", run_id=self.run_id, url=config.target_url)

    async def execute(self) -> None:
        """Execute the full pipeline."""
        try:
            await self._phase_protection()
            await self._phase_discovery()
            await self._phase_extraction()
        finally:
            await self._save_artifacts()
            await self._generate_report()
            logger.info(
                "run.complete",
                run_id=self.run_id,
                products=len(self._products),
            )

    # --- Phase 1: Protection ---

    async def _phase_protection(self) -> None:
        logger.info("phase.protection.start")
        analyzer = ProtectionAnalyzer(self.config.target_url)
        try:
            protections = await analyzer.analyze()
            if self._intelligence:
                self._intelligence.protections = protections
            self._log("protection_analysis", {
                "detected": [p.name for p in protections if p.detected]
            })
        finally:
            await analyzer.close()

    # --- Phase 2: Discovery ---

    async def _phase_discovery(self) -> None:
        logger.info("phase.discovery.start")
        discoverer = WebsiteDiscoverer(self.config.target_url)
        try:
            self._intelligence = await discoverer.discover()
            self._log("discovery_complete", {
                "sitemaps": len(self._intelligence.sitemaps),
                "apis": len(self._intelligence.api_endpoints),
            })
        finally:
            await discoverer.close()

    # --- Phase 3: Extraction (priority order) ---

    async def _phase_extraction(self) -> None:
        logger.info("phase.extraction.start")

        # Collect candidate product URLs from sitemaps
        candidate_urls = self._collect_product_urls()
        if not candidate_urls:
            candidate_urls = [self.config.target_url]

        logger.info("phase.extraction.candidates", count=len(candidate_urls))

        # Priority 1: JSON-LD
        await self._run_extractor("json-ld", JsonLdExtractor(self.config.target_url), candidate_urls[:50])

        # Priority 2: Playwright (if JS rendering detected or JSON-LD got nothing)
        js_required = self._is_js_rendering_required()
        if js_required or not self._products:
            await self._run_extractor(
                "playwright",
                PlaywrightExtractor(self.config.target_url),
                candidate_urls[:10],  # Playwright is slower
            )

    async def _run_extractor(self, name: str, extractor, urls: list[str]) -> None:
        """Run one extractor and accumulate results."""
        logger.info(f"extractor.start", name=name, urls=len(urls))
        try:
            products, attempt = await extractor.extract(urls)
            self._products.extend(products)
            self._attempts.append(attempt)
            self.context.products_extracted += len(products)
            self._log(f"extractor_{name}", {
                "status": attempt.status,
                "products": len(products),
            })
            logger.info(f"extractor.done", name=name, products=len(products), status=attempt.status)
        except Exception as exc:
            logger.error(f"extractor.error", name=name, error=str(exc))

    # --- Helpers ---

    def _collect_product_urls(self) -> list[str]:
        """Collect product URLs from discovered sitemaps."""
        urls: list[str] = []
        if not self._intelligence:
            return urls
        for sitemap in self._intelligence.sitemaps:
            if sitemap.type in ("products", "general"):
                urls.extend(sitemap.sample_urls)
        return list(dict.fromkeys(urls))  # deduplicate, preserve order

    def _is_js_rendering_required(self) -> bool:
        if not self._intelligence:
            return False
        for protection in self._intelligence.protections:
            if "JavaScript Rendering" in protection.name and protection.detected:
                return True
        return False

    def _log(self, event: str, data: dict[str, Any]) -> None:
        self._logs.append({"event": event, "data": data})

    # --- Artifact Saving ---

    async def _save_artifacts(self) -> None:
        logger.info("artifacts.saving", run_dir=str(self.run_dir))

        # Products as JSONL
        with open(self.run_dir / "raw_products.jsonl", "wb") as f:
            for product in self._products:
                f.write(orjson.dumps(product.model_dump()) + b"\n")

        # Intelligence
        if self._intelligence:
            self._save_json("website_intelligence.json", self._intelligence.model_dump())

            # Individual intelligence files as per spec
            if self._intelligence.sitemaps:
                self._save_json("sitemaps.json", [s.model_dump() for s in self._intelligence.sitemaps])
            if self._intelligence.api_endpoints:
                self._save_json("apis.json", [a.model_dump() for a in self._intelligence.api_endpoints])
            if self._intelligence.graphql_endpoints:
                self._save_json("graphql_endpoints.json", [e.model_dump() for e in self._intelligence.graphql_endpoints])
            if self._intelligence.json_endpoints:
                self._save_json("json_endpoints.json", [e.model_dump() for e in self._intelligence.json_endpoints])
            if self._intelligence.protections:
                self._save_json("protection_analysis.json", [p.model_dump() for p in self._intelligence.protections])
            if self._intelligence.robots_txt:
                (self.run_dir / "robots.txt").write_text(self._intelligence.robots_txt)
            if self._intelligence.network_requests:
                self._save_json("network_requests.json", self._intelligence.network_requests)

        # Coverage + stats
        coverage = self._compute_coverage()
        self._save_json("coverage_report.json", coverage)

        stats = self._compute_stats()
        self._save_json("statistics.json", stats)

        # Logs
        self._save_json("logs.json", self._logs)

        logger.info("artifacts.saved")

    def _save_json(self, filename: str, data: Any) -> None:
        path = self.run_dir / filename
        path.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))

    def _compute_coverage(self) -> dict[str, Any]:
        if not self._products:
            return {}

        fields = [
            "barcode", "product_name", "brand", "description",
            "categories", "package_size", "serving_size",
            "ingredients_raw", "nutrition_raw", "allergens_raw",
            "certifications", "marketing_claims", "image_urls",
            "manufacturer", "price",
        ]
        total = len(self._products)
        coverage = {}
        for field in fields:
            count = sum(
                1 for p in self._products
                if getattr(p, field, None) not in (None, [], "")
            )
            coverage[field] = {
                "extracted": count,
                "total": total,
                "rate": f"{count / total * 100:.1f}%" if total else "0%",
            }
        return coverage

    def _compute_stats(self) -> dict[str, Any]:
        intel = self._intelligence
        return {
            "run_id": self.run_id,
            "target_url": self.config.target_url,
            "products_discovered": self.context.products_discovered,
            "products_extracted": len(self._products),
            "pages_visited": self.context.pages_visited,
            "sitemaps_discovered": len(intel.sitemaps) if intel else 0,
            "apis_discovered": len(intel.api_endpoints) if intel else 0,
            "graphql_endpoints": len(intel.graphql_endpoints) if intel else 0,
            "extraction_methods_used": [a.method for a in self._attempts],
            "extraction_success_rate": self._success_rate(),
        }

    def _success_rate(self) -> str:
        if not self._attempts:
            return "0%"
        success = sum(1 for a in self._attempts if a.status == "success")
        return f"{success / len(self._attempts) * 100:.1f}%"

    async def _generate_report(self) -> None:
        generator = ReportGenerator(
            run_dir=self.run_dir,
            config=self.config,
            context=self.context,
            intelligence=self._intelligence,
            products=self._products,
            attempts=self._attempts,
        )
        generator.generate()
