"""PDF/HTML -> clean text, sentence splitting, Loughran-McDonald sentiment scoring,
mention counting, and simple collocation extraction.

Deterministic lexicon scoring (Loughran-McDonald) is the primary layer
everywhere in this project. LLM document scoring is an optional secondary
layer with the same disk-caching discipline as common/entity.py's tiebreaker;
wherever both exist, report both series and their disagreement rather than
picking one.
"""
from __future__ import annotations

import datetime as _dt
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

import config

logger = logging.getLogger("clo_atlas.text")

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
_WORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z'\-]*")
_WS_PATTERN = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------
def pdf_to_text(path: Path) -> str:
    import pdfplumber
    parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            parts.append(t)
    return "\n".join(parts)


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    return _WS_PATTERN.sub(" ", text).strip()


def clean_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = _WS_PATTERN.sub(" ", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def split_paragraphs(raw_text: str) -> list[str]:
    paras = re.split(r"\n\s*\n", raw_text)
    return [clean_text(p) for p in paras if clean_text(p)]


def tokenize(text: str) -> list[str]:
    return [w.lower() for w in _WORD_PATTERN.findall(text)]


# ---------------------------------------------------------------------------
# Loughran-McDonald lexicon
# ---------------------------------------------------------------------------
@dataclass
class LMLexicon:
    positive: set
    negative: set
    uncertainty: set
    litigious: set

    @classmethod
    def load(cls, path: Path = config.LM_DICTIONARY_PATH) -> "LMLexicon":
        if not path.exists():
            raise FileNotFoundError(
                f"LM master dictionary not found at {path}. Run "
                f"`python -m src.common.text --fetch-lexicon` (or the relevant scraper) "
                f"to download it from {config.LM_DICTIONARY_LANDING_PAGE} first; the "
                f"resolved file URL gets logged to docs/sources.md on first fetch."
            )
        df = pd.read_csv(path)
        df.columns = [c.strip().lower() for c in df.columns]
        word_col = "word" if "word" in df.columns else df.columns[0]

        def words_where(flag_col: str) -> set:
            if flag_col not in df.columns:
                return set()
            return set(df.loc[df[flag_col].fillna(0).astype(float) > 0, word_col].str.lower())

        return cls(
            positive=words_where("positive"),
            negative=words_where("negative"),
            uncertainty=words_where("uncertainty"),
            litigious=words_where("litigious"),
        )


_SRAF_CSV_LINK_PATTERN = re.compile(
    r'CSV Format:.{0,40}?<a href="(https://drive\.google\.com/file/d/([^/]+)/[^"]*)"', re.DOTALL)


def fetch_lm_dictionary(session, force: bool = False) -> Path:
    """Download the Loughran-McDonald master dictionary CSV to
    config.LM_DICTIONARY_PATH. Previously blocked (the landing page appeared
    client-rendered on an earlier pass); re-checked 2026-07-11 and the CSV
    link is in fact present in the server-rendered HTML — it just points to
    a Google Drive share (`drive.google.com/file/d/<id>/...`), not a direct
    file host, discovered by reading the actual page source, not guessed.
    The share resolves through Drive's `uc?export=download` redirect to a
    plain CSV for a file this size (no interstitial virus-scan/confirm page
    at ~87k rows), verified by fetching it directly.
    """
    if config.LM_DICTIONARY_PATH.exists() and not force:
        logger.info("LM dictionary already cached at %s", config.LM_DICTIONARY_PATH)
        return config.LM_DICTIONARY_PATH

    landing = session.get(config.LM_DICTIONARY_LANDING_PAGE)
    if landing.status != 200:
        raise RuntimeError(f"LM dictionary landing page failed: status {landing.status}")
    match = _SRAF_CSV_LINK_PATTERN.search(landing.text())
    if not match:
        raise RuntimeError(
            f"could not find the CSV download link on {config.LM_DICTIONARY_LANDING_PAGE}; "
            "the page structure may have changed since 2026-07-11."
        )
    file_id = match.group(2)
    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    result = session.get(download_url)
    if result.status != 200:
        raise RuntimeError(f"LM dictionary download failed: status {result.status} from {download_url}")

    text = result.text()
    header = text.splitlines()[0].lower() if text else ""
    if "word" not in header or "negative" not in header:
        raise RuntimeError(
            f"downloaded content from {download_url} doesn't look like the LM dictionary "
            f"(header: {header[:120]!r}) — Drive may have served an interstitial page instead of the file."
        )

    config.LM_DICTIONARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.LM_DICTIONARY_PATH.write_text(text)
    sidecar = config.LM_DICTIONARY_PATH.with_suffix(config.LM_DICTIONARY_PATH.suffix + ".provenance.json")
    sidecar.write_text(json.dumps({
        "source_urls": [config.LM_DICTIONARY_LANDING_PAGE, download_url],
        "scrape_timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "parser": "src.common.text.fetch_lm_dictionary",
        "row_count": max(len(text.splitlines()) - 1, 0),
        "notes": "Loughran-McDonald Master Dictionary, free for academic/research use per sraf.nd.edu. "
                 "Google Drive share resolved to a direct CSV via the uc?export=download redirect.",
        "written_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    }, indent=2))
    logger.info("wrote LM dictionary (%d words) to %s", max(len(text.splitlines()) - 1, 0), config.LM_DICTIONARY_PATH)
    return config.LM_DICTIONARY_PATH


@dataclass
class LMScore:
    n_tokens: int
    n_positive: int
    n_negative: int
    n_uncertainty: int
    n_litigious: int

    @property
    def net_sentiment(self) -> float:
        """(pos - neg) / tokens"""
        return (self.n_positive - self.n_negative) / self.n_tokens if self.n_tokens else 0.0

    @property
    def uncertainty_rate(self) -> float:
        return self.n_uncertainty / self.n_tokens if self.n_tokens else 0.0

    @property
    def litigious_rate(self) -> float:
        return self.n_litigious / self.n_tokens if self.n_tokens else 0.0


def score_lm(text: str, lexicon: LMLexicon) -> LMScore:
    tokens = tokenize(text)
    n = len(tokens)
    counts = Counter(tokens)
    n_pos = sum(counts[w] for w in lexicon.positive if w in counts)
    n_neg = sum(counts[w] for w in lexicon.negative if w in counts)
    n_unc = sum(counts[w] for w in lexicon.uncertainty if w in counts)
    n_lit = sum(counts[w] for w in lexicon.litigious if w in counts)
    return LMScore(n_tokens=n, n_positive=n_pos, n_negative=n_neg, n_uncertainty=n_unc, n_litigious=n_lit)


# ---------------------------------------------------------------------------
# Vulnerability lexicon (config.VULNERABILITY_STEMS) — regulator alarm lives
# in these words, not in general-purpose (VADER) social-media valence.
# Stem-based substring matching, not exact-token matching like LM, since the
# lexicon is deliberately specified as word stems (e.g. "vulnerab" matches
# vulnerable/vulnerability/vulnerabilities).
# ---------------------------------------------------------------------------
def score_vulnerability(text: str, stems: list[str] | None = None) -> float:
    """Vulnerability-lexicon hit rate per token (stem substring match)."""
    stems = stems or config.VULNERABILITY_STEMS
    tokens = tokenize(text)
    n = len(tokens)
    if not n:
        return 0.0
    hits = sum(1 for tok in tokens if any(tok.startswith(stem) for stem in stems))
    # Multi-word stems (e.g. "fire sale", "run risk") aren't single tokens;
    # count phrase occurrences in the lowered text separately.
    phrase_stems = [s for s in stems if " " in s]
    lowered = text.lower()
    phrase_hits = sum(lowered.count(p) for p in phrase_stems)
    return (hits + phrase_hits) / n


# ---------------------------------------------------------------------------
# Mention counting / collocation
# ---------------------------------------------------------------------------
def mention_rate_per_1000(text: str, terms: list[str]) -> dict[str, float]:
    """Per-1,000-token mention rate for each term (case-insensitive, phrase-aware)."""
    tokens = tokenize(text)
    n = len(tokens)
    lowered = text.lower()
    rates = {}
    for term in terms:
        term_l = term.lower()
        if " " in term_l:
            count = lowered.count(term_l)
        else:
            count = sum(1 for t in tokens if t == term_l)
        rates[term] = (count / n * 1000) if n else 0.0
    return rates


def collocates(text: str, target: str, window: int = 5, top_n: int = 20,
                stopwords: set | None = None) -> list[tuple[str, int]]:
    """Words appearing within `window` tokens of `target` (case-insensitive), ranked by frequency."""
    stopwords = stopwords or _DEFAULT_STOPWORDS
    tokens = tokenize(text)
    target_l = target.lower()
    counter = Counter()
    for i, tok in enumerate(tokens):
        if tok == target_l:
            lo, hi = max(0, i - window), min(len(tokens), i + window + 1)
            for j in range(lo, hi):
                if j == i:
                    continue
                w = tokens[j]
                if w not in stopwords and w != target_l:
                    counter[w] += 1
    return counter.most_common(top_n)


_DEFAULT_STOPWORDS = set(
    "the a an of to in and or for on with as is are was were be by at from this that "
    "it its their they he she we you i but not no also has have had will would could "
    "should may might than then so such which who what when where".split()
)


def main():
    import sys
    logging.basicConfig(level=logging.INFO)
    if "--fetch-lexicon" in sys.argv:
        from src.common.http import CachedSession
        fetch_lm_dictionary(CachedSession())
        return
    sample = "The CLO market showed resilient performance despite uncertainty about litigation risk in the loan collateral."
    print(split_sentences(sample))
    print(mention_rate_per_1000(sample, ["CLO", "litigation risk"]))
    print(collocates(sample, "CLO", window=4))
    print("vulnerability rate:", score_vulnerability("The fire sale risk amplified contagion across correlated portfolios."))


if __name__ == "__main__":
    main()
