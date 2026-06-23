"""
Protection analysis module.

Detects and documents website protection mechanisms.
"""

from __future__ import annotations

import httpx
import structlog

from src.models.intelligence import ProtectionReport

logger = structlog.get_logger(__name__)


class ProtectionAnalyzer:
    """
    Analyzes a website's protection mechanisms.

    Detects: Cloudflare, CAPTCHA, rate limiting,
    bot protection, JS rendering requirements.
    """

    def __init__(self, base_url: str, client: httpx.AsyncClient | None = None):
        self.base_url = base_url
        self.client = client or httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
        )

    async def analyze(self) -> list[ProtectionReport]:
        """Run full protection analysis. Returns list of detected protections."""
        reports: list[ProtectionReport] = []

        try:
            r = await self.client.get(self.base_url)
            headers = r.headers
            body = r.text.lower()
            status = r.status_code

            reports.append(self._check_cloudflare(headers, body, status))
            reports.append(self._check_captcha(body))
            reports.append(self._check_rate_limiting(headers, status))
            reports.append(self._check_bot_protection(headers, body))
            reports.append(self._check_js_rendering(body))

        except httpx.ConnectError as exc:
            logger.warning("protection.connect_error", error=str(exc))
            reports.append(
                ProtectionReport(
                    name="Connection Error",
                    detected=True,
                    detection_method="connection_attempt",
                    impact="Cannot reach website at all",
                    notes=str(exc),
                )
            )
        except Exception as exc:
            logger.warning("protection.analysis_error", error=str(exc))

        detected = [r for r in reports if r.detected]
        logger.info(
            "protection.complete",
            total=len(reports),
            detected=[r.name for r in detected],
        )
        return reports

    def _check_cloudflare(
        self, headers: httpx.Headers, body: str, status: int
    ) -> ProtectionReport:
        detected = (
            "cf-ray" in headers
            or "cloudflare" in headers.get("server", "").lower()
            or status == 403
            and "cloudflare" in body
            or "__cf_bm" in headers.get("set-cookie", "")
        )
        return ProtectionReport(
            name="Cloudflare",
            detected=detected,
            detection_method="response_headers_and_body",
            impact="May block automated requests; requires Playwright or residential proxy" if detected else None,
            workaround_attempted="None yet",
            result="not_attempted",
        )

    def _check_captcha(self, body: str) -> ProtectionReport:
        keywords = ["captcha", "recaptcha", "hcaptcha", "turnstile", "are you human"]
        detected = any(k in body for k in keywords)
        return ProtectionReport(
            name="CAPTCHA",
            detected=detected,
            detection_method="body_keyword_scan",
            impact="Blocks automated requests; requires manual solving or 3rd-party service" if detected else None,
            result="not_attempted",
        )

    def _check_rate_limiting(
        self, headers: httpx.Headers, status: int
    ) -> ProtectionReport:
        detected = (
            status == 429
            or "retry-after" in headers
            or "x-ratelimit-limit" in headers
        )
        return ProtectionReport(
            name="Rate Limiting",
            detected=detected,
            detection_method="status_code_and_headers",
            impact="Requests will be throttled or blocked after threshold" if detected else None,
            result="not_attempted",
        )

    def _check_bot_protection(
        self, headers: httpx.Headers, body: str
    ) -> ProtectionReport:
        keywords = ["bot", "automated", "crawler", "robot", "datadome", "perimeterx"]
        server = headers.get("server", "").lower()
        detected = any(k in body[:2000] for k in keywords) or any(
            k in server for k in ["datadome", "perimeterx"]
        )
        return ProtectionReport(
            name="Bot Protection",
            detected=detected,
            detection_method="body_and_header_scan",
            impact="Sophisticated bot detection active" if detected else None,
            result="not_attempted",
        )

    def _check_js_rendering(self, body: str) -> ProtectionReport:
        # Page with very little HTML content suggests JS rendering required
        has_little_content = len(body.strip()) < 500
        has_js_framework = any(
            k in body
            for k in ["__NEXT_DATA__", "__nuxt", "window.__STATE__", "ng-version"]
        )
        detected = has_little_content or has_js_framework
        return ProtectionReport(
            name="JavaScript Rendering Required",
            detected=detected,
            detection_method="body_content_analysis",
            impact="Static HTTP requests won't get product data; need Playwright" if detected else None,
            result="not_attempted",
        )

    async def close(self) -> None:
        await self.client.aclose()
