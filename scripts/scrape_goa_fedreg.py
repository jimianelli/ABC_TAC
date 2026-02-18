import re
import sys
import json
import time
import io
import os
import difflib
from datetime import datetime
from urllib.parse import urlencode

import requests
import pandas as pd
from lxml import etree

try:
    import pdfplumber
except Exception:
    pdfplumber = None

BASE = "https://www.federalregister.gov/api/v1/documents.json"

START_YEAR = int(os.getenv("GOA_FR_START_YEAR", "1986"))
END_YEAR = int(os.getenv("GOA_FR_END_YEAR", str(datetime.utcnow().year + 1)))
PILOT_START = 2018
PILOT_END = 2026

OUT_PATH = "data/GOA_OFL_ABC_TAC_2yr_full.csv"
EXISTING_GOA = "data/GOA_OFL_ABC_TAC.csv"

SPECIES_CANON = [
    "Arrowtooth Flounder",
    "Atka Mackerel",
    "Big Skates",
    "Deep-water Flatfish",
    "Demersal Shelf Rockfish",
    "Dusky Rockfish",
    "Flathead Sole",
    "Longnose Skates",
    "Northern Rockfish",
    "Octopus",
    "Other Flounder",
    "Other Rockfish",
    "Other Skates",
    "Other Species",
    "Pacific cod",
    "Pacific Ocean Perch",
    "Pelagic Shelf Rockfish",
    "Pollock",
    "Rex Sole",
    "Rougheye and Blackspotted Rockfish",
    "Sablefish",
    "Sculpins",
    "Shallow-water Flatfish",
    "Sharks",
    "Shortraker Rockfish",
    "Shortraker/Rougheye Rockfish",
    "Squids",
    "Thornyhead Rockfish",
]

AREA_CANON = [
    "610/620",
    "610/620/630 (subtotal)",
    "C",
    "Chirikof (620)",
    "E",
    "E (WYK and SEO subtotal)",
    "GW",
    "Kodiak (630)",
    "SEO",
    "SEO (650)",
    "SEO/EYK",
    "Shelikof",
    "Shumagin (610)",
    "Total",
    "Total (GW)",
    "W",
    "W and C",
    "W/C/WYK",
    "W/C/WYK (subtotal)",
    "W/C/WYK combined",
    "WYK",
    "WYK (640)",
    "WYK/SEO (subtotal)",
    "",
]

SPECIES_CANON_SET = set(SPECIES_CANON)
AREA_CANON_SET = set(AREA_CANON)

BSAI_AREA_TOKENS = {"bs", "ai", "ebs", "bsai", "eai", "cai", "wai"}

SEARCH_TERMS = [
    "harvest specifications",
    "harvest specification",
    "groundfish specifications",
    "groundfish specification",
    "total allowable catch",
    # 2001-2002 combined BSAI+GOA specs were published under Steller Sea
    # Lion protection measures titles; this extra term helps find them.
    "steller sea lion harvest specifications",
]


def get_with_retries(url, timeout=30, retries=4, backoff=1.5):
    """GET with bounded retries; return response or None on repeated failure."""
    for i in range(retries):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp
        except Exception:
            if i == retries - 1:
                return None
            time.sleep(backoff * (i + 1))
    return None


def fetch_docs(year=None, term=None):
    params = {
        "conditions[term]": term or "harvest specifications",
        "conditions[type]": "RULE",
        "per_page": 100,
        "order": "oldest",
    }
    if year:
        params["conditions[publication_date][gte]"] = f"{year}-01-01"
        params["conditions[publication_date][lte]"] = f"{year}-12-31"
    else:
        params["conditions[publication_date][gte]"] = f"{START_YEAR}-01-01"

    url = f"{BASE}?{urlencode(params)}"
    docs = []
    while url:
        resp = get_with_retries(url, timeout=30, retries=4, backoff=1.0)
        if resp is None:
            print(f"Warning: fetch_docs failed for URL: {url}")
            break
        data = resp.json()
        docs.extend(data.get("results", []))
        url = data.get("next_page_url")
    return docs


def _choose_year_pair(years, pub_year=None):
    years = sorted(set(int(y) for y in years))
    if not years:
        return None, None
    if len(years) == 1:
        return years[0], years[0]

    consecutive = [(a, b) for a, b in zip(years, years[1:]) if b - a == 1]
    if consecutive:
        if pub_year is not None:
            consecutive = sorted(consecutive, key=lambda p: (abs(p[0] - pub_year), p[0]))
            return consecutive[0]
        return consecutive[0]

    # Fallback when no adjacent pair appears.
    if pub_year is not None:
        near = sorted(years, key=lambda y: (abs(y - pub_year), y))[:2]
        near = sorted(near)
        return near[0], near[1]
    return years[0], years[1]


