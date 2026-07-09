"""Issuer entity-resolution cascade.

normalize -> exact match against canonical table -> rapidfuzz token_set_ratio
fuzzy match (>=92 auto-accept, 80-92 review queue, <80 unmatched) -> alias
table that accretes every confirmed resolution so matching compounds across
sources as more get resolved.

The canonical table is bootstrapped from the union of every scraped holdings
source and grows over time; it lives at data/interim/entity_canonical.parquet
with a companion alias table at data/interim/entity_aliases.parquet. The
review queue (80-92 band) is written to data/interim/entity_review_queue.csv
for human (or optional cached LLM) adjudication.

First-token blocking: candidates are only fuzzy-compared against canonical
names sharing the first normalized token, which keeps the cascade close to
linear instead of O(n*m).
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

import config

logger = logging.getLogger("clo_atlas.entity")

_SUFFIX_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(s) for s in config.LEGAL_SUFFIXES) + r")\b"
)
_PUNCT_PATTERN = re.compile(r"[^\w\s]")
_WS_PATTERN = re.compile(r"\s+")

CANONICAL_PATH = config.INTERIM_DIR / "entity_canonical.parquet"
ALIAS_PATH = config.INTERIM_DIR / "entity_aliases.parquet"
REVIEW_QUEUE_PATH = config.INTERIM_DIR / "entity_review_queue.csv"


def normalize(name: str) -> str:
    """lowercase, strip punctuation, kill legal/LBO suffixes, collapse whitespace."""
    if not isinstance(name, str) or not name.strip():
        return ""
    s = name.lower()
    s = _PUNCT_PATTERN.sub(" ", s)
    s = _SUFFIX_PATTERN.sub(" ", s)
    s = _WS_PATTERN.sub(" ", s).strip()
    return s


def first_token(normalized_name: str) -> str:
    parts = normalized_name.split(" ")
    return parts[0] if parts else ""


@dataclass
class MatchResult:
    raw_name: str
    normalized_name: str
    canonical_id: str | None
    canonical_name: str | None
    method: str  # "exact" | "alias" | "fuzzy_auto" | "fuzzy_review" | "unresolved"
    score: float | None


class EntityResolver:
    """Stateful resolver: load canonical/alias tables, resolve names, persist growth."""

    def __init__(self, canonical_path: Path = CANONICAL_PATH, alias_path: Path = ALIAS_PATH):
        self.canonical_path = canonical_path
        self.alias_path = alias_path
        self.canonical = self._load_canonical()
        self.aliases = self._load_aliases()
        self._blocks: dict[str, list[str]] = {}
        self._rebuild_blocks()
        self.review_rows: list[dict] = []

    def _load_canonical(self) -> pd.DataFrame:
        if self.canonical_path.exists():
            return pd.read_parquet(self.canonical_path)
        return pd.DataFrame(columns=["canonical_id", "canonical_name", "normalized_name"])

    def _load_aliases(self) -> pd.DataFrame:
        if self.alias_path.exists():
            return pd.read_parquet(self.alias_path)
        return pd.DataFrame(columns=["raw_name", "normalized_name", "canonical_id", "method", "score", "source"])

    def _rebuild_blocks(self) -> None:
        self._blocks = {}
        for _, row in self.canonical.iterrows():
            tok = first_token(row["normalized_name"])
            self._blocks.setdefault(tok, []).append(row["normalized_name"])
        self._norm_to_id = dict(zip(self.canonical["normalized_name"], self.canonical["canonical_id"]))
        self._norm_to_canonical_name = dict(zip(self.canonical["normalized_name"], self.canonical["canonical_name"]))

    def _new_canonical_id(self, normalized_name: str) -> str:
        return "ent_" + hashlib.sha1(normalized_name.encode()).hexdigest()[:12]

    def bootstrap(self, names: list[str]) -> None:
        """Seed the canonical table from a union of raw issuer names (first run)."""
        seen = set(self.canonical["normalized_name"]) if len(self.canonical) else set()
        new_rows = []
        for raw in names:
            norm = normalize(raw)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            new_rows.append({
                "canonical_id": self._new_canonical_id(norm),
                "canonical_name": raw.strip(),
                "normalized_name": norm,
            })
        if new_rows:
            self.canonical = pd.concat([self.canonical, pd.DataFrame(new_rows)], ignore_index=True)
            self._rebuild_blocks()
        logger.info("bootstrapped canonical table: %d entities (%d new)", len(self.canonical), len(new_rows))

    def resolve(self, raw_name: str, source: str = "") -> MatchResult:
        norm = normalize(raw_name)
        if not norm:
            return MatchResult(raw_name, norm, None, None, "unresolved", None)

        # 1. exact match
        if norm in self._norm_to_id:
            cid = self._norm_to_id[norm]
            return MatchResult(raw_name, norm, cid, self._norm_to_canonical_name[norm], "exact", 100.0)

        # 2. alias table (previously confirmed resolutions)
        alias_hit = self.aliases[self.aliases["normalized_name"] == norm]
        if len(alias_hit):
            row = alias_hit.iloc[0]
            cname = self._norm_to_canonical_name.get(row["canonical_id"])
            return MatchResult(raw_name, norm, row["canonical_id"], cname, "alias", float(row["score"]))

        # 3. fuzzy match within first-token block
        block = self._blocks.get(first_token(norm), [])
        if block:
            best = process.extractOne(norm, block, scorer=fuzz.token_set_ratio)
            if best:
                candidate_norm, score, _ = best
                cid = self._norm_to_id[candidate_norm]
                cname = self._norm_to_canonical_name[candidate_norm]
                if score >= config.ENTITY_AUTO_ACCEPT_SCORE:
                    self._record_alias(raw_name, norm, cid, "fuzzy_auto", score, source)
                    return MatchResult(raw_name, norm, cid, cname, "fuzzy_auto", score)
                if score >= config.ENTITY_REVIEW_MIN_SCORE:
                    self.review_rows.append({
                        "raw_name": raw_name, "normalized_name": norm,
                        "candidate_canonical_id": cid, "candidate_canonical_name": cname,
                        "score": score, "source": source,
                    })
                    return MatchResult(raw_name, norm, None, cname, "fuzzy_review", score)

        # 4. unresolved -> becomes a new canonical entity of its own
        new_id = self._new_canonical_id(norm)
        self.canonical = pd.concat([self.canonical, pd.DataFrame([{
            "canonical_id": new_id, "canonical_name": raw_name.strip(), "normalized_name": norm,
        }])], ignore_index=True)
        self._rebuild_blocks()
        return MatchResult(raw_name, norm, new_id, raw_name.strip(), "unresolved", None)

    def _record_alias(self, raw_name: str, norm: str, canonical_id: str, method: str, score: float, source: str) -> None:
        new_row = pd.DataFrame([{
            "raw_name": raw_name, "normalized_name": norm, "canonical_id": canonical_id,
            "method": method, "score": score, "source": source,
        }])
        self.aliases = new_row if self.aliases.empty else pd.concat([self.aliases, new_row], ignore_index=True)

    def resolve_many(self, raw_names: list[str], source: str = "") -> pd.DataFrame:
        results = [self.resolve(n, source=source) for n in raw_names]
        return pd.DataFrame([r.__dict__ for r in results])

    def confirm_review(self, raw_name: str, canonical_id: str, source: str = "manual_review") -> None:
        """Human (or LLM tiebreaker) confirms a review-queue candidate; promote it to the alias table."""
        norm = normalize(raw_name)
        self._record_alias(raw_name, norm, canonical_id, "review_confirmed", 100.0, source)

    def save(self) -> None:
        config.INTERIM_DIR.mkdir(parents=True, exist_ok=True)
        self.canonical.to_parquet(self.canonical_path, index=False)
        self.aliases.to_parquet(self.alias_path, index=False)
        if self.review_rows:
            existing = pd.read_csv(REVIEW_QUEUE_PATH) if REVIEW_QUEUE_PATH.exists() else pd.DataFrame()
            combined = pd.concat([existing, pd.DataFrame(self.review_rows)], ignore_index=True)
            combined = combined.drop_duplicates(subset=["raw_name", "candidate_canonical_id"])
            combined.to_csv(REVIEW_QUEUE_PATH, index=False)
            logger.info("wrote %d rows to review queue at %s", len(combined), REVIEW_QUEUE_PATH)

    def match_funnel_stats(self, results: pd.DataFrame) -> dict:
        """Summary stats for the entity-resolution funnel exhibit (Section 3 viz_funnel.py)."""
        counts = results["method"].value_counts().to_dict()
        total = len(results)
        return {
            "total": total,
            "exact": counts.get("exact", 0),
            "alias": counts.get("alias", 0),
            "fuzzy_auto": counts.get("fuzzy_auto", 0),
            "fuzzy_review": counts.get("fuzzy_review", 0),
            "unresolved": counts.get("unresolved", 0),
            "match_rate": (total - counts.get("unresolved", 0)) / total if total else 0.0,
        }


def llm_tiebreak_cached(raw_name: str, candidates: list[str]) -> dict:
    """Optional LLM adjudication for the review queue. Fixed prompt, temperature 0,
    JSON output, cached to disk keyed by a hash of (raw_name, candidates) so reruns
    are free and deterministic. Left as a documented stub: wiring the actual Claude
    API call is a caller-provided concern (this module has no network dependency
    beyond entity matching itself) so it can be swapped/mocked in tests.
    """
    key = hashlib.sha256(json.dumps([raw_name, sorted(candidates)]).encode()).hexdigest()
    cache_path = config.LLM_CACHE_DIR / f"entity_tiebreak_{key}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text())
    raise NotImplementedError(
        "llm_tiebreak_cached has no model call wired up; this is a documented stub. "
        "Populate data/_llm_cache/entity_tiebreak_<hash>.json to backfill, or wire a "
        "temperature-0 JSON-mode call here and it will self-cache thereafter."
    )


def main():
    logging.basicConfig(level=logging.INFO)
    resolver = EntityResolver()
    sample = ["Carlyle Global Market Strategies LLC", "Carlyle GMS Finance, Inc.", "Ares Capital Corporation"]
    resolver.bootstrap(sample)
    results = resolver.resolve_many(["Carlyle GMS", "ARES CAPITAL CORP", "Totally New Manager Ltd"], source="demo")
    print(results)
    print(resolver.match_funnel_stats(results))
    resolver.save()


if __name__ == "__main__":
    main()
