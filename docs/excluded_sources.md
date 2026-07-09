# Excluded sources

Sources considered and rejected because they are licensed, paywalled, require
credentials, or otherwise violate the "public, unlicensed data only" rule.
Format:

`Source | Section it would have served | Reason excluded | Date`

| Source | Would have served | Reason excluded | Date |
|---|---|---|---|
| Intex | Section 3/5 (deal-level cashflow/waterfall detail) | Licensed, credentialed platform | 2026-07-08 |
| LCD / PitchBook | Section 4/5 (loan/CLO market commentary and data) | Subscription required | 2026-07-08 |
| Creditflux | Section 5 (CLO news/data) | Subscription required | 2026-07-08 |
| Bloomberg Terminal/BVAL | Any section needing pricing | Licensed terminal access | 2026-07-08 |
| Morningstar (behind login) | Section 2 (fund data) | Paywalled beyond free summary pages | 2026-07-08 |
| `ishares.com` full-holdings ajax CSV for CLOA/CLOD | Section 1 (ETF holdings) | Not paywalled, but the classic `<id>.ajax?fileType=csv` endpoint returns an HTML shell rather than data for these products, and the product page's real holdings widget loads via a client-rendered JS component with no discovered stable JSON endpoint. Not a licensing issue — a JS-rendering wall. Left unresolved rather than adding headless-browser automation. | 2026-07-08 |
| `vaneck.com` CLOB/CLOI holdings pages | Section 1 (ETF holdings) | Plain HTTP GET loops on a cookie-consent redirect (`?cken=true`) and never reaches a data page without executing JS/setting the consent cookie via a real browser. | 2026-07-08 |
| `invesco.com` ICLO product page | Section 1 (ETF holdings) | Returns HTTP 406 to a scripted client regardless of Accept/User-Agent headers tried. | 2026-07-08 |
| `clozfund.com` (Eldridge, fka Panagram, CLOZ) | Section 1 (ETF holdings) | Only quarterly holdings PDFs found (`Eldridge-CLOZ-Q1.pdf`, `-Q3.pdf`); no daily CSV/HTML table. Not excluded for licensing — just no daily granularity available. Presale-style PDF extraction could recover quarterly snapshots later if needed. | 2026-07-08 |

| SIFMA US ABS/issuance statistics | Section 4 (issuance cycle) | The download link on sifma.org routes through an HubSpot lead-gen form (`share.hsforms.com`), not a direct file; a previously-known direct `.xlsx` path under `wp-content/uploads` now 404s (site rebuilt on Next.js). Automating a marketing lead-capture form isn't "polite public scraping" in spirit, so this is treated as gated rather than public, even though there's no paywall per se. | 2026-07-09 |

| S&P Global Ratings (spglobal.com/ratings) | Section 5 (rating actions, presales) | Entire domain sits behind Akamai bot protection — even `robots.txt` itself returns HTTP 403 to a scripted client with a declared, honest User-Agent. Not a login wall in the traditional sense, but a hard access-denied wall regardless of client behavior. | 2026-07-09 |
| Fitch Ratings (fitchratings.com) | Section 5 (rating actions, presales) | Reachable (200, permissive robots.txt) but the research/rating-action listing pages are entirely client-rendered — no server-side HTML content, no discoverable JSON API in the page source. Fitch's own documentation confirms programmatic access ("Feeds and API") is a paid product, not a free channel. A third-party mirror (LSTA's "Fitch Ratings Commentary Page") exists but is itself a trade-association member benefit, not clearly licensed for systematic scraping. | 2026-07-09 |

_(This list grows as individual scrapers hit a paywall/login wall; each gets logged here rather than worked around.)_
