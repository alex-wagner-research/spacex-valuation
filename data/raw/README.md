# data/raw

This folder is nearly empty by design: the analysis runs on public SEC documents that the
pipeline downloads for you rather than redistributing.

- `s1_exhibits/spaceexplorationtechnologi.htm` -- the SpaceX Form S-1 main document, carrying the
  full preliminary prospectus text including the financial-statement notes (SEC EDGAR accession
  0001628280-26-036936, filed 2026-05-20). Downloaded automatically by step 0 of
  `code/python/00_master.py`; it appears here after the first run (~1.5 MB, excluded from git). The
  complete exhibit set (merger agreement, award agreements, credit agreements, ...) can be fetched
  with `code/python/fetch_s1_exhibits.py`.
- `post_ipo_day1.json` -- ships filled: SpaceX's first trading day (June 12, 2026), open/high/low/
  close/volume. Refresh via `code/python/fetch_day1.py`; pipeline step 9 computes the postscript
  numbers from it.
- `post_ipo_series.json` -- ships with the official daily open/high/low/close/volume from listing,
  from the Nasdaq official historical record (written by `code/python/fetch_series.py`, cross-checked
  against an independent Yahoo 1-minute reconstruction). Pipeline step 10 draws the
  price-versus-implied-expected-return figure with a counterfactual median-IPO price path.
- `options_day1_cboe.json` -- a snapshot of SpaceX's listed-options chain on their first trading day
  (June 16, 2026) from the public CBOE delayed-quotes feed; pipeline step 12 reads SpaceX's
  at-the-money implied volatility from it for the cross-IPO debut comparison.

The cross-IPO debut comparison (step 12) is built on an objective, ex-ante set -- the largest U.S.
common-stock IPOs by gross proceeds since 2000 -- using WRDS data that is NOT redistributed here.
With WRDS access, regenerate it in three steps: `code/R/pull_sdc_ipo_raw.R` exports the candidate
IPOs from SDC New Issues; `code/python/build_ipo_universe_from_raw.py` selects the objective universe
(`data/raw/ipo_universe.csv`); and `code/R/pull_debut_panel_wrds.R` attaches first-day return and
continuation from CRSP and implied volatility from OptionMetrics IvyDB US by CUSIP
(`data/clean/ipo_debut_panel.csv`). Step 12 reads that panel; without it, the comparison figure is
skipped. SpaceX's own implied volatility comes from the shipped CBOE snapshot, not from WRDS.

All other model inputs are calibration constants defined in the code with their sources in
comments (see the main README).
