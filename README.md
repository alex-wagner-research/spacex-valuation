# Replication code — "Valuing SpaceX: Cash Flows versus the Cost of Capital"

Alexander F. Wagner, June 2026. Paper: https://ssrn.com/abstract=6918120

Comments and corrections are very welcome (alexander.wagner@df.uzh.ch). This code was put
together in a short window around a live IPO, so it is entirely possible that not everything
works as intended; if something looks off, it may well be.

```
pip install -r requirements.txt        # numpy, scipy, matplotlib
python code/python/run_valuation.py    # the valuation, decomposed, in ~1 minute
```

`run_valuation.py` is the front door: it runs the three-segment stochastic DCF, prints the
segment values, the equity distribution, and the real-option layer (expansion claims with their
closed-form validation, the Mars claim, the xAI abandonment option), and can invert the model:

```
python code/python/run_valuation.py --wacc 0.07              # your discount rate
python code/python/run_valuation.py --xai-rev 300 --xai-margin 0.30
python code/python/run_valuation.py --invert 135             # implied discount rate at $135/share
```

To reproduce the paper's complete exhibit set instead (all figures, tables, and the macro file
behind every in-text number), run the pipeline:

```
python code/python/00_master.py
```

It downloads its one input (the SpaceX prospectus, a public SEC EDGAR document) if not already
present, runs the analysis in paper order, and writes all outputs in two to three minutes. The
simulations use fixed seeds, so reruns should reproduce the reported numbers.

## The model

The economics lives in two modules; everything else drives them.

- **`spacex_realoptions.py`** — the core of the analysis (paper Sections 4–5, Appendix A): the
  three-segment correlated stochastic DCF (`FirmParams` and `Segment` hold every input of the
  paper's Table 1 — revenue targets, margins, sales-to-capital ratios, volatilities, the 8.25
  percent cost of capital, terminal growth, share count), the two exercise-at-gate expansion
  claims (Starlink direct-to-cell; Starship, gated on a technical trigger), and the Mars
  sovereign-program state tree.
- **`venture_option.py`** — the xAI abandonment option (Section 5.2, Appendix A.2): the
  stand-alone venture model (`VentureParams`) and the Longstaff–Schwartz two-pass least-squares
  Monte Carlo valuation of the annual abandon-or-continue decision.

The hard-coded constants in these modules are calibration inputs, with sources documented in
comments where they are defined (2025 financials from the prospectus; 2036 targets and the
discount rate from Damodaran's June 2026 valuation; margins disciplined by listed
AI-infrastructure comparables; the launch market from government budget documents). No parameter
is tuned to hit a target value.

## Excel companion

`excel/spacex_valuation.xlsx` implements the valuation in formulas for readers who prefer Excel:
the DCF as a classic year-by-year waterfall with a step-by-step terminal value, the expansion
claims by their closed forms, the Mars probability tree, a live 1,000-trial Monte Carlo of the
correlated segment model (press F9), the sum of parts, and the inversion (implied discount rate
at any target price, no macros). Inputs are blue on the Inputs tab with sources; grey italics
quote the Python pipeline's values for checking. The xAI abandonment option is imported (its
least-squares Monte Carlo has no formula representation). Regenerate the workbook after a
recalibration with `python code/python/make_excel_workbook.py` (requires openpyxl).

## Playing with the parameters

To rerun the valuation under your own assumptions:

1. Change inputs where they live — `FirmParams` / `Segment` in `spacex_realoptions.py` (the
   paper's Table 1), `VentureParams` in `venture_option.py`, the option-claim parameters in the
   option functions, or the sampling ranges at the top of `06_layer3_sampling.py` (the paper's
   Table 6).
2. Rerun `python code/python/00_master.py --from 3` (steps 1–2 are text counts and the market
   catalog; they do not depend on the model).
3. Read the results from the console — segment values, the equity distribution, option values
   with the closed-form validation, the one-lever implied values, the implied discount rate, and
   the joint-sampling acceptance shares are all printed — or from the JSONs in `output/tables/`.

## Pipeline map

| Step | Script | Output (paper exhibit) |
|---|---|---|
| 1 | `01_prospectus_text_analysis.py` | Figure 2 (prospectus term frequencies) + counts JSON |
| 2 | `02_spacex_landscape.py` | Figure 1 (valuation landscape) + sourced catalog CSV |
| 3 | `03_decomposition.py` | Figures 3–4 (abandonment distribution; waterfall); segment, scenario, and option values incl. the closed-form validation (Appendix A.2) |
| 4 | `04_inverse_valuation.py` | Figure 5 (what \$1.77T requires); one-lever implied values (Table 4) |
| 5 | `05_physical_implications.py` | physical-units translations (Table 5) |
| 6 | `06_layer3_sampling.py` | Figure 6 (joint acceptance sampling); Appendix B |
| 7 | `07_make_macros.py` | `numbers.tex` + table bodies (Tables 2–5) |
| 8 | `08_fig_first_day.py` | first-day-returns figure for the postscript |

JSON results land in `output/tables/`; figures, table bodies, and `numbers.tex` land in
`paper/draft/output/`, the folder the paper's LaTeX consumes — the paper's in-text numbers are
macros from `numbers.tex` rather than hand-typed values.

Auxiliary, outside the pipeline: `fetch_s1_exhibits.py` (downloads the complete S-1 exhibit set
from EDGAR) and `schwartz_moon.py` (a standalone replication of Schwartz–Moon (2000), the model
the paper's dynamics descend from).

## After the June 12, 2026 listing

The paper gains a short postscript on the first trading day. `fetch_day1.py` fills
`data/raw/post_ipo_day1.json` with the day's official prices; step 9 (`09_post_ipo_update.py`) then
computes the postscript numbers — the first-day return against the IPO literature benchmarks and
the discount rate implied by the closing capitalization — and the figure of step 8 switches its
SpaceX marker from the projected to the observed value. Until that data exists, the pipeline
skips step 9 automatically.

## License

MIT (see LICENSE).