def extract_years(title, abstract=None, pub_year=None):
    title = title or ""
    abstract = abstract or ""

    # Prefer explicit "YYYY and YYYY harvest specifications" phrase in title.
    m = re.search(
        r"\b(19\d{2}|20\d{2})\s*(?:and|&|/|-)\s*(19\d{2}|20\d{2})\s+harvest specifications\b",
        title,
        flags=re.IGNORECASE,
    )
    if m:
        y1, y2 = int(m.group(1)), int(m.group(2))
        return (y1, y2) if y1 <= y2 else (y2, y1)

    # Single-year title style (more common in older rules).
    m1 = re.search(
        r"\b(19\d{2}|20\d{2})\s+harvest specifications\b",
        title,
        flags=re.IGNORECASE,
    )
    if m1:
        y = int(m1.group(1))
        return y, y

    # Next best: infer from title years near publication year.
    title_years = re.findall(r"\b(19\d{2}|20\d{2})\b", title)
    y1, y2 = _choose_year_pair(title_years, pub_year=pub_year)
    if y1 is not None:
        return y1, y2

    # Last resort: include abstract years (can be noisy, so done last).
    blob_years = re.findall(r"\b(19\d{2}|20\d{2})\b", f"{title} {abstract}")
    return _choose_year_pair(blob_years, pub_year=pub_year)


def normalize_columns(df):
    df = df.copy()
    df.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in df.columns]
    return df


def clean_text(x):
    if x is None:
        return x
    s = str(x)
    s = s.replace("â", " ").replace("â", " ")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s*\d+$", "", s).strip()
    return s


def _norm_key(x):
    s = clean_text(x) or ""
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_species(name, cutoff=0.85):
    canon, matched = canonicalize_species(name, cutoff=cutoff)
    return canon if matched else name


def canonicalize_species(name, cutoff=0.85):
    if name is None:
        return name, False
    key = _norm_key(name)
    if key == "":
        return name, False

    canon_keys = {_norm_key(c): c for c in SPECIES_CANON}
    if key in canon_keys:
        return canon_keys[key], True

    # handle common connectors
    key = key.replace(" and ", " ").replace("/", " ")

    matches = difflib.get_close_matches(key, canon_keys.keys(), n=1, cutoff=cutoff)
    if matches:
        return canon_keys[matches[0]], True

    return name, False


def normalize_area(area, cutoff=0.8):
    if area is None:
        return area
    key = _norm_key(area)
    if key == "":
        return ""

    canon_keys = {_norm_key(c): c for c in AREA_CANON}
    if key in canon_keys:
        return canon_keys[key]

    # try digit-based mapping
    if "610" in key and "620" in key and "630" in key:
        return "610/620/630 (subtotal)"
    if "610" in key and "620" in key:
        return "610/620"
    if "630" in key:
        return "Kodiak (630)"
    if "620" in key:
        return "Chirikof (620)"
    if "610" in key:
        return "Shumagin (610)"
    if "640" in key:
        return "WYK (640)"
    if "650" in key:
        return "SEO (650)"
    if "shumagin" in key:
        return "Shumagin (610)"
    if "chirikof" in key:
        return "Chirikof (620)"
    if "kodiak" in key:
        return "Kodiak (630)"
    if key in {"wyk", "west yakutat"}:
        return "WYK (640)"
    if key in {"seo", "seq", "southeast outside"}:
        return "SEO (650)"

    matches = difflib.get_close_matches(key, canon_keys.keys(), n=1, cutoff=cutoff)
    if matches:
        return canon_keys[matches[0]]

    return ""


def is_probably_goa_area(area):
    """Heuristic filter to keep GOA rows in combined BSAI+GOA tables."""
    key = _norm_key(area or "")
    if key == "":
        return True
    tokens = set(key.split())
    if tokens & BSAI_AREA_TOKENS:
        return False
    if "total" in tokens:
        return True
    # GOA area cues used in FR tables.
    goa_hints = [
        "goa", "gulf of alaska", "610", "620", "630", "640", "650",
        "shumagin", "chirikof", "kodiak", "shelikof", "wyk", "seo",
        "gw", "w c wyk", "w c wyk combined", "w and c",
    ]
    return any(h in key for h in goa_hints)


