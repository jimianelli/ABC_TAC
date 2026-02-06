# Data notes

## File

- `BSAI_OFL_ABC_TAC.csv`

## Contents

This dataset contains BSAI groundfish management quantities by assessment/projection year, including:
- `ABC` (Allowable Biological Catch)
- `TAC` (Total Allowable Catch)
- `OFL` (Overfishing Level)

Key columns used in the analysis:
- `ProjYear`: year the value applies to
- `lag`: whether the record is the value used (lag 1) or a prior projection (lag 2)
- `OY`: indicator used to subset records included in OY-related summaries
- `Species`, `Area`

## Conventions

- `lag = 1`: final values used for that year
- `lag = 2`: two-year projection created the prior year

## Provenance

Add a short note here describing the source (document, query, or workflow) used to assemble the CSV and how/when it should be updated.
