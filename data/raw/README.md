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

The cross-IPO comparison (step 12) also uses two derived inputs that are NOT shipped here:
`data/clean/ipo_aftermarket.csv` (the first three daily closes of the comparison IPOs, regenerated
from public sources by `code/python/11_ipo_aftermarket.py`), and `data/clean/ipo_options_iv.csv`
(each comparison IPO's implied volatility on its first options day, from OptionMetrics IvyDB US via
WRDS -- regenerate with `code/R/pull_optionmetrics_iv.R` if you have access). Step 12 skips the
implied-volatility panel when the latter is absent.

All other model inputs are calibration constants defined in the code with their sources in
comments (see the main README).
