"""
Report generator.

Generates the final Markdown report for each run.
Detailed enough to reproduce extraction without re-discovery.
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

import structlog

from src.models.intelligence import ExtractionAttempt, WebsiteIntelligence
from src.models.product import RawProduct
from src.models.run import RunConfig, RunContext

logger = structlog.get_logger(__name__)


class ReportGenerator:
    """Generates a detailed run report in Markdown."""

    def __init__(
        self,
        run_dir: Path,
        config: RunConfig,
        context: RunContext,
        intelligence: WebsiteIntelligence | None,
        products: list[RawProduct],
        attempts: list[ExtractionAttempt],
    ):
        self.run_dir = run_dir
        self.config = config
        self.context = context
        self.intel = intelligence
        self.products = products
        self.attempts = attempts

    def generate(self) -> Path:
        """Generate and write report.md. Returns path."""
        lines: list[str] = []

        lines += self._header()
        lines += self._website_summary()
        lines += self._protection_analysis()
        lines += self._discovery_section()
        lines += self._extraction_section()
        lines += self._coverage_section()
        lines += self._statistics_section()
        lines += self._recommendations()
        lines += self._footer()

        report_path = self.run_dir / "report.md"
        report_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("report.generated", path=str(report_path))
        return report_path

    def _header(self) -> list[str]:
        return [
            f"# Reference DB Intelligence Agent — Run Report",
            f"",
            f"**Run ID:** `{self.context.run_id}`  ",
            f"**Target:** {self.config.target_url}  ",
            f"**Started:** {self.context.started_at.isoformat()}  ",
            f"**Generated:** {datetime.now(timezone.utc).isoformat()}  ",
            f"",
            "---",
            "",
        ]

    def _website_summary(self) -> list[str]:
        lines = ["## 1. Website Summary", ""]
        lines.append(f"- **URL:** {self.config.target_url}")
        if self.intel:
            lines.append(f"- **Robots.txt:** {'Found' if self.intel.robots_txt else 'Not found'}")
            lines.append(f"- **Sitemaps discovered:** {len(self.intel.sitemaps)}")
            lines.append(f"- **API endpoints discovered:** {len(self.intel.api_endpoints)}")
            lines.append(f"- **GraphQL endpoints:** {len(self.intel.graphql_endpoints)}")
            if self.intel.product_url_patterns:
                lines.append(f"- **Product URL pattern:** `{'`, `'.join(self.intel.product_url_patterns)}`")
        lines += ["", "---", ""]
        return lines

    def _protection_analysis(self) -> list[str]:
        lines = ["## 2. Protection Analysis", ""]
        if not self.intel or not self.intel.protections:
            lines.append("No protection analysis available.")
            lines += ["", "---", ""]
            return lines

        for p in self.intel.protections:
            status = "⚠️ DETECTED" if p.detected else "✅ Not detected"
            lines.append(f"### {p.name} — {status}")
            if p.detection_method:
                lines.append(f"- **Detection method:** {p.detection_method}")
            if p.impact and p.detected:
                lines.append(f"- **Impact:** {p.impact}")
            if p.workaround_attempted:
                lines.append(f"- **Workaround:** {p.workaround_attempted} → {p.result}")
            if p.notes:
                lines.append(f"- **Notes:** {p.notes}")
            lines.append("")

        lines += ["---", ""]
        return lines

    def _discovery_section(self) -> list[str]:
        lines = ["## 3. Discovery Results", ""]
        if not self.intel:
            lines.append("Discovery was not completed.")
            lines += ["", "---", ""]
            return lines

        # Sitemaps
        if self.intel.sitemaps:
            lines.append("### Sitemaps")
            for s in self.intel.sitemaps:
                lines.append(f"- `{s.url}` — type: **{s.type}**, URLs: {s.url_count or 'unknown'}")
            lines.append("")

        # APIs
        if self.intel.api_endpoints:
            lines.append("### API Endpoints")
            for ep in self.intel.api_endpoints:
                lines.append(f"- `{ep.url}` — {ep.type} ({ep.method})")
            lines.append("")

        if self.intel.graphql_endpoints:
            lines.append("### GraphQL Endpoints")
            for ep in self.intel.graphql_endpoints:
                lines.append(f"- `{ep.url}`")
            lines.append("")

        if self.intel.robots_txt:
            lines.append("### robots.txt (excerpt)")
            lines.append("```")
            lines.append(self.intel.robots_txt[:500])
            lines.append("```")
            lines.append("")

        lines += ["---", ""]
        return lines

    def _extraction_section(self) -> list[str]:
        lines = ["## 4. Extraction Attempts", ""]
        for attempt in self.attempts:
            icon = "✅" if attempt.status == "success" else "❌" if attempt.status == "failed" else "⚠️"
            lines.append(f"### {icon} {attempt.method}")
            lines.append(f"- **Tool:** {attempt.tool or 'N/A'}")
            lines.append(f"- **Status:** {attempt.status}")
            lines.append(f"- **Products extracted:** {attempt.products_extracted}")
            lines.append(f"- **URLs processed:** {len(attempt.urls_processed)}")
            if attempt.fields_extracted:
                lines.append(f"- **Fields found:** {', '.join(attempt.fields_extracted)}")
            if attempt.failure_reason:
                lines.append(f"- **Failure reason:** {attempt.failure_reason}")
            if attempt.observations:
                lines.append(f"- **Observations:** {attempt.observations}")
            lines.append("")
        lines += ["---", ""]
        return lines

    def _coverage_section(self) -> list[str]:
        lines = ["## 5. Field Coverage", ""]
        if not self.products:
            lines.append("No products extracted.")
            lines += ["", "---", ""]
            return lines

        fields = [
            "barcode", "product_name", "brand", "description",
            "categories", "package_size", "ingredients_raw",
            "nutrition_raw", "allergens_raw", "certifications",
            "image_urls", "manufacturer", "price",
        ]
        total = len(self.products)

        lines.append(f"Total products: **{total}**")
        lines.append("")
        lines.append("| Field | Extracted | Coverage |")
        lines.append("|-------|-----------|----------|")
        for field in fields:
            count = sum(
                1 for p in self.products
                if getattr(p, field, None) not in (None, [], "")
            )
            rate = f"{count / total * 100:.1f}%"
            lines.append(f"| {field} | {count}/{total} | {rate} |")

        lines += ["", "---", ""]
        return lines

    def _statistics_section(self) -> list[str]:
        lines = ["## 6. Run Statistics", ""]
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Products extracted | {len(self.products)} |")
        lines.append(f"| Pages visited | {self.context.pages_visited} |")
        lines.append(f"| Extraction methods tried | {len(self.attempts)} |")
        successful = sum(1 for a in self.attempts if a.status == "success")
        lines.append(f"| Successful methods | {successful}/{len(self.attempts)} |")
        lines += ["", "---", ""]
        return lines

    def _recommendations(self) -> list[str]:
        lines = ["## 7. Recommendations for Future Runs", ""]

        if self.intel:
            for p in self.intel.protections:
                if p.detected:
                    if "Cloudflare" in p.name:
                        lines.append("- **Cloudflare detected:** Use residential proxy or Bright Data MCP for future runs.")
                    if "JavaScript Rendering" in p.name:
                        lines.append("- **JS rendering required:** Playwright is mandatory for this site.")
                    if "Rate Limiting" in p.name:
                        lines.append("- **Rate limiting detected:** Add delays between requests (2-5 seconds).")

        if not self.products:
            lines.append("- No products extracted this run. Try Playwright or Crawl4AI next.")

        if self.products and not any(p.barcode for p in self.products):
            lines.append("- **Barcodes missing:** Check network requests for a hidden API returning GTIN/UPC data.")

        lines += ["", "---", ""]
        return lines

    def _footer(self) -> list[str]:
        return [
            f"*Generated by Reference DB Intelligence Agent — {datetime.now(timezone.utc).isoformat()}*",
        ]
