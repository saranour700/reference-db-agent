# Project Context

## What Is This?

The Reference DB Intelligence Agent is a tool for building the **Reference DB** — a comprehensive, reliable database of Canadian food products.

The Reference DB supplements Open Food Facts (OFF) with higher-quality, verified product data sourced directly from Canadian retailers and brands.

---

## Team

This agent is part of a larger data pipeline:

- **Open DB**: Built on Open Food Facts data.
- **Reference DB**: Built by scraping verified Canadian sources.
- **Matching**: Products are matched between Open DB and Reference DB using product name, size, and barcode/UPC.

---

## Target Sources

Primary Canadian sources:

- **Voila.ca** — Sobeys online grocery (includes Compliments brand products)
- **Sobeys.com** — Canadian grocery chain
- **IGA.net** — Quebec grocery chain
- **Aliments du Québec** — Quebec food products certification body
- **MadeInCA** — Canadian-made products directory

---

## Key Fields

Priority fields for Canadian food products:

| Field | Notes |
|-------|-------|
| `barcode` | GTIN-13 / UPC preferred |
| `product_name` | As printed on package |
| `brand` | As listed on website |
| `categories` | As listed on website |
| `package_size` | e.g. "500g", "1L" |
| `ingredients_raw` | Exact text from website |
| `nutrition_raw` | Exact nutrition table |
| `allergens_raw` | Exact allergen statement |
| `certifications` | e.g. "Organic", "Kosher", "Halal" |
| `image_urls` | Product images |
| `manufacturer` | If listed |

---

## Storage

- Products stored as JSONL in `runs/*/raw_products.jsonl`
- Final datasets uploaded to HuggingFace in Parquet format
- Intelligence artifacts stored in `runs/*/` for reuse

---

## Data Principles

1. **Transparency over completeness** — missing values stay missing
2. **Source fidelity** — data is preserved exactly as found
3. **Reusability** — every discovery is saved for future runs
4. **No normalization** — cleaning happens downstream, not here