def parse_table(df, year1, year2, allow_single_year=False):
    df = normalize_columns(df)
    col_map = {}
    for col in df.columns:
        m = re.search(r"(19\d{2}|20\d{2})", str(col))
        if not m:
            continue
        yr = int(m.group(1))
        tag = None
        if "OFL" in str(col).upper():
            tag = "OFL"
        elif "ABC" in str(col).upper():
            tag = "ABC"
        elif "TAC" in str(col).upper():
            tag = "TAC"
        if tag and yr in (year1, year2):
            col_map.setdefault(yr, {})[tag] = col

    if not col_map and allow_single_year:
        # Try headers without explicit year; map OFL/ABC/TAC to year1.
        for col in df.columns:
            tag = None
            if "OFL" in str(col).upper():
                tag = "OFL"
            elif "ABC" in str(col).upper():
                tag = "ABC"
            elif "TAC" in str(col).upper():
                tag = "TAC"
            if tag:
                col_map.setdefault(year1, {})[tag] = col

    if not col_map:
        return []

    # Identify species/area columns
    species_col = None
    area_col = None
    for col in df.columns:
        u = str(col).upper()
        if species_col is None and "SPECIES" in u:
            species_col = col
        if area_col is None and ("AREA" in u or "REGION" in u):
            area_col = col

    if species_col is None:
        return []

    rows = []
    for _, row in df.iterrows():
        species = clean_text(row.get(species_col))
        if pd.isna(species) or str(species).strip() == "":
            continue
        area = clean_text(row.get(area_col)) if area_col else "GOA"
        species, matched = canonicalize_species(species)
        if not matched:
            continue
        area = normalize_area(area)

        for yr in (year1, year2):
            if yr not in col_map:
                continue
            ofl_col = col_map[yr].get("OFL")
            abc_col = col_map[yr].get("ABC")
            tac_col = col_map[yr].get("TAC")
            ofl = row.get(ofl_col) if ofl_col else None
            abc = row.get(abc_col) if abc_col else None
            tac = row.get(tac_col) if tac_col else None
            if all(pd.isna(x) for x in [ofl, abc, tac]):
                continue
            rows.append({
                "ProjYear": yr,
                "Species": str(species).strip(),
                "Area": str(area).strip() if not pd.isna(area) else "GOA",
                "OFL": ofl,
                "ABC": abc,
                "TAC": tac,
            })
    return rows


def parse_xml_tables(xml_text, year1, year2, require_goa=True):
    rows = []
    try:
        root = etree.fromstring(xml_text.encode("utf-8"))
    except Exception:
        return rows

    for table in root.findall(".//GPOTABLE"):
        title_el = table.find("TTITLE")
        title = "".join(title_el.itertext()).strip() if title_el is not None else ""
        title_l = title.lower()
        # Older combined rules may place GOA specs in table numbers > 2.
        # Keep any table that appears to carry OFL/ABC/TAC content.
        if not any(x in title_l for x in ["ofl", "abc", "tac", "harvest specification"]):
            # Fall back to headers check below.
            pass

        year_match = re.findall(r"\b(19\d{2}|20\d{2})\b", title)
        table_year = int(year_match[0]) if year_match else None

        # headers
        headers = []
        for ched in table.findall(".//BOXHD//CHED"):
            headers.append(" ".join(ched.itertext()).strip())

        if not headers:
            continue
        header_blob = " ".join(headers).lower()
        if not any(x in header_blob for x in ["ofl", "abc", "tac"]):
            # Not a harvest spec data table.
            continue

        prev_species = None
        for row in table.findall(".//ROW"):
            ents = [" ".join(ent.itertext()).strip() for ent in row.findall(".//ENT")]
            if not ents or all(e == "" for e in ents):
                continue
            if len(ents) < 2:
                continue
            row_dict = dict(zip(headers[: len(ents)], ents))

            # carry forward species if blank or separator
            sp_val = clean_text(row_dict.get(headers[0], ""))
            sp_val_clean = sp_val
            if sp_val_clean == "" or sp_val_clean == "-":
                sp_val_clean = prev_species
            else:
                prev_species = sp_val_clean
            row_dict[headers[0]] = sp_val_clean

            df = pd.DataFrame([row_dict])
            # First try the generic parser, which can map explicit year
            # columns (e.g., "2003 OFL", "2004 ABC", etc.).
            parsed_rows = parse_table(df, year1, year2, allow_single_year=True)
            if parsed_rows:
                rows.extend(parsed_rows)
                continue

            # Fallback for single-year rows with plain OFL/ABC/TAC headers.
            if table_year:
                for _, r in df.iterrows():
                    sp_canon, matched = canonicalize_species(clean_text(r[headers[0]]))
                    if not matched:
                        continue
                    rows.append({
                        "ProjYear": table_year,
                        "Species": sp_canon,
                        "Area": normalize_area(clean_text(r.get(headers[1], "GOA")) or "GOA"),
                        "OFL": r.get("OFL"),
                        "ABC": r.get("ABC"),
                        "TAC": r.get("TAC"),
                    })

        if require_goa and rows:
            rows = [r for r in rows if is_probably_goa_area(r.get("Area", ""))]
    return rows


