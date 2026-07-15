"""Shared NPORT-P XML fetch/parse logic, used by both Section 2 (CLO CEFs)
and Section 3 (bank-loan funds holding CLO tranches). Verified 2026-07-09
against ECC's (CIK 1604174) filings.

CLO-tranche positions are identified by `assetCat == "ABS-CBDO"` (the NPORT
asset-category code funds use for CLO/CBDO securities), falling back to a
name/title regex for filers that leave assetCat blank (verified: OXLC's
NPORT-P does this for securities ECC would tag ABS-CBDO). Every row is
tagged with which method found it so downstream analysis can weight
confidence.
"""
from __future__ import annotations

import logging
import re

import pandas as pd

from src.common.http import CachedSession

logger = logging.getLogger("clo_atlas.common.nport")

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:0>10}.json"
FILING_DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{doc}"

_INVSTORSEC_PATTERN = re.compile(r"<invstOrSec>(.*?)</invstOrSec>", re.DOTALL)
_TAG_PATTERNS = {
    "name": re.compile(r"<name>(.*?)</name>"),
    "title": re.compile(r"<title>(.*?)</title>"),
    "cusip": re.compile(r"<cusip>(.*?)</cusip>"),
    "balance": re.compile(r"<balance>(.*?)</balance>"),
    "valUSD": re.compile(r"<valUSD>(.*?)</valUSD>"),
    "pctVal": re.compile(r"<pctVal>(.*?)</pctVal>"),
    "assetCat": re.compile(r"<assetCat>(.*?)</assetCat>"),
    "invCountry": re.compile(r"<invCountry>(.*?)</invCountry>"),
    "maturityDt": re.compile(r"<maturityDt>(.*?)</maturityDt>"),
    "couponKind": re.compile(r"<couponKind>(.*?)</couponKind>"),
    "annualizedRt": re.compile(r"<annualizedRt>(.*?)</annualizedRt>"),
}
_PERIOD_PATTERN = re.compile(r"<repPdDate>(.*?)</repPdDate>")
_NET_ASSETS_PATTERN = re.compile(r"<netAssets>(.*?)</netAssets>")

CLO_ASSET_CATEGORIES = {"ABS-CBDO"}
_CLO_NAME_PATTERN = re.compile(r"\bCLO\b", re.IGNORECASE)


def list_nport_filings(session: CachedSession, cik: str, limit: int = 4) -> list[dict]:
    result = session.get(SUBMISSIONS_URL.format(cik=cik))
    if result.status != 200:
        logger.warning("CIK %s: submissions lookup failed (status %d)", cik, result.status)
        return []
    data = result.json()
    recent = data.get("filings", {}).get("recent", {})
    filings = []
    for form, accession, doc, filed in zip(recent.get("form", []), recent.get("accessionNumber", []),
                                             recent.get("primaryDocument", []), recent.get("filingDate", [])):
        if form == "NPORT-P":
            filings.append({"accession": accession, "doc": doc, "filed": filed})
    return filings[:limit]


def parse_nport_xml(xml_text: str, fund: str) -> pd.DataFrame:
    period_match = _PERIOD_PATTERN.search(xml_text)
    period = period_match.group(1) if period_match else None

    # Fund-level total net assets (Part B, outside any <invstOrSec> block) --
    # stamped onto every position row so a caller only interested in the
    # fund-level figure (e.g. a NAV-per-share estimate) doesn't need a
    # second fetch/parse of the same filing.
    net_assets_match = _NET_ASSETS_PATTERN.search(xml_text)
    net_assets = float(net_assets_match.group(1)) if net_assets_match else None

    records = []
    for block in _INVSTORSEC_PATTERN.findall(xml_text):
        row = {"fund": fund, "period": period, "net_assets": net_assets}
        for field, pattern in _TAG_PATTERNS.items():
            m = pattern.search(block)
            row[field] = m.group(1).strip() if m else None
        records.append(row)

    if not records:
        raise ValueError(f"parsed zero positions from NPORT-P filing for {fund}")

    df = pd.DataFrame.from_records(records)
    for col in ("balance", "valUSD", "pctVal", "annualizedRt"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    by_asset_cat = df["assetCat"].isin(CLO_ASSET_CATEGORIES)
    name_hits = df["name"].fillna("").str.contains(_CLO_NAME_PATTERN) | df["title"].fillna("").str.contains(_CLO_NAME_PATTERN)
    by_name_fallback = (~by_asset_cat) & df["assetCat"].isna() & name_hits

    df["is_clo"] = by_asset_cat | by_name_fallback
    df["clo_detection_method"] = "none"
    df.loc[by_asset_cat, "clo_detection_method"] = "assetCat"
    df.loc[by_name_fallback, "clo_detection_method"] = "name_regex"
    return df


def scrape_fund(session: CachedSession, fund: str, cik: str, limit: int = 4) -> pd.DataFrame | None:
    filings = list_nport_filings(session, cik, limit=limit)
    if not filings:
        logger.warning("%s: no NPORT-P filings found", fund)
        return None

    frames = []
    for f in filings:
        accession_nodash = f["accession"].replace("-", "")
        cik_int = str(int(cik))
        # submissions API's primaryDocument ("xslFormNPORT-P_X01/primary_doc.xml")
        # points at SEC's XSL-rendered HTML viewer, not the raw XML. The raw
        # file sits at the same accession root under its bare filename.
        doc_basename = f["doc"].rsplit("/", 1)[-1]
        url = FILING_DOC_URL.format(cik=cik_int, accession_nodash=accession_nodash, doc=doc_basename)
        try:
            result = session.get(url)
        except Exception as exc:
            logger.warning("%s: failed to fetch %s (%s)", fund, url, exc)
            continue
        if result.status != 200:
            logger.warning("%s: %s returned status %d", fund, url, result.status)
            continue
        try:
            df = parse_nport_xml(result.text(), fund)
        except Exception as exc:
            logger.warning("%s: parse failed for %s (%s)", fund, f["accession"], exc)
            continue
        frames.append(df)
        logger.info("%s: parsed %d positions (%d CLO) from filing period %s",
                    fund, len(df), df["is_clo"].sum(), df["period"].iloc[0])

    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


def scrape_funds(session: CachedSession, fund_ciks: dict[str, str], limit_per_fund: int = 4) -> pd.DataFrame:
    frames = []
    for fund, cik in fund_ciks.items():
        df = scrape_fund(session, fund, cik, limit=limit_per_fund)
        if df is not None:
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    return combined.drop_duplicates(subset=["fund", "period", "cusip", "name", "title"], keep="last")
