"""
Change detection module.

Compares current run with the most recent previous run for the same domain.
Detects: new products, removed products, updated products, new fields.

Runs automatically every time the agent executes.
Default schedule: weekly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import orjson
import structlog

logger = structlog.get_logger(__name__)

RUNS_DIR = Path("runs")


class ChangeDetector:
    """
    Compares current extraction results with the previous run.

    Produces a change_report.json for every run.
    """

    def __init__(
        self,
        domain: str,
        current_run_id: str,
        current_products: list[dict[str, Any]],
    ):
        self.domain = domain
        self.current_run_id = current_run_id
        self.current_products = current_products

    def detect(self) -> dict[str, Any]:
        """
        Run change detection. Returns a change report dict.

        Always returns a report — even on first run (baseline).
        """
        previous_products = self._load_previous_products()

        if not previous_products:
            logger.info("change_detection.baseline", domain=self.domain)
            return self._baseline_report()

        # Index by identifier
        current_index = self._index_products(self.current_products)
        previous_index = self._index_products(previous_products)

        new_products = self._find_new(current_index, previous_index)
        removed_products = self._find_removed(current_index, previous_index)
        updated_products = self._find_updated(current_index, previous_index)
        new_fields = self._find_new_fields(current_index, previous_index)

        report = {
            "run_id": self.current_run_id,
            "domain": self.domain,
            "compared_with": self._find_previous_run_id(),
            "summary": {
                "new_products": len(new_products),
                "removed_products": len(removed_products),
                "updated_products": len(updated_products),
                "new_fields_discovered": len(new_fields),
            },
            "new_products": new_products,
            "removed_products": removed_products,
            "updated_products": updated_products,
            "new_fields_discovered": new_fields,
        }

        logger.info(
            "change_detection.complete",
            new=len(new_products),
            removed=len(removed_products),
            updated=len(updated_products),
            new_fields=new_fields,
        )
        return report

    def _load_previous_products(self) -> list[dict[str, Any]]:
        """Load products.jsonl from the most recent previous run for this domain."""
        previous_run_dir = self._find_previous_run_dir()
        if not previous_run_dir:
            return []

        products_file = previous_run_dir / "products.jsonl"
        if not products_file.exists():
            return []

        products = []
        for line in products_file.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    products.append(orjson.loads(line))
                except Exception:
                    pass
        return products

    def _find_previous_run_dir(self) -> Path | None:
        """Find the most recent run directory for this domain (not the current one)."""
        if not RUNS_DIR.exists():
            return None

        # Run dirs are named YYYY-MM-DD_XXXXXX — sort descending
        candidates = sorted(
            [d for d in RUNS_DIR.iterdir() if d.is_dir() and d.name != self.current_run_id],
            reverse=True,
        )
        for candidate in candidates:
            # Check if this run was for the same domain
            intel_file = candidate / "website_intelligence.json"
            if intel_file.exists():
                try:
                    intel = orjson.loads(intel_file.read_bytes())
                    if self.domain in intel.get("target_url", ""):
                        return candidate
                except Exception:
                    pass
        return None

    def _find_previous_run_id(self) -> str | None:
        d = self._find_previous_run_dir()
        return d.name if d else None

    def _index_products(self, products: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Index products by their strongest identifier."""
        IDENTIFIER_PRIORITY = ["barcode", "gtin", "upc", "ean", "external_id", "source_product_id", "natural_key"]
        index: dict[str, dict[str, Any]] = {}
        for product in products:
            for field in IDENTIFIER_PRIORITY:
                val = product.get(field)
                if val:
                    index[str(val)] = product
                    break
        return index

    def _find_new(
        self,
        current: dict[str, dict],
        previous: dict[str, dict],
    ) -> list[dict[str, Any]]:
        """Products in current run but not in previous run."""
        return [
            {"identifier": k, "product_name": v.get("product_name"), "brand": v.get("brand")}
            for k, v in current.items()
            if k not in previous
        ]

    def _find_removed(
        self,
        current: dict[str, dict],
        previous: dict[str, dict],
    ) -> list[dict[str, Any]]:
        """Products in previous run but not in current run."""
        return [
            {"identifier": k, "product_name": v.get("product_name"), "brand": v.get("brand")}
            for k, v in previous.items()
            if k not in current
        ]

    def _find_updated(
        self,
        current: dict[str, dict],
        previous: dict[str, dict],
    ) -> list[dict[str, Any]]:
        """Products present in both runs but with changed fields."""
        TRACKED_FIELDS = [
            "product_name", "brand", "category", "package_size", "package_unit",
            "ingredients", "image_url", "price", "description",
            "certifications", "marketing_claims",
        ]
        updated = []
        for identifier, current_product in current.items():
            if identifier not in previous:
                continue
            previous_product = previous[identifier]
            changed_fields = []
            for field in TRACKED_FIELDS:
                curr_val = current_product.get(field)
                prev_val = previous_product.get(field)
                if curr_val != prev_val:
                    changed_fields.append({
                        "field": field,
                        "previous": prev_val,
                        "current": curr_val,
                    })
            if changed_fields:
                updated.append({
                    "identifier": identifier,
                    "product_name": current_product.get("product_name"),
                    "changed_fields": changed_fields,
                })
        return updated

    def _find_new_fields(
        self,
        current: dict[str, dict],
        previous: dict[str, dict],
    ) -> list[str]:
        """Fields discovered in this run that weren't in the previous run."""
        if not current or not previous:
            return []
        current_fields: set[str] = set()
        for p in current.values():
            current_fields.update(p.keys())
        previous_fields: set[str] = set()
        for p in previous.values():
            previous_fields.update(p.keys())
        return sorted(current_fields - previous_fields)

    def _baseline_report(self) -> dict[str, Any]:
        """Report for first-ever run — no previous data to compare."""
        return {
            "run_id": self.current_run_id,
            "domain": self.domain,
            "compared_with": None,
            "note": "First run for this domain — baseline established.",
            "summary": {
                "new_products": len(self.current_products),
                "removed_products": 0,
                "updated_products": 0,
                "new_fields_discovered": 0,
            },
            "new_products": [],
            "removed_products": [],
            "updated_products": [],
            "new_fields_discovered": [],
        }
