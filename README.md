# README.md

## Project Overview

This repository evaluates ABC (Allowable Biological Catch) and TAC (Total Allowable Catch) projections for Bering Sea and Aleutian Islands (BSAI) groundfish fisheries. The analysis compares two-year model projections against final values and a naive rollover baseline to assess forecast reliability for fisheries management.

## Repository Structure

- `doc/` - Main analysis document (Quarto), bibliography, and rendered outputs
- `R/` - Exploratory R scripts for data analysis and visualization
- `data/` - Source data (BSAI_OFL_ABC_TAC.csv with OFL/ABC/TAC records 1986-2025)

## Key Analysis Components

The main analysis (`doc/evaluation-abc-tac-projections.qmd`) uses Quarto with R and covers:
- Interannual variability (CV) of ABC/TAC across species
- Two-year vs final value comparisons (percent and absolute changes)
- Rollover baseline comparison
- Log-linear TAC~ABC regressions with cross-species effects
- Dynamic Structural Equation Model (DSEM) for TAC prediction

## Required R Packages

Core: `tidyverse`, `here`, `scales`, `GGally`
Visualization: `ggthemes`, `ggdag`, `patchwork`, `viridis`, `wesanderson`
Modeling: `dsem`
Tables: `gt`, `knitr`, `flextable`, `YesSiR`

## Rendering the Document

```bash
quarto render doc/evaluation-abc-tac-projections.qmd
```

Outputs both HTML (with embedded resources) and PDF formats.

## Data Structure

The CSV contains columns: `AssmentYr`, `ProjYear`, `lag`, `Area`, `Species`, `ABC`, `OFL`, `TAC`, `OY`, `Order`

- `lag=1`: Final values used that year
- `lag=2`: Two-year projection made the prior year
- `OY=1`: Records included in Optimum Yield calculations
- Seven main species account for ~90% of total ABC: Pollock, Yellowfin sole, Pacific cod, Atka mackerel, Northern rock sole, Flathead sole, Pacific ocean perch

## Key Metrics

- Percent differences scaled by two-year ABC: `(value_lag1 - value_lag2) / ABC_lag2`
- Absolute percent error for model vs rollover comparisons
- Coefficient of variation for interannual variability
