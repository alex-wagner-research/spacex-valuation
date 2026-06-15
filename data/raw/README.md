# data/raw

This folder is nearly empty by design: the analysis runs on public SEC documents that the
pipeline downloads for you rather than redistributing.

- `s1_exhibits/spaceexplorationtechnologi.htm` -- the SpaceX Form S-1 main document, carrying the
  full preliminary prospectus text including the financial-statement notes (SEC EDGAR accession
  0001628280-26-036936, filed 2026-05-20). Downloaded automatically by step 0 of
  `code/python/00_master.py`; it appears here after the first run (~1.5 MB, excluded from git). The
  complete exhibit set (merger agreement, award agreements, credit agreements, ...) can be fetched
  with `code/python/fetch_s1_exhibits.py`.
- `post_ipo_day1.json` -- the one file that ships: the template for SpaceX's first trading day
  (June 12, 2026). Fill it via `code/python/fetch_day1.py` after the close; pipeline step 9 then
  computes the paper's postscript numbers.

All other model inputs are calibration constants defined in the code with their sources in
comments (see the main README).