def parse_xml_tables_alt(xml_text, year1, year2, require_goa=True):
    rows = []
    try:
        root = etree.fromstring(xml_text.encode("utf-8"))
    except Exception:
        return rows

    for table in root.findall(".//TABLE"):
        title_el = table.find("TITLE")
        title = "".join(title_el.itertext()).strip() if title_el is not None else ""
        title_l = title.lower()
        if title and not any(x in title_l for x in ["ofl", "abc", "tac", "harvest specification"]):
            continue

        try:
            html_str = etree.tostring(table, encoding="unicode", method="html")
            tables = pd.read_html(html_str)
        except Exception:
            tables = []

        for tbl in tables:
            rows.extend(parse_table(tbl, year1, year2, allow_single_year=True))

    if require_goa and rows:
        rows = [r for r in rows if is_probably_goa_area(r.get("Area", ""))]

    return rows


def parse_pdf_text_tables(pdf, year1, year2=None):
    area_norm_set = {_norm_key(a) for a in AREA_CANON if a is not None}

    def is_area_like(text):
        k = _norm_key(text or "")
        if not k:
            return False
        if k in area_norm_set:
            return True
        # Common compact area rows in FR tables.
        short_tokens = {"w", "c", "e", "wyk", "seo", "total", "subtotal", "goa"}
        toks = set(k.split())
        if toks and toks.issubset(short_tokens):
            return True
        hints = [
            "shumagin", "chirikof", "kodiak",
            "wyk", "seo", "w c wyk", "w and c",
            "subtotal", "total",
        ]
        return any(h in k for h in hints)

    def split_species_area(text, current_species=None):
        s = clean_text(text) or ""
        # Remove footnote digits attached to words (e.g., Pollock2).
        s = re.sub(r"(?<=[A-Za-z])\d+\b", "", s).strip()
        s = re.sub(r"\bn/?a\b", "", s, flags=re.IGNORECASE).strip()
        if not s:
            return None, None

        s_norm = _norm_key(s)
        for sp in sorted(SPECIES_CANON, key=len, reverse=True):
            sp_norm = _norm_key(sp)
            if s_norm.startswith(sp_norm):
                # Remove the matched species prefix from the original string.
                m = re.match(re.escape(sp), s, flags=re.IGNORECASE)
                if m:
                    area = s[m.end():].strip()
                else:
                    # Fallback: try canonicalized split via normalized prefix length.
                    area = s
                return sp, area

        sp_canon, matched = canonicalize_species(s)
        if matched:
            return sp_canon, ""
        if current_species is not None and is_area_like(s):
            return current_species, s
        return None, None

    # Pass 1: parse modern table-like PDF text where rows look like
    # "Species Area OFL ABC TAC" (often with OCR artifacts).
    rows = []
    in_table = False
    current_species = None
    current_proj_year = year1
    for page in pdf.pages:
        text = page.extract_text(layout=True) or page.extract_text() or ""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines:
            u = line.upper()
            tm = re.search(r"\bTABLE\s*([12])\b", u)
            if tm:
                in_table = True
                current_species = None
                tnum = tm.group(1)
                if tnum == "1":
                    current_proj_year = year1
                elif tnum == "2":
                    current_proj_year = year2 if year2 is not None else year1
                continue
            if not in_table:
                continue
            if "BILLING CODE" in u:
                in_table = False
                current_species = None
                continue
            if (
                "FEDERAL REGISTER/VOL" in u
                or u.startswith("VERDATE")
            ):
                continue
            if re.search(r"\bSPECIES\b.*\bABC\b.*\bTAC\b", u):
                continue
            if re.fullmatch(r"n/?a", line, flags=re.IGNORECASE):
                continue

            # Keep numeric content intact; clean_text() trims trailing digits
            # for footnote markers, which is too aggressive for table rows.
            line_clean = str(line).replace("â", " ").replace("â", " ")
            line_clean = re.sub(r"\s+", " ", line_clean).strip()
            line_no_codes = re.sub(r"\(\s*\d{3}\s*\)", "", line_clean)
            nums = re.findall(r"\b\d{1,3}(?:,\d{3})*\b", line_no_codes)
            if len(nums) < 2:
                # May be a species-only line in wrapped layouts.
                sp_tmp, _ = split_species_area(line_no_codes, current_species=current_species)
                if sp_tmp is not None and sp_tmp in SPECIES_CANON_SET:
                    current_species = sp_tmp
                continue

            # Text before the trailing numeric block is species+area text.
            lead = re.sub(r"(?:\s+\d{1,3}(?:,\d{3})*)+\s*$", "", line_no_codes).strip()
            if not lead:
                continue
            species, area_txt = split_species_area(lead, current_species=current_species)
            if species is None or species not in SPECIES_CANON_SET:
                continue
            if area_txt and not is_area_like(area_txt):
                # Guard against parsing narrative lines while a species context
                # is still active from previous rows.
                continue
            current_species = species
            area = normalize_area(area_txt or "GOA")

            vals = [int(n.replace(",", "")) for n in nums]
            ofl = abc = tac = None
            if len(vals) >= 3:
                ofl, abc, tac = vals[-3], vals[-2], vals[-1]
            elif len(vals) == 2:
                abc, tac = vals[-2], vals[-1]

            if abc is None and tac is None and ofl is None:
                continue
            rows.append({
                "ProjYear": current_proj_year,
                "Species": species,
                "Area": area,
                "OFL": ofl,
                "ABC": abc,
                "TAC": tac,
                "FromPDFText": True,
            })

    if rows:
        return rows

    # Pass 2: legacy dotted-leader parser used by older PDF layouts.
    rows = []
    in_table = False
    current_species = None

    current_proj_year = year1
    for page in pdf.pages:
        text = page.extract_text(layout=True) or ""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines:
            tm = re.search(r"\bTABLE\s*([12])\b", line.upper())
            if tm:
                in_table = True
                current_species = None
                tnum = tm.group(1)
                if tnum == "1":
                    current_proj_year = year1
                elif tnum == "2":
                    current_proj_year = year2 if year2 is not None else year1
                continue

            if not in_table:
                continue

            if line.upper().startswith("TABLE"):
                continue

            # Remove area codes like "(610)" before extracting numeric columns.
            line_clean = re.sub(r"\(\s*\d{3}\s*\)", "", line)
            nums = re.findall(r"\b\d{1,3}(?:,\d{3})*\b", line_clean)
            if not nums:
                # species header line
                if re.search(r"[A-Za-z]", line):
                    sp_raw = clean_text(re.sub(r"\.{2,}.*", "", line))
                    sp_canon, matched = canonicalize_species(sp_raw)
                    current_species = sp_canon if matched else None
                continue

            # probable data line: require dotted leader or area code
            if not (re.search(r"\.{2,}", line) or re.search(r"\(\d+\)", line)):
                continue

            if len(nums) < 2:
                continue

            area = re.sub(r"\.{2,}.*", "", line_clean)
            area = re.sub(r"\s+\(\d+\)$", "", area)
            area = clean_text(area)

            vals = [int(n.replace(",", "")) for n in nums]
            abc = tac = ofl = None
            if len(vals) >= 3:
                # Standard harvest-spec column order is OFL, ABC, TAC.
                ofl, abc, tac = vals[-3], vals[-2], vals[-1]
            elif len(vals) == 2:
                abc, tac = vals[-2], vals[-1]

            if current_species and (abc is not None or tac is not None or ofl is not None):
                rows.append({
                    "ProjYear": current_proj_year,
                    "Species": current_species,
                    "Area": normalize_area(area or "GOA"),
                    "OFL": ofl,
                    "ABC": abc,
                    "TAC": tac,
                    "FromPDFText": True,
                })

    return rows


