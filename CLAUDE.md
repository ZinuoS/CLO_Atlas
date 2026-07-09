# clo-atlas

Research codebase scraping **public, unlicensed** CLO-market data for original,
NYT-style data-journalism charts introducing CLOs as an asset class.

## Absolute rules

1. **No licensed/paywalled data.** Never scrape Intex, LCD/PitchBook,
   Creditflux, Bloomberg, Morningstar-behind-login, or anything needing
   credentials or violating ToS. Log exclusions in `docs/excluded_sources.md`
   with the reason and move on — never fake or fabricate a substitute number.
2. **Polite scraping only.** Everything goes through `src/common/http.py`'s
   `CachedSession` — never bare `requests.get`. Respect robots.txt, rate limits
   in `config.RATE_LIMITS`, exponential backoff on 429/503. SEC EDGAR: ≤10
   req/s, declared User-Agent (`config.USER_AGENT`, built from
   `CLO_ATLAS_NAME`/`CLO_ATLAS_EMAIL` env vars).
3. **Reproducibility.** Raw responses archived to `data/raw/` before parsing
   (automatic via `CachedSession`). Every interim/final dataset gets a
   provenance JSON sidecar (`src/common/cache.py`). Analysis/viz stages run
   entirely from cached parquet — no network calls outside `scrape_*.py`.

## Architecture

- Pure functions in `src/`; notebooks (`notebooks/*.ipynb`) are thin drivers
  only — no logic in notebook cells.
- `config.py` is the single source of truth for paths, tickers, URLs, dates,
  rate limits, the shared event registry, and the random seed. Never hardcode
  these in a module.
- Stage boundary = artifact boundary: `scrape -> data/raw` (untouched) ->
  `parse -> data/interim` (tidy parquet) -> `analysis -> data/final`
  (analysis-ready tables) -> `viz -> figures/` (PNG@300dpi + SVG) and
  `figures/interactive/` (self-contained HTML).
- Every scraper is idempotent/incremental (`CachedSession` skips URLs already
  in the manifest) and has `def main():` behind `if __name__ == "__main__":`
  so it runs standalone via `python -m src.<section>.<module>`.
- Dead/blocked sources degrade gracefully: log a structured warning, let
  downstream stages run on whatever is cached, never break `make all`.
- Quantitative claims in the synthesis notebook are tagged `VERIFIED`
  (computed here) or `TO-VERIFY` (external number). No untagged numbers.

## Shared infra (`src/common/`)

- `http.py` — `CachedSession`: rate limiting, retry/backoff, raw archiving + manifest.
- `cache.py` — parquet read/write with provenance sidecars.
- `wayback.py` — Wayback CDX backfill for issuer pages that only host the latest file.
- `entity.py` — issuer entity-resolution cascade: normalize -> exact -> alias
  table -> rapidfuzz fuzzy (>=92 auto-accept, 80-92 review queue, <80
  unmatched) -> optional cached LLM tiebreaker. First-token blocking.
- `text.py` — PDF/HTML -> text, sentence/paragraph split, Loughran-McDonald
  sentiment scoring, mention rates, collocations.
- `style.py` — `apply_theme()` / `save_figure()`: off-white bg, horizontal
  gridlines only, no boxed spines, direct labeling over legends (<=6 series),
  one accent color, headline/subtitle/source/byline scaffold, event-flag
  helper keyed to `config.EVENTS`, small-multiples grid, matching Altair theme.

## Execution order

Scaffold -> Section 1 (ETF) -> Section 4 (official) -> Section 2 (CEF) ->
Section 5 (ratings) -> Section 3 (EDGAR/BDC, hardest parsing) -> Section 6
(sentiment) -> `notebooks/7_synthesis.ipynb`. At each section boundary: run
that section's notebook top-to-bottom from cache, commit, update
`docs/sources.md`.

## Testing

`pytest tests/` — every parser has a golden test: fixture in, known tidy
frame out. Fixtures live in `tests/fixtures/`.

## Dependency policy

Do not add a dependency outside `requirements.txt` without asking first.
`jupyter`/`ipykernel` were added beyond the original approved list because the
architecture requires runnable `.ipynb` notebooks as deliverables; `openpyxl`
was added because FINRA/SIFMA publish source data as `.xlsx` and pandas needs
it as an engine to read those — both flagged here rather than silently
expanded.

## Allowed data domains discovered so far

See `docs/sources.md` (used) and `docs/excluded_sources.md` (rejected, with reason).
