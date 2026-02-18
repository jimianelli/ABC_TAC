# Munge GOA harvest specs Excel into a long CSV comparable to data/BSAI_OFL_ABC_TAC.csv
#
# Input:  data/GOA_harvest specs_1986-2024.xlsx
# Output: data/GOA_OFL_ABC_TAC_specs.csv (default)
#
# Notes / assumptions:
# - The Excel sheet is laid out with:
#     row 1: years (e.g., 2024, 2023, ...)
#     row 2: metric labels (OFL/ABC/TAC) repeated within each year
#     row 3+: data rows
# - This script produces lag=1 records only (final/used values). If you later
#   add projection (lag=2) values, we can extend the format.
# - OY is set to 1 for all records because the GOA spreadsheet does not encode
#   the OY subset used in the BSAI file.
# - AssmentYr is set equal to ProjYear as a placeholder; adjust if you prefer
#   another convention.

suppressPackageStartupMessages({
  library(readxl)
  library(dplyr)
  library(tidyr)
  library(readr)
  library(stringr)
})

in_path <- file.path("data", "GOA_harvest specs_1986-2024.xlsx")

# Optional CLI override:
#   Rscript R/munge_goa_harvest_specs.R data/GOA_OFL_ABC_TAC_specs.csv
args <- commandArgs(trailingOnly = TRUE)
out_path <- if (length(args) >= 1) args[[1]] else file.path("data", "GOA_OFL_ABC_TAC_specs.csv")

sheet <- "GOA harvest specs 1986-present"
raw <- read_excel(in_path, sheet = sheet, col_names = FALSE)

# Row 1 has years; row 2 has metric labels; rows 3+ are data.
years_row  <- raw[1, ] |> unlist(use.names = FALSE)
labels_row <- raw[2, ] |> unlist(use.names = FALSE)

# Helper: coerce numeric-ish strings, tolerate "n/a".
numify <- function(x) {
  if (is.numeric(x)) return(x)
  x <- as.character(x)
  x <- str_replace_all(x, ",", "")
  x <- str_trim(x)
  x[x %in% c("n/a", "na", "N/A", "NA", "")] <- NA_character_
  suppressWarnings(as.numeric(x))
}

# Build a column map for the year blocks.
# Expect columns: 1=Species, 2=Area, then repeating triples OFL/ABC/TAC.
stopifnot(ncol(raw) >= 5)

block_starts <- seq(3, ncol(raw), by = 3)

col_map <- lapply(block_starts, function(j) {
  yr <- years_row[j]
  labs <- labels_row[j:(j + 2)]
  list(
    year = as.integer(yr),
    cols = j:(j + 2),
    labs = as.character(labs)
  )
})

# Drop malformed blocks (e.g., trailing partial columns)
col_map <- Filter(function(b) !any(is.na(b$year)) && length(b$cols) == 3, col_map)

dat <- raw[-c(1, 2), ]

names(dat) <- paste0("V", seq_len(ncol(dat)))

dat <- dat %>%
  transmute(
    Species = as.character(V1),
    Area = as.character(V2),
    across(everything(), ~ .x)
  )

# Fill species down where the spreadsheet uses merged cells
# (Species only appears on the first line of a block).
dat <- dat %>%
  tidyr::fill(Species, .direction = "down")

# Remove empty rows
is_empty_row <- function(x) {
  all(is.na(x) | str_trim(as.character(x)) == "")
}
keep <- apply(dat, 1, function(r) !is_empty_row(r))
dat <- dat[keep, , drop = FALSE]

# Convert each year block into long format and bind
pieces <- lapply(col_map, function(b) {
  j <- b$cols
  # Rebuild a small tibble with standard column names
  tmp <- dat %>%
    transmute(
      Species,
      Area,
      OFL = numify(.data[[paste0("V", j[1])]]),
      ABC = numify(.data[[paste0("V", j[2])]]),
      TAC = numify(.data[[paste0("V", j[3])]])
    ) %>%
    mutate(ProjYear = b$year)
  tmp
})

out <- bind_rows(pieces) %>%
  mutate(
    AssmentYr = ProjYear,
    lag = 1L,
    OY = 1L
  ) %>%
  # Drop rows with no numeric values at all for the year
  filter(!(is.na(OFL) & is.na(ABC) & is.na(TAC)))

# Create a stable species order based on first appearance
species_order <- out %>%
  distinct(Species) %>%
  mutate(Order = row_number())

out <- out %>%
  left_join(species_order, by = "Species") %>%
  select(AssmentYr, ProjYear, lag, Area, Species, ABC, OFL, TAC, OY, Order) %>%
  arrange(ProjYear, Order, Area)

write_csv(out, out_path, na = "")

message("Wrote ", out_path, " (", nrow(out), " rows)")