def parse_pdf_tables(pdf_url, year1, year2, require_goa=True):
    if pdfplumber is None:
        return []

    try:
        resp = requests.get(pdf_url, timeout=30)
        resp.raise_for_status()
    except Exception:
        return []

    rows = []
    try:
        with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables() or []
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    header = table[0]
                    data = table[1:]
                    df = pd.DataFrame(data, columns=header)
                    rows.extend(parse_table(df, year1, year2, allow_single_year=True))

            if not rows:
                rows = parse_pdf_text_tables(pdf, year1, year2=year2)
    except Exception:
        return rows

    return rows


def build_order_map():
    try:
        df = pd.read_csv(EXISTING_GOA)
        return df.groupby("Species")["Order"].first().to_dict()
    except Exception:
        return {}


def fetch_govinfo_xml(pub_date):
    try:
        url = f"https://www.govinfo.gov/content/pkg/FR-{pub_date}/xml/FR-{pub_date}.xml"
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            return resp.text
    except Exception:
        return None
    return None


# Known FR document numbers for combined BSAI+GOA or hard-to-find GOA
# harvest spec rules that the API search may miss.  Keyed by the
# *publication year* so they are injected into the correct loop iteration.
# Each entry is a document_number string.
KNOWN_DOCS_BY_PUB_YEAR = {
    # 2001 final harvest specs (emergency rule, combined BSAI+GOA under
    # Steller sea lion protection measures).  Published 2001-01-22 as
    # 66 FR 7276; amended 2001-03-29 (01-7668) and 2001-07-17 (01-17850).
    2001: ["01-1213", "01-7668", "01-17850"],
    # 2002 final harvest specs (emergency rule, combined BSAI+GOA).
    # Published 2002-01-08 (01-32251); amended 2002-05-16 (02-12179).
    2002: ["01-32251", "02-12179"],
    # 2003 final GOA harvest specs (published ~2003-03; proposed 02-31368).
    2003: ["03-4103"],
    # 2004 final GOA harvest specs (published 2004-02-27, doc 04-4370).
    2004: ["04-4370"],
}


