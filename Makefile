.PHONY: all setup test macro etf cef edgar official ratings sentiment sentiment_v2 cef_deep_dive future figures synthesis clean

PYTHON := .venv/bin/python

all: macro etf official cef ratings edgar sentiment sentiment_v2 cef_deep_dive future synthesis

setup:
	python3 -m venv .venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(PYTHON) -m pytest tests/ -q

# --- Macro opener: slides 1-2 (regime, disintermediation, scale, income) ---
macro:
	$(PYTHON) -m src.macro.scrape_fred
	$(PYTHON) -m src.macro.scrape_z1
	$(PYTHON) -m src.macro.scrape_market_size
	$(PYTHON) -m src.macro.scrape_returns
	$(PYTHON) -m src.macro.analysis_regime
	$(PYTHON) -m src.macro.analysis_disintermediation
	$(PYTHON) -m src.macro.analysis_scale
	$(PYTHON) -m src.macro.analysis_tightening
	$(PYTHON) -m src.macro.analysis_income
	$(PYTHON) -m src.macro.viz_regime
	$(PYTHON) -m src.macro.viz_disintermediation
	$(PYTHON) -m src.macro.viz_scale
	$(PYTHON) -m src.macro.viz_tightening
	$(PYTHON) -m src.macro.viz_income
	$(PYTHON) -m src.macro.ledger

# --- Section 1: CLO ETFs ---------------------------------------------------
etf:
	$(PYTHON) -m src.etf.scrape_holdings
	$(PYTHON) -m src.etf.scrape_nav_flows
	$(PYTHON) -m src.etf.analysis_flows
	$(PYTHON) -m src.etf.analysis_nav_dislocation
	$(PYTHON) -m src.etf.analysis_tranche_panel
	$(PYTHON) -m src.etf.analysis_manager_league
	$(PYTHON) -m src.etf.analysis_returns
	$(PYTHON) -m src.etf.viz_growth
	$(PYTHON) -m src.etf.viz_dislocation
	$(PYTHON) -m src.etf.viz_tranche
	$(PYTHON) -m src.etf.viz_league
	$(PYTHON) -m src.etf.viz_returns

# --- Section 2: Listed CLO closed-end funds --------------------------------
cef:
	$(PYTHON) -m src.cef.scrape_prices_nav
	$(PYTHON) -m src.cef.scrape_filings
	$(PYTHON) -m src.cef.analysis_premium_discount
	$(PYTHON) -m src.cef.analysis_distributions
	$(PYTHON) -m src.cef.analysis_portfolio
	$(PYTHON) -m src.cef.analysis_equity_beta
	$(PYTHON) -m src.cef.viz_sentiment
	$(PYTHON) -m src.cef.viz_navprice
	$(PYTHON) -m src.cef.viz_portfolio

# --- Section 3: BDC & fund filings ------------------------------------------
edgar:
	$(PYTHON) -m src.edgar.scrape_bdc_soi
	$(PYTHON) -m src.edgar.scrape_nport
	$(PYTHON) -m src.edgar.scrape_adv
	$(PYTHON) -m src.edgar.analysis_resolution
	$(PYTHON) -m src.edgar.analysis_mark_dispersion
	$(PYTHON) -m src.edgar.analysis_crowding
	$(PYTHON) -m src.edgar.analysis_terms
	$(PYTHON) -m src.edgar.analysis_managers
	$(PYTHON) -m src.edgar.viz_dispersion
	$(PYTHON) -m src.edgar.viz_crowding
	$(PYTHON) -m src.edgar.viz_terms
	$(PYTHON) -m src.edgar.viz_funnel

# --- Section 4: Official-sector data -----------------------------------
official:
	$(PYTHON) -m src.official.scrape_efa
	$(PYTHON) -m src.official.scrape_ffiec
	$(PYTHON) -m src.official.scrape_trace
	$(PYTHON) -m src.official.scrape_sifma
	$(PYTHON) -m src.official.scrape_fred
	$(PYTHON) -m src.official.analysis_holders
	$(PYTHON) -m src.official.analysis_banks
	$(PYTHON) -m src.official.analysis_liquidity
	$(PYTHON) -m src.official.analysis_issuance
	$(PYTHON) -m src.official.viz_holders
	$(PYTHON) -m src.official.viz_liquidity
	$(PYTHON) -m src.official.viz_issuance

# --- Section 5: Rating actions & presale text ------------------------------
ratings:
	$(PYTHON) -m src.ratings.scrape_actions
	$(PYTHON) -m src.ratings.scrape_presales
	$(PYTHON) -m src.ratings.analysis_transitions
	$(PYTHON) -m src.ratings.analysis_vintage
	$(PYTHON) -m src.ratings.analysis_vocabulary
	$(PYTHON) -m src.ratings.analysis_structure_drift
	$(PYTHON) -m src.ratings.viz_transitions
	$(PYTHON) -m src.ratings.viz_vintage
	$(PYTHON) -m src.ratings.viz_vocabulary

