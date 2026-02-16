import re
import sys
import json
import time
import io
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

START_YEAR = 1986
END_YEAR = datetime.utcnow().year + 1
PILOT_START = 2018
PILOT_END = 2026

OUT_PATH = "data/GOA_OFL_ABC_TAC_2yr_full.csv"
EXISTING_GOA = "data/GOA_OFL_ABC_TAC.csv"


def fetch_docs(year=None):
    params = {
        "conditions[term]": "harvest specifications",
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
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        docs.extend(data.get("results", []))
        url = data.get("next_page_url")
    return docs


def extract_years(text):
    if not text:
        return None, None
    years = re.findall(r"\b(19\d{2}|20\d{2})\b", text)
    years = [int(y) for y in years]
    if len(years) >= 2:
        years = sorted(list(set(years)))
        if len(years) >= 2:
            return years[0], years[1]
    if len(years) == 1:
        return years[0], years[0]
    return None, None


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
        if "table 1" not in title_l and "table 2" not in title_l:
            continue
        if not any(x in title_l for x in ["ofl", "abc", "tac"]):
            continue
        if require_goa and ("gulf of alaska" not in title_l and "goa" not in title_l):
            continue

        year_match = re.findall(r"\b(19\d{2}|20\d{2})\b", title)
        table_year = int(year_match[0]) if year_match else None

        # headers
        headers = []
        for ched in table.findall(".//BOXHD//CHED"):
            headers.append(" ".join(ched.itertext()).strip())

        if not headers:
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
            if table_year:
                tmp_rows = []
                for _, r in df.iterrows():
                    tmp_rows.append({
                        "ProjYear": table_year,
                        "Species": clean_text(r[headers[0]]),
                        "Area": clean_text(r.get(headers[1], "GOA")) or "GOA",
                        "OFL": r.get("OFL"),
                        "ABC": r.get("ABC"),
                        "TAC": r.get("TAC"),
                    })
                rows.extend(tmp_rows)
            else:
                rows.extend(parse_table(df, year1, year2, allow_single_year=True))
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
        if title and not any(x in title_l for x in ["ofl", "abc", "tac"]):
            continue
        if require_goa and title and ("gulf of alaska" not in title_l and "goa" not in title_l):
            continue

        try:
            html_str = etree.tostring(table, encoding="unicode", method="html")
            tables = pd.read_html(html_str)
        except Exception:
            tables = []

        for tbl in tables:
            rows.extend(parse_table(tbl, year1, year2, allow_single_year=True))

    return rows


def parse_pdf_text_tables(pdf, year1):
    rows = []
    in_table = False
    current_species = None

    for page in pdf.pages:
        text = page.extract_text(layout=True) or ""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines:
            if "TABLE 1" in line.upper() or "TABLE 2" in line.upper():
                in_table = True
                current_species = None
                continue

            if not in_table:
                continue

            if line.upper().startswith("TABLE"):
                continue

            nums = re.findall(r"\b\d{1,3}(?:,\d{3})*\b", line)
            if not nums:
                # species header line
                if re.search(r"[A-Za-z]", line):
                    current_species = clean_text(re.sub(r"\.{2,}.*", "", line))
                continue

            # probable data line
            area = re.sub(r"\.{2,}.*", "", line)
            area = re.sub(r"\s+\(\d+\)$", "", area)
            area = clean_text(area)

            vals = [int(n.replace(",", "")) for n in nums]
            abc = tac = ofl = None
            if len(vals) >= 3:
                abc, tac, ofl = vals[-3], vals[-2], vals[-1]
            elif len(vals) == 2:
                abc, tac = vals[-2], vals[-1]

            if current_species and (abc is not None or tac is not None or ofl is not None):
                rows.append({
                    "ProjYear": year1,
                    "Species": current_species,
                    "Area": area or "GOA",
                    "OFL": ofl,
                    "ABC": abc,
                    "TAC": tac,
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
                rows = parse_pdf_text_tables(pdf, year1)
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


def main():
    order_map = build_order_map()

    all_rows = []
    for year in range(START_YEAR, END_YEAR + 1):
        docs = fetch_docs(year=year)
        for doc in docs:
            title = doc.get("title", "")
            abstract = doc.get("abstract", "") or ""
            text_blob = f"{title} {abstract}"

            title_l = title.lower()
            if "gulf of alaska" not in title_l:
                continue
            if "harvest specification" not in title_l and "groundfish specification" not in title_l:
                continue
            if "interim" in title_l:
                continue

            y1, y2 = extract_years(text_blob)
            if not y1 or not y2:
                pub = doc.get("publication_date")
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
                        tables = pd.read_html(html_text)
                        for tbl in tables:
                            rows.extend(parse_table(tbl, y1, y2, allow_single_year=True))
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
                    all_rows.append(r)
            time.sleep(0.2)

    if not all_rows:
        print("No rows parsed.")
        sys.exit(1)

    out_df = pd.DataFrame(all_rows)
    cols = ["AssmentYr", "ProjYear", "lag", "Species", "Area", "OFL", "ABC", "TAC", "Order", "OY", "IsTotal", "SourceURL", "SourceType"]
    out_df = out_df[cols]

    out_df.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(out_df)} rows to {OUT_PATH}")
    if "SourceType" in out_df.columns:
        counts = out_df["SourceType"].value_counts(dropna=False)
        print("SourceType counts:")
        for k, v in counts.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
