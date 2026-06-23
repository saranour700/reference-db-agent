"""
Reference DB Intelligence Agent — CLI.

Usage:
    rdai run --url https://example.com
    rdai run --url https://example.com --fields barcode,brand,product_name
    rdai run --url https://example.com --max-products 100
"""

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from src.models.run import RunConfig
from src.run_manager import RunManager

app = typer.Typer(
    name="rdai",
    help="Reference DB Intelligence Agent — discover and extract product data.",
    pretty_exceptions_enable=False,
)
console = Console()


@app.command()
def run(
    url: str = typer.Option(..., "--url", "-u", help="Target website URL"),
    fields: Optional[str] = typer.Option(
        None,
        "--fields",
        "-f",
        help="Comma-separated fields to extract. Default: all fields.",
    ),
    max_products: Optional[int] = typer.Option(
        None, "--max-products", "-m", help="Max products to extract."
    ),
    use_bright_data: bool = typer.Option(
        False, "--bright-data", help="Allow Bright Data MCP as fallback."
    ),
) -> None:
    """Run the intelligence agent on a target URL."""
    console.print(
        Panel.fit(
            f"[bold blue]Reference DB Intelligence Agent[/bold blue]\n"
            f"Target: [green]{url}[/green]",
            border_style="blue",
        )
    )

    target_fields = [f.strip() for f in fields.split(",")] if fields else []

    config = RunConfig(
        target_url=url,
        target_fields=target_fields,
        max_products=max_products,
        use_bright_data=use_bright_data,
    )

    manager = RunManager(config)

    async def _run() -> None:
        await manager.execute()

    asyncio.run(_run())

    console.print(f"\n[green]✓ Run complete.[/green] Artifacts saved to: [blue]{manager.run_dir}[/blue]")
    console.print(f"[blue]Report:[/blue] {manager.run_dir}/report.md")


@app.command()
def discover(
    url: str = typer.Option(..., "--url", "-u", help="Target website URL"),
) -> None:
    """Run discovery only (no extraction). Useful for first-time analysis."""
    from src.discovery.discoverer import WebsiteDiscoverer
    from src.protection.analyzer import ProtectionAnalyzer
    import orjson
    from pathlib import Path
    from datetime import datetime, timezone

    console.print(f"[blue]Discovering:[/blue] {url}")

    async def _discover() -> None:
        analyzer = ProtectionAnalyzer(url)
        protections = await analyzer.analyze()
        await analyzer.close()

        discoverer = WebsiteDiscoverer(url)
        intel = await discoverer.discover()
        intel.protections = protections
        await discoverer.close()

        out_dir = Path("runs") / f"discover_{datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M%S')}"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "website_intelligence.json").write_bytes(
            orjson.dumps(intel.model_dump(), option=orjson.OPT_INDENT_2)
        )
        console.print(f"[green]✓ Discovery complete.[/green] Saved to: {out_dir}")
        console.print(f"  Sitemaps: {len(intel.sitemaps)}")
        console.print(f"  APIs: {len(intel.api_endpoints)}")
        console.print(f"  Protections detected: {[p.name for p in protections if p.detected]}")

    asyncio.run(_discover())


if __name__ == "__main__":
    app()
