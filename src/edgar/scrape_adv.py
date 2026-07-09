"""SEC Form ADV bulk firm-roster snapshots (Section 3): manager count, RAUM,
and registration dates for every SEC-registered investment adviser,
including CLO managers.

Real historical archive, not a same-day snapshot: config.ADV_BULK_SNAPSHOTS
pins three dated zips (2012, 2018, 2026) spanning 14 years, so
analysis_managers.py gets an actual multi-point consolidation trend on day
one rather than one this project has to accrete daily. Verified 2026-07-09.
"""
from __future__ import annotations

import datetime as dt
import io
import logging
import zipfile

import pandas as pd

import config
from src.common.cache import Provenance, write_parquet
from src.common.http import CachedSession

logger = logging.getLogger("clo_atlas.edgar.scrape_adv")

OUT_PATH = config.INTERIM_DIR / "adv_firm_roster.parquet"

_COLUMNS = {
    "Primary Business Name": "firm_name",
    "Legal Name": "legal_name",
    "SEC#": "sec_number",
    "CRD#": "crd_number",  # some vintages label it differently; handled below
    "Organization CRD#": "crd_number",
    "CIK#": "cik",
    "SEC Current Status": "sec_status",
    "SEC Status Effective Date": "sec_status_date",
    "5F(2)(c)": "raum_discretionary_usd",
    "5F(3)": "raum_total_usd",
}


def _find_data_file_in_zip(zf: zipfile.ZipFile) -> str:
    # Vintage varies: recent snapshots ship a .CSV, older ones (2012, 2018)
    # ship a .xlsx with the same layout.
    names = [n for n in zf.namelist() if n.upper().endswith((".CSV", ".XLSX"))]
    if not names:
        raise ValueError("no CSV or XLSX found in ADV bulk zip")
    return names[0]


def parse_adv_zip(zip_bytes: bytes, snapshot_date: str) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        data_name = _find_data_file_in_zip(zf)
        with zf.open(data_name) as f:
            if data_name.upper().endswith(".CSV"):
                df = pd.read_csv(f, encoding="latin-1", low_memory=False)
            else:
                df = pd.read_excel(f)

    df.columns = [str(c).strip() for c in df.columns]
    available = {src: dst for src, dst in _COLUMNS.items() if src in df.columns}
    tidy = df[list(available.keys())].rename(columns=available)
    tidy = tidy.loc[:, ~tidy.columns.duplicated()]
    tidy["snapshot_date"] = snapshot_date

    for col in ("raum_discretionary_usd", "raum_total_usd"):
        if col in tidy.columns:
            tidy[col] = pd.to_numeric(tidy[col].astype(str).str.replace(",", "").str.strip(), errors="coerce")
    # Vintage files mix types in the same nominally-text column (e.g. a
    # status-date field is a datetime in one snapshot's export and a string
    # in another) — force to string so concatenating snapshots doesn't choke
    # pyarrow at write time.
    text_cols = [c for c in tidy.columns if c not in ("raum_discretionary_usd", "raum_total_usd", "snapshot_date")]
    for col in text_cols:
        tidy[col] = tidy[col].astype(str)
    return tidy


def run() -> pd.DataFrame:
    session = CachedSession()
    frames = []
    for snapshot_date, path in config.ADV_BULK_SNAPSHOTS.items():
        url = f"https://www.sec.gov{path}"
        try:
            result = session.get(url)
        except Exception as exc:
            logger.warning("%s: fetch failed (%s), skipping", snapshot_date, exc)
            continue
        if result.status != 200:
            logger.warning("%s: status %d, skipping", snapshot_date, result.status)
            continue
        try:
            df = parse_adv_zip(result.content, snapshot_date)
        except Exception as exc:
            logger.warning("%s: parse failed (%s), skipping", snapshot_date, exc)
            continue
        frames.append(df)
        logger.info("%s: parsed %d firm records", snapshot_date, len(df))

    if not frames:
        raise RuntimeError("ADV bulk scrape returned nothing for any snapshot")
    combined = pd.concat(frames, ignore_index=True)

    write_parquet(combined, OUT_PATH, Provenance(
        source_urls=[f"https://www.sec.gov{p}" for p in config.ADV_BULK_SNAPSHOTS.values()],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.edgar.scrape_adv",
        notes=f"{len(config.ADV_BULK_SNAPSHOTS)} dated snapshots: {list(config.ADV_BULK_SNAPSHOTS.keys())}",
    ))
    logger.info("wrote %d total firm-snapshot rows to %s", len(combined), OUT_PATH)
    return combined


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
