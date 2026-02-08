# REPO_MAP.md

## Repo
- Name: `ABC_TAC`
- Purpose: Evaluate BSAI ABC/TAC projection performance (two-year projections vs final values, plus rollover baseline), with Quarto-based reporting.

## Top-level Structure
- `.github/workflows/publish.yml` — CI pipeline to render and deploy HTML to GitHub Pages
- `doc/` — main Quarto analysis/report sources
- `data/` — input datasets (BSAI + GOA CSVs)
- `R/` — helper/exploratory R scripts
- `README.md` — project overview and run instructions

## Primary Execution Path (CI + Local)
1. Read data from:
   - `data/BSAI_OFL_ABC_TAC.csv`
   - `data/GOA_OFL_ABC_TAC.csv`
2. Render report:
   - `doc/index.qmd`
3. Output:
   - HTML report (CI renders HTML and deploys Pages artifact from `doc/`)

## Key Files and Roles
- `doc/index.qmd`
  - Main analysis pipeline and narrative
  - Includes metrics: CV, projection deltas, rollover comparison, regression sections, DSEM section
- `doc/ref.bib`
  - Bibliography for the Quarto report
- `R/munge_goa_harvest_specs.R`
  - Converts GOA Excel harvest specs into long-format CSV (`data/GOA_OFL_ABC_TAC.csv`)
- `R/Specs_ABC_TAC.R`
  - Exploratory/legacy script with ad hoc plotting and summaries

## Build / Repro Commands
From repo root:
```bash
quarto render doc/index.qmd
```

## CI Workflow Summary
From `.github/workflows/publish.yml`:
- Setup R + package dependencies
- Setup Quarto
- `cd doc && quarto render index.qmd --to html`
- Upload/deploy to GitHub Pages

## Required Inputs for Reproducible Main Report
- `doc/index.qmd`
- `doc/ref.bib`
- `data/BSAI_OFL_ABC_TAC.csv`
- `data/GOA_OFL_ABC_TAC.csv`

## Notes
- Rendered `.html`/`.pdf` are gitignored.
- Repo is analysis-report oriented (not an R package layout).
