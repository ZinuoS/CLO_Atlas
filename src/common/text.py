"""PDF/HTML -> clean text, sentence splitting, Loughran-McDonald sentiment scoring,
mention counting, and simple collocation extraction.

Deterministic lexicon scoring (Loughran-McDonald) is the primary layer
everywhere in this project. LLM document scoring is an optional secondary
layer with the same disk-caching discipline as common/entity.py's tiebreaker;
wherever both exist, report both series and their disagreement rather than
picking one.
"""
from __future__ import annotations

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
    logging.basicConfig(level=logging.INFO)
    sample = "The CLO market showed resilient performance despite uncertainty about litigation risk in the loan collateral."
    print(split_sentences(sample))
    print(mention_rate_per_1000(sample, ["CLO", "litigation risk"]))
    print(collocates(sample, "CLO", window=4))


if __name__ == "__main__":
    main()
