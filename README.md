# ABC TAC Analyses

Evaluates OFL, ABC (Allowable Biological Catch), and TAC (Total Allowable Catch) harvest specifications for Bering Sea/Aleutian Islands (BSAI) and Gulf of Alaska (GOA) groundfish fisheries. The analysis compares two-year model projections against final values and a naive rollover baseline to assess forecast reliability for fisheries management.

**Published site:** https://jimianelli.github.io/ABC_TAC/

## Repository Structure

- `doc/` — Quarto website source (rendered outputs are *generated*, not committed)
  - `index.qmd` — Main BSAI analysis (interannual variability, two-year projections, DSEM)
  - `stoplight_criteria_framework.qmd` — Stoplight test framework for multispecies model ensemble inclusion
  - `rovellini-goa-oy-cap.qmd` — Technical note on rescaling GOA projected catch to meet OY cap
  - `ref.bib`, `references.bib` — Bibliographies
- `R/` — Exploratory R scripts for data analysis and visualization
- `data/` — Source data files:
  - `BSAI_OFL_ABC_TAC.csv` — BSAI harvest specifications (1986–present)
  - `GOA_OFL_ABC_TAC_specs.csv` — GOA harvest specifications
  - `GOA_OFL_ABC_TAC_2yr.csv` — GOA two-year pilot (2018–2026)
  - `GOA_OFL_ABC_TAC_2yr_full.csv` — GOA full historical scrape (1986–present)
  - `bsai-historic-akro.csv`, `goa-historic-akro.csv` — Historic AKRO data
  - `summary_goa_species_area_by_year_lag.csv` — Aggregated GOA summary
- `scripts/` — Python utilities (Federal Register scraper)

## Publishing

The site renders automatically via GitHub Actions on push to `main` and deploys to GitHub Pages. To render locally:

```bash
cd doc
quarto render
```

This produces the full website in `doc/_site/`. To render a single page:

```bash
cd doc
quarto render index.qmd
```

## Key Analysis Components (`index.qmd`)

- Interannual variability (CV) of ABC/TAC across species
- Two-year vs final value comparisons (percent and absolute changes)
- Rollover baseline comparison
- Log-linear TAC~ABC regressions with cross-species effects
- Dynamic Structural Equation Model (DSEM) for TAC prediction

## Required R Packages

Core: `tidyverse`, `here`, `scales`, `GGally`
Visualization / graphs: `ggthemes`, `ggdag`
Modeling: `dsem`
Tables: `gt`, `knitr`

## Data Structure

The CSV files share columns: `AssmentYr`, `ProjYear`, `lag`, `Area`, `Species`, `ABC`, `OFL`, `TAC`, `OY`, `Order`, `SourceURL`, `SourceType`

- `lag=1`: Final values used that year
- `lag=2`: Two-year projection made the prior year
- `OY=1`: Records included in Optimum Yield calculations
- Seven main species account for ~90% of total BSAI ABC: Pollock, Yellowfin sole, Pacific cod, Atka mackerel, Northern rock sole, Flathead sole, Pacific ocean perch

## GOA Federal Register Scraper

The GOA two-year files are produced by `scripts/scrape_goa_fedreg.py`.

Key behavior:
- Uses Federal Register API for document metadata; falls back to govinfo daily FR XML and FR PDFs for early years.
- Parses GPOTABLE/TABLE content with OFL/ABC/TAC headers and filters to Gulf of Alaska rows.
- Includes an alternate XML parser for older FR XML that uses TABLE blocks.
- Falls back to PDF table extraction when XML/HTML parsing fails.
- Strips footnote markers and normalizes area labels.
- Adds `SourceURL` and `SourceType` (XML/XML_ALT/HTML/PDF).

Dependencies: `pdfplumber` (required only for PDF fallback parsing)

```bash
python scripts/scrape_goa_fedreg.py
```

## Key Metrics

- Percent differences scaled by two-year ABC: `(value_lag1 - value_lag2) / ABC_lag2`
- Absolute percent error for model vs rollover comparisons
- Coefficient of variation for interannual variability
