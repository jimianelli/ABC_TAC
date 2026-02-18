# README.md

## Project Overview

This repository evaluates ABC (Allowable Biological Catch) and TAC (Total Allowable Catch) projections for Bering Sea and Aleutian Islands (BSAI) groundfish fisheries. The analysis compares two-year model projections against final values and a naive rollover baseline to assess forecast reliability for fisheries management.

## Repository Structure

- `doc/` - Quarto source document(s) and bibliography (rendered outputs are *generated*, not committed)
- `R/` - Exploratory R scripts for data analysis and visualization
- `data/` - Source data (`BSAI_OFL_ABC_TAC.csv` with OFL/ABC/TAC records 1986–2025)
  - GOA two-year outputs:
    - `GOA_OFL_ABC_TAC_2yr.csv` (pilot, 2018–2026)
    - `GOA_OFL_ABC_TAC_2yr_full.csv` (full scrape, 1986–present)

## Key Analysis Components

The main analysis (`doc/index.qmd`) uses Quarto with R and covers:
- Interannual variability (CV) of ABC/TAC across species
- Two-year vs final value comparisons (percent and absolute changes)
- Rollover baseline comparison
- Log-linear TAC~ABC regressions with cross-species effects
- Dynamic Structural Equation Model (DSEM) for TAC prediction

## Required R Packages

The document loads packages as needed; the GitHub Actions workflow installs the core set.

Core: `tidyverse`, `here`, `scales`, `GGally`
Visualization / graphs: `ggthemes`, `ggdag`
Modeling: `dsem`
Tables: `gt`, `knitr`

## Rendering the Document

```bash
quarto render doc/index.qmd
```

This produces HTML (with embedded resources) and PDF locally. Rendered `.html`/`.pdf` outputs are ignored via `.gitignore` (recommended) and are not committed.

## Data Structure

The CSV contains columns: `AssmentYr`, `ProjYear`, `lag`, `Area`, `Species`, `ABC`, `OFL`, `TAC`, `OY`, `Order`, `SourceURL`, `SourceType`

- `lag=1`: Final values used that year
- `lag=2`: Two-year projection made the prior year
- `OY=1`: Records included in Optimum Yield calculations
- Seven main species account for ~90% of total ABC: Pollock, Yellowfin sole, Pacific cod, Atka mackerel, Northern rock sole, Flathead sole, Pacific ocean perch

## GOA Federal Register Scraper

The GOA two-year files are produced by `scripts/scrape_goa_fedreg.py`.

Key behavior:
- Uses Federal Register API for document metadata; falls back to govinfo daily FR XML and FR PDFs for early years.
- Parses GPOTABLE/TABLE content with OFL/ABC/TAC headers (not limited to Table 1/2) and filters to Gulf of Alaska rows.
- Includes an alternate XML parser for older FR XML that uses TABLE blocks.
- Falls back to PDF table extraction when XML/HTML parsing fails (tables only; single-year tables are accepted).
- Skips interim harvest specifications.
- Strips footnote markers and normalizes area labels.
- Adds `SourceURL` (FR HTML document URL when available) and `SourceType` (XML/XML_ALT/HTML/PDF).

Dependencies:
- `pdfplumber` (required only for PDF fallback parsing)

Run:
```bash
python scripts/scrape_goa_fedreg.py
```

## Key Metrics

- Percent differences scaled by two-year ABC: `(value_lag1 - value_lag2) / ABC_lag2`
- Absolute percent error for model vs rollover comparisons
- Coefficient of variation for interannual variability