def main():
    order_map = build_order_map()

    all_rows = []
    for year in range(START_YEAR, END_YEAR + 1):
        year_before = len(all_rows)
        docs = []
        seen = set()
        for term in SEARCH_TERMS:
            for doc in fetch_docs(year=year, term=term):
                key = doc.get("document_number") or doc.get("id") or doc.get("html_url")
                if key in seen:
                    continue
                seen.add(key)
                docs.append(doc)

        # Inject known hard-to-find documents for this publication year.
        for doc_num in KNOWN_DOCS_BY_PUB_YEAR.get(year, []):
            if doc_num in seen:
                continue
            try:
                resp = requests.get(
                    f"https://www.federalregister.gov/api/v1/documents/{doc_num}.json",
                    timeout=30,
                )
                if resp.status_code == 200:
                    doc = resp.json()
                    seen.add(doc_num)
                    docs.append(doc)
            except Exception:
                pass

        for doc in docs:
            title = doc.get("title", "")
            abstract = doc.get("abstract", "") or ""
            text_blob = f"{title} {abstract}"

            title_l = title.lower()
            blob_l = text_blob.lower()

            # Accept documents that are either:
            # (a) GOA-specific harvest specs (post-~2005 pattern), or
            # (b) combined BSAI+GOA harvest specs (2001-2004 pattern,
            #     e.g. "Steller Sea Lion Protection Measures ... Final 2001
            #     Harvest Specifications ... Groundfish Fisheries Off Alaska")
            is_goa_specific = "gulf of alaska" in title_l
            is_combined_alaska = (
                "groundfish fisheries off alaska" in title_l
                or "groundfish fisheries off alaska" in blob_l
            )
            has_harvest_spec = (
                "harvest specification" in title_l
                or "groundfish specification" in title_l
                or "harvest specification" in blob_l
            )

            is_known_doc = doc.get("document_number") in set(KNOWN_DOCS_BY_PUB_YEAR.get(year, []))

            if not (is_goa_specific or is_combined_alaska or is_known_doc):
                continue
            if not has_harvest_spec and not is_known_doc:
                continue
            if "interim" in title_l:
                continue

            pub = doc.get("publication_date")
            pub_year = None
            if pub:
                try:
                    pub_year = int(pub.split("-")[0])
                except Exception:
                    pub_year = None

            y1, y2 = extract_years(title, abstract, pub_year=pub_year)
            if not y1 or not y2:
                if pub:
                    try:
                        y1 = int(pub.split("-")[0])
                        y2 = y1 + 1
                    except Exception:
                        y1, y2 = None, None
            if not y1 or not y2:
                continue

            doc_num = doc.get("document_number")
            detail = None
            if doc_num:
                try:
                    detail = requests.get(f"https://www.federalregister.gov/api/v1/documents/{doc_num}.json", timeout=30).json()
                except Exception:
                    detail = None

            html_url = (detail or {}).get("html_url") or doc.get("html_url")
            xml_url = (detail or {}).get("full_text_xml_url") or doc.get("full_text_xml_url")
            pdf_url = (detail or {}).get("pdf_url") or doc.get("pdf_url")

            parsed = False
            rows = []
            source_url = None
            source_type = None
            if xml_url:
                try:
                    xml_text = requests.get(xml_url, timeout=30).text
                    if "Request Access" not in xml_text:
                        rows = parse_xml_tables(xml_text, y1, y2)
                        if rows:
                            parsed = True
                            source_url = html_url or xml_url
                            source_type = "XML"
                        else:
                            rows = parse_xml_tables_alt(xml_text, y1, y2, require_goa=True)
                            if rows:
                                parsed = True
                                source_url = html_url or xml_url
                                source_type = "XML_ALT"
                except Exception:
                    rows = []

            if not parsed and html_url:
                try:
                    html_text = requests.get(html_url, timeout=30).text
                    if "Request Access" not in html_text:
                        # For combined BSAI+GOA documents, only keep tables
                        # that appear in GOA sections.  We check the HTML for
                        # "Gulf of Alaska" near each table as a heuristic.
                        html_lower = html_text.lower()
                        is_combined = is_combined_alaska and not is_goa_specific
                        if is_combined and "gulf of alaska" not in html_lower:
                            # Document body doesn't mention GOA at all — skip.
                            pass
                        else:
                            tables = pd.read_html(html_text)
                            for tbl in tables:
                                rows.extend(parse_table(tbl, y1, y2, allow_single_year=True))
                        if rows and is_combined:
                            # Filter to rows whose Area looks like a GOA area
                            # (not BSAI codes like BS, AI, EBS, BSAI).
                            bsai_areas = {"BS", "AI", "EBS", "BSAI", "EAI", "CAI", "WAI"}
                            rows = [r for r in rows
                                    if r.get("Area", "").upper() not in bsai_areas]
                        if rows:
                            parsed = True
                            source_url = html_url
                            source_type = "HTML"
                except Exception:
                    rows = []

            if not parsed:
                pub = doc.get("publication_date")
                if pub:
                    gov_xml = fetch_govinfo_xml(pub)
                    if gov_xml:
                        rows = parse_xml_tables(gov_xml, y1, y2, require_goa=True)
                        if rows:
                            parsed = True
                            source_url = html_url or f"https://www.govinfo.gov/content/pkg/FR-{pub}/html/FR-{pub}.htm"
                            source_type = "XML"
                        else:
                            rows = parse_xml_tables_alt(gov_xml, y1, y2, require_goa=True)
                            if rows:
                                parsed = True
                                source_url = html_url or f"https://www.govinfo.gov/content/pkg/FR-{pub}/html/FR-{pub}.htm"
                                source_type = "XML_ALT"

            if not parsed:
                pub = doc.get("publication_date")
                doc_num = doc.get("document_number")
                if not pdf_url and pub and doc_num:
                    pdf_url = f"https://www.govinfo.gov/content/pkg/FR-{pub}/pdf/{doc_num}.pdf"
                if pdf_url:
                    rows = parse_pdf_tables(pdf_url, y1, y2, require_goa=True)
                    if rows:
                        parsed = True
                        source_url = html_url or pdf_url
                        source_type = "PDF"

            if rows:
                for r in rows:
                    r["AssmentYr"] = y1
                    r["lag"] = 1 if r["ProjYear"] == y1 else 2
                    r["OY"] = 1
                    r["Order"] = order_map.get(r["Species"], None)
                    r["IsTotal"] = f"{r['Species']}{re.sub(r'[^A-Za-z0-9]+', '', str(r['Area']))}"
                    r["SourceURL"] = html_url or source_url
                    r["SourceType"] = source_type
                    r["FromPDFText"] = bool(r.get("FromPDFText", False))
                    all_rows.append(r)
            time.sleep(0.2)
        year_added = len(all_rows) - year_before
        print(f"[{year}] docs={len(docs)} rows_added={year_added}")

    if not all_rows:
        print("No rows parsed.")
        sys.exit(1)

    out_df = pd.DataFrame(all_rows)
    out_df = out_df[out_df["Species"].isin(SPECIES_CANON_SET)]
    cols = ["AssmentYr", "ProjYear", "lag", "Species", "Area", "OFL", "ABC", "TAC", "Order", "OY", "IsTotal", "SourceURL", "SourceType", "FromPDFText"]
    out_df = out_df[cols]

    # Remove exact duplicate data rows generated from overlapping document
    # sources/corrections.
    dedup_key = ["AssmentYr", "ProjYear", "lag", "Species", "Area", "OFL", "ABC", "TAC"]
    out_df = out_df.drop_duplicates(subset=dedup_key, keep="first").copy()

    # Normalize numeric harvest fields and enforce biological ordering:
    # OFL >= ABC >= TAC when those values are available.
    def to_num(series):
        s = series.astype(str).str.replace(",", "", regex=False).str.strip()
        s = s.replace({"": pd.NA, "na": pd.NA, "n/a": pd.NA, "N/A": pd.NA, "None": pd.NA, "nan": pd.NA})
        return pd.to_numeric(s, errors="coerce")

    ofl_n = to_num(out_df["OFL"])
    abc_n = to_num(out_df["ABC"])
    tac_n = to_num(out_df["TAC"])

    out_df["_OFL_num"] = ofl_n
    out_df["_ABC_num"] = abc_n
    out_df["_TAC_num"] = tac_n

    # Backfill missing Area == "Total" rows by species-year-lag from
    # area-level components when totals are absent.
    leaf_areas = {
        "W", "C", "E", "WYK", "SEO",
        "Shumagin (610)", "Chirikof (620)", "Kodiak (630)",
        "WYK (640)", "SEO (650)"
    }
    derived_rows = []
    grp_cols = ["AssmentYr", "ProjYear", "lag", "Species", "OY"]
    for keys, g in out_df.groupby(grp_cols, dropna=False):
        areas = g["Area"].fillna("").astype(str).str.strip()
        has_total = areas.str.startswith("Total").any()
        if has_total:
            continue

        candidates = g.loc[
            (areas != "")
            & (~areas.str.startswith("Total"))
            & (~areas.str.contains("subtotal", case=False, regex=True))
        ].copy()
        if candidates.empty:
            continue

        leaf = candidates[candidates["Area"].isin(leaf_areas)]
        use_rows = leaf if not leaf.empty else candidates

        ofl_sum = use_rows["_OFL_num"].sum(min_count=1)
        abc_sum = use_rows["_ABC_num"].sum(min_count=1)
        tac_sum = use_rows["_TAC_num"].sum(min_count=1)
        if pd.isna(ofl_sum) and pd.isna(abc_sum) and pd.isna(tac_sum):
            continue

        first = use_rows.iloc[0]
        row = {
            "AssmentYr": keys[0],
            "ProjYear": keys[1],
            "lag": keys[2],
            "Species": keys[3],
            "Area": "Total",
            "OFL": first.get("OFL"),
            "ABC": first.get("ABC"),
            "TAC": first.get("TAC"),
            "Order": first.get("Order"),
            "OY": keys[4],
            "IsTotal": f"{keys[3]}Total",
            "SourceURL": first.get("SourceURL"),
            "SourceType": "DERIVED_TOTAL",
            "FromPDFText": False,
            "_OFL_num": ofl_sum,
            "_ABC_num": abc_sum,
            "_TAC_num": tac_sum,
        }
        derived_rows.append(row)

    if derived_rows:
        out_df = pd.concat([out_df, pd.DataFrame(derived_rows)], ignore_index=True, sort=False)
        # Keep one row per key-area after adding derived totals.
        out_df = out_df.drop_duplicates(subset=dedup_key, keep="first").copy()

    tac_hi = tac_n.notna() & abc_n.notna() & (tac_n > abc_n)
    # Recompute numeric vectors after derived rows were appended.
    ofl_n = out_df["_OFL_num"].copy()
    abc_n = out_df["_ABC_num"].copy()
    tac_n = out_df["_TAC_num"].copy()

    tac_hi = tac_n.notna() & abc_n.notna() & (tac_n > abc_n)
    if tac_hi.any():
        tac_n.loc[tac_hi] = abc_n.loc[tac_hi]

    ofl_lo = ofl_n.notna() & abc_n.notna() & (ofl_n < abc_n)
    if ofl_lo.any():
        ofl_n.loc[ofl_lo] = abc_n.loc[ofl_lo]

    # Keep NA where values are unavailable.
    out_df["OFL"] = ofl_n.round().astype("Int64")
    out_df["ABC"] = abc_n.round().astype("Int64")
    out_df["TAC"] = tac_n.round().astype("Int64")
    out_df = out_df.drop(columns=["_OFL_num", "_ABC_num", "_TAC_num"])

    out_df.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(out_df)} rows to {OUT_PATH}")
    if "SourceType" in out_df.columns:
        counts = out_df["SourceType"].value_counts(dropna=False)
        print("SourceType counts:")
        for k, v in counts.items():
            print(f"  {k}: {v}")
    if "AssmentYr" in out_df.columns:
        years = sorted(out_df["AssmentYr"].dropna().astype(int).unique())
        expected = set(range(START_YEAR, END_YEAR + 1))
        missing = sorted(expected - set(years))
        print(f"Assessment years in output: {years[0]}-{years[-1]} ({len(years)} years)")
        if missing:
            print("Missing assessment years in requested range:")
            print("  " + ", ".join(str(y) for y in missing))


if __name__ == "__main__":
    main()
