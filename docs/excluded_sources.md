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

_(This list grows as individual scrapers hit a paywall/login wall; each gets logged here rather than worked around.)_
