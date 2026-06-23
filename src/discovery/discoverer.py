"""
Website discovery module.

Discovers robots.txt, sitemaps, API endpoints,
and website structure before extraction begins.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import httpx
import structlog

from src.models.intelligence import ApiEndpoint, SitemapEntry, WebsiteIntelligence

logger = structlog.get_logger(__name__)


class WebsiteDiscoverer:
    """
    Discovers website structure, sitemaps, and API endpoints.

    Runs before any extraction to build reusable intelligence.
    """

    COMMON_API_PATHS = [
        "/api/products",
        "/api/v1/products",
        "/api/v2/products",
        "/graphql",
        "/api/graphql",
        "/search.json",
        "/products.json",
        "/sitemap.xml",
        "/sitemap_index.xml",
        "/robots.txt",
        "/.well-known/sitemap",
    ]

    def __init__(self, base_url: str, client: httpx.AsyncClient | None = None):
        parsed = urlparse(base_url)
        self.base_url = f"{parsed.scheme}://{parsed.netloc}"
        self.client = client or httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; ReferenceDBBot/1.0; "
                    "+https://github.com/reference-db)"
                )
            },
        )

    async def discover(self) -> WebsiteIntelligence:
        """Run full discovery pipeline."""
        intel = WebsiteIntelligence(
            target_url=self.base_url,
            discovered_at=datetime.now(timezone.utc).isoformat(),
        )

        logger.info("discovery.start", url=self.base_url)

        intel.robots_txt_url = urljoin(self.base_url, "/robots.txt")
        intel.robots_txt = await self._fetch_robots(intel.robots_txt_url)

        intel.sitemaps = await self._discover_sitemaps(intel.robots_txt)

        api_endpoints = await self._probe_common_paths()
        for ep in api_endpoints:
            if ep.type == "graphql":
                intel.graphql_endpoints.append(ep)
            elif ep.type == "search":
                intel.search_endpoints.append(ep)
            elif ep.type == "json":
                intel.json_endpoints.append(ep)
            else:
                intel.api_endpoints.append(ep)

        logger.info(
            "discovery.complete",
            sitemaps=len(intel.sitemaps),
            apis=len(intel.api_endpoints),
            graphql=len(intel.graphql_endpoints),
        )
        return intel

    async def _fetch_robots(self, url: str) -> str | None:
        """Fetch and return robots.txt content."""
        try:
            r = await self.client.get(url)
            if r.status_code == 200:
                logger.info("discovery.robots_txt", status="found", url=url)
                return r.text
        except Exception as exc:
            logger.warning("discovery.robots_txt", status="failed", error=str(exc))
        return None

    async def _discover_sitemaps(self, robots_txt: str | None) -> list[SitemapEntry]:
        """Discover sitemaps from robots.txt and common paths."""
        sitemap_urls: set[str] = set()

        # Parse sitemap URLs from robots.txt
        if robots_txt:
            for line in robots_txt.splitlines():
                if line.lower().startswith("sitemap:"):
                    url = line.split(":", 1)[1].strip()
                    sitemap_urls.add(url)

        # Probe common sitemap paths
        for path in ["/sitemap.xml", "/sitemap_index.xml", "/sitemap/"]:
            sitemap_urls.add(urljoin(self.base_url, path))

        entries: list[SitemapEntry] = []
        for url in sitemap_urls:
            entry = await self._fetch_sitemap(url)
            if entry:
                entries.append(entry)

        return entries

    async def _fetch_sitemap(self, url: str) -> SitemapEntry | None:
        """Fetch a sitemap and classify it."""
        try:
            r = await self.client.get(url)
            if r.status_code != 200:
                return None

            content = r.text
            sitemap_type = self._classify_sitemap(url, content)

            # Count URLs
            url_count = content.count("<loc>")

            # Sample up to 5 product URLs
            sample_urls = re.findall(r"<loc>(.*?)</loc>", content)[:5]

            entry = SitemapEntry(
                url=url,
                type=sitemap_type,
                discovered_at=datetime.now(timezone.utc).isoformat(),
                url_count=url_count,
                sample_urls=sample_urls,
            )
            logger.info("discovery.sitemap", url=url, type=sitemap_type, urls=url_count)
            return entry

        except Exception as exc:
            logger.warning("discovery.sitemap.failed", url=url, error=str(exc))
            return None

    def _classify_sitemap(self, url: str, content: str) -> str:
        """Classify a sitemap by its URL and content."""
        url_lower = url.lower()
        if "product" in url_lower:
            return "products"
        if "categor" in url_lower:
            return "categories"
        if "index" in url_lower or "<sitemapindex" in content:
            return "index"
        if "<urlset" in content:
            return "general"
        return "unknown"

    async def _probe_common_paths(self) -> list[ApiEndpoint]:
        """Probe common API paths and classify responses."""
        endpoints: list[ApiEndpoint] = []

        for path in self.COMMON_API_PATHS:
            if path in ("/robots.txt", "/sitemap.xml", "/sitemap_index.xml"):
                continue  # Already handled

            url = urljoin(self.base_url, path)
            endpoint = await self._probe_endpoint(url)
            if endpoint:
                endpoints.append(endpoint)

        return endpoints

    async def _probe_endpoint(self, url: str) -> ApiEndpoint | None:
        """Probe a URL and return an ApiEndpoint if useful."""
        try:
            r = await self.client.get(url)
            content_type = r.headers.get("content-type", "")

            if r.status_code not in (200, 201):
                return None

            ep_type = "unknown"
            sample_keys: list[str] = []

            if "graphql" in url.lower():
                ep_type = "graphql"
            elif "search" in url.lower():
                ep_type = "search"
            elif "json" in content_type or url.endswith(".json"):
                ep_type = "json"
                try:
                    import orjson
                    data = orjson.loads(r.content)
                    if isinstance(data, dict):
                        sample_keys = list(data.keys())[:10]
                    elif isinstance(data, list) and data:
                        sample_keys = list(data[0].keys())[:10] if isinstance(data[0], dict) else []
                except Exception:
                    pass

            endpoint = ApiEndpoint(
                url=url,
                type=ep_type,
                method="GET",
                discovered_via="path_probe",
                sample_response_keys=sample_keys,
            )
            logger.info("discovery.endpoint", url=url, type=ep_type)
            return endpoint

        except Exception as exc:
            logger.debug("discovery.endpoint.failed", url=url, error=str(exc))
            return None

    async def close(self) -> None:
        await self.client.aclose()