# --- Section 6: Textual sentiment ------------------------------------------
sentiment:
	$(PYTHON) -m src.sentiment.scrape_regulators
	$(PYTHON) -m src.sentiment.scrape_reddit
	$(PYTHON) -m src.sentiment.scrape_transcripts
	$(PYTHON) -m src.sentiment.analysis_alarm_index
	$(PYTHON) -m src.sentiment.analysis_narrative_arc
	$(PYTHON) -m src.sentiment.analysis_retail
	$(PYTHON) -m src.sentiment.analysis_insider_tone
	$(PYTHON) -m src.sentiment.viz_alarm
	$(PYTHON) -m src.sentiment.viz_narrative
	$(PYTHON) -m src.sentiment.viz_retail
	$(PYTHON) -m src.sentiment.viz_tone

# --- Sentiment v2: rebuilt alarm index + high-frequency attention backbone -
sentiment_v2:
	$(PYTHON) -m src.sentiment.scrape_regulators_v2
	$(PYTHON) -m src.sentiment.scrape_gdelt
	$(PYTHON) -m src.sentiment.scrape_news_rss
	$(PYTHON) -m src.sentiment.scrape_yf_news
	$(PYTHON) -m src.sentiment.scrape_pressreleases
	$(PYTHON) -m src.sentiment.scrape_stocktwits
	$(PYTHON) -m src.sentiment.scrape_ssrn_arxiv
	$(PYTHON) -m src.sentiment.analysis_alarm_v2
	$(PYTHON) -m src.sentiment.analysis_attention_tone
	$(PYTHON) -m src.sentiment.analysis_scorer_validation
	$(PYTHON) -m src.sentiment.viz_alarm_v2
	$(PYTHON) -m src.sentiment.viz_attention
	$(PYTHON) -m src.sentiment.viz_validation
	$(PYTHON) -m src.sentiment.ledger

# --- CEF deep-dive: Oxford Lane capital machine + capital-structure ---------
cef_deep_dive:
	$(PYTHON) -m src.cef.scrape_capital_actions
	$(PYTHON) -m src.cef.scrape_preferreds
	$(PYTHON) -m src.cef.scrape_13f_ownership
	$(PYTHON) -m src.cef.analysis_capital_machine
	$(PYTHON) -m src.cef.analysis_cost_of_capital
	$(PYTHON) -m src.cef.analysis_distribution_quality
	$(PYTHON) -m src.cef.analysis_portfolio_style
	$(PYTHON) -m src.cef.analysis_nav_translation
	$(PYTHON) -m src.cef.analysis_ownership
	$(PYTHON) -m src.cef.analysis_demand_transmission
	$(PYTHON) -m src.cef.viz_flywheel
	$(PYTHON) -m src.cef.viz_cost_of_capital
	$(PYTHON) -m src.cef.viz_distribution
	$(PYTHON) -m src.cef.viz_style
	$(PYTHON) -m src.cef.viz_wrapper
	$(PYTHON) -m src.cef.ledger

# --- Part C: where the asset class is going (closing slides) ---------------
future:
	$(PYTHON) -m src.future.scrape_product_pipeline
	$(PYTHON) -m src.future.scrape_mm_share
	$(PYTHON) -m src.future.scrape_litigation
	$(PYTHON) -m src.future.scrape_rulemaking
	$(PYTHON) -m src.future.scrape_trends
	$(PYTHON) -m src.future.scrape_etf_filings_options
	$(PYTHON) -m src.future.analysis_pipeline
	$(PYTHON) -m src.future.analysis_composition_shift
	$(PYTHON) -m src.future.analysis_legal_regime
	$(PYTHON) -m src.future.analysis_maturation_scorecard
	$(PYTHON) -m src.future.analysis_scenarios
	$(PYTHON) -m src.future.viz_pipeline
	$(PYTHON) -m src.future.viz_composition
	$(PYTHON) -m src.future.viz_legal
	$(PYTHON) -m src.future.viz_scorecard
	$(PYTHON) -m src.future.viz_watchlist
	$(PYTHON) -m src.future.ledger

# --- Regenerate every chart from cache (no network) -------------------------
figures:
	$(PYTHON) -m jupyter nbconvert --to notebook --execute --inplace notebooks/0_macro_opener.ipynb
	$(PYTHON) -m jupyter nbconvert --to notebook --execute --inplace notebooks/1_etf.ipynb
	$(PYTHON) -m jupyter nbconvert --to notebook --execute --inplace notebooks/2_cef.ipynb
	$(PYTHON) -m jupyter nbconvert --to notebook --execute --inplace notebooks/3_edgar.ipynb
	$(PYTHON) -m jupyter nbconvert --to notebook --execute --inplace notebooks/4_official.ipynb
	$(PYTHON) -m jupyter nbconvert --to notebook --execute --inplace notebooks/5_ratings.ipynb
	$(PYTHON) -m jupyter nbconvert --to notebook --execute --inplace notebooks/6_sentiment.ipynb
	$(PYTHON) -m jupyter nbconvert --to notebook --execute --inplace notebooks/8_sentiment_v2.ipynb
	$(PYTHON) -m jupyter nbconvert --to notebook --execute --inplace notebooks/9_cef_oxford_lane.ipynb
	$(PYTHON) -m jupyter nbconvert --to notebook --execute --inplace notebooks/10_future.ipynb

synthesis: figures
	$(PYTHON) -m jupyter nbconvert --to notebook --execute --inplace notebooks/7_synthesis.ipynb

clean:
	find . -name "__pycache__" -type d -exec rm -rf {} +
	rm -rf .pytest_cache
