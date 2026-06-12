r"""
09_post_ipo_update.py -- turn the first trading day into the paper's Postscript numbers.

Workflow (the day after listing):
  1. Fill data/raw/post_ipo_day1.json with the observed prices (open, close, high, low, volume).
  2. Run this script. It computes the first-day return, locates it against the literature
     benchmarks, computes money left on the table, and inverts the paper's valuation model
     (same machinery as 04_inverse_valuation.py: deterministic segment value + base option layer)
     for the discount rate implied by the opening and closing market capitalizations.
  3. It writes paper/draft/output/postipo.tex with one macro per number.
  4. Flip \postipotrue in paper/draft/main.tex and recompile.

Literature constants (each verified against the cited primary document):
  * Ritter (2026), "Initial Public Offerings: Updated Statistics," May 18, 2026 vintage.
    Table 1 (1980-2025, 9,343 IPOs): mean first-day return 19.0% (equal-weighted), median 7.0%;
    aggregate money left on the table $250.1B. Table 1a: 16.5% of IPOs closed below the offer
    (1980-2025); 23.9% in 2001-2025. Table 2: mean first-day return for issuers with trailing
    sales >= $500M (Jan-2024 dollars) is 13.3% in 2001-2025 (N=749).
  * Lowry, Officer, Schwert (2010, JF 65(2), 425-465): initial returns 1965-2005 average 22%
    with a cross-sectional standard deviation of 55%; nearly one-third are negative; they
    measure initial returns at the 21st trading day to avoid price-support contamination.
  * Loughran, Ritter (2004, FM 33(3), 5-37): money on the table = (first closing price - offer
    price) x shares sold.
"""

from __future__ import annotations

import json
from pathlib import Path

from run_valuation import implied_wacc as _solve_wacc
from spacex_realoptions import FirmParams

ROOT = Path(__file__).resolve().parents[2]
DAY1 = ROOT / "data" / "raw" / "post_ipo_day1.json"
OUT = ROOT / "paper" / "draft" / "output" / "postipo.tex"

# Base option layer and supported range from the decomposition results (pipeline step 3)
_dec = json.loads((ROOT / "output" / "tables" / "decomposition.json").read_text())
OPT_BASE = sum(v for k, v in _dec["options"].items() if k != "Abandonment")

OFFER = 135.0
SHARES_M = 13091.0        # post-IPO shares outstanding (millions), as in the paper
RF = 4.56                 # June 2026 risk-free rate (percent), as in the paper

# Literature constants (sources in the module docstring)
RITTER_MEAN, RITTER_MEDIAN, RITTER_NEG = 19.0, 7.0, 16.5
RITTER_NEG_RECENT = 23.9          # 2001-2025 share of first-day returns < 0
RITTER_BIG_MEAN = 13.3            # sales >= $500M (2024 $), 2001-2025
RITTER_TABLE_AGG_B = 250.1        # aggregate money left on the table 1980-2025, $B
LOS_MEAN, LOS_SD = 22.0, 55.0     # 1965-2005 initial returns: mean, cross-sectional SD (%)

# Listing-day reporting, all from the FT live blog of June 12, 2026 ("SpaceX live: Elon Musk
# becomes trillionaire as SpaceX soars in Wall Street debut"; PDF archived in Literature/)
FT_TURNOVER_B = 81.5              # dollar value of shares traded on day 1 ($B)
MORNINGSTAR_SH = 63               # Morningstar fair-value estimate, $/share ("probably worth")
GOLDMAN_XAI_2030_B = 322          # Goldman projection: AI-unit revenue needed by 2030 ($B)
PRED_EOD_LO_T, PRED_EOD_HI_T = 2.2, 2.4   # same-day Polymarket / IG expected closing cap ($T)
PERP_JUNE11 = 162.0               # June 11 pre-listing perpetual-futures level, $/share
                                  # (already cited in Sec. 3 of the paper via CNBC, June 10-11)
IND_HIGH = 175                    # highest pre-open indication, $/share (early quotes)

# Ritter, "Money Left on the Table in IPOs by Firm" (May 15, 2026 vintage), rank 1 of the
# listing: Visa, March 2008, $5,075,000,000 (Alibaba's 2014 ADR left $8.29B but is excluded
# from the listing by construction)
RITTER_TOP_US_B = 5.1


def implied_wacc(cap_musd: float) -> float | None:
    """Discount rate at which deterministic value + base options equals cap ($M)."""
    return _solve_wacc(FirmParams(), cap_musd, OPT_BASE)


def main():
    d = json.loads(DAY1.read_text(encoding="utf-8-sig"))
    if d.get("open") is None or d.get("close") is None:
        raise SystemExit(f"Fill open/close in {DAY1} first (currently null).")

    o, c = float(d["open"]), float(d["close"])
    hi = d.get("intraday_high")
    lo = d.get("intraday_low")
    shares_sold_m = float(d.get("shares_offered_m") or 555.6)

    pop_open = (o / OFFER - 1) * 100
    pop_close = (c / OFFER - 1) * 100
    cap_open_t = o * SHARES_M / 1e6
    cap_close_t = c * SHARES_M / 1e6
    table_b = (c - OFFER) * shares_sold_m / 1000          # Loughran-Ritter money on the table
    sd_units_all = (pop_close - LOS_MEAN) / LOS_SD        # vs the all-IPO distribution
    dist_big = pop_close - RITTER_BIG_MEAN                # vs the large-issuer mean (pp)
    vol_m = float(d.get("volume_mshares") or 0)
    vol_pct_sold = vol_m / shares_sold_m * 100            # day-1 volume vs shares sold
    pop_high = (float(hi) / OFFER - 1) * 100 if hi is not None else None
    cap_high_t = float(hi) * SHARES_M / 1e6 if hi is not None else None
    perp_gap_pct = abs(PERP_JUNE11 / c - 1) * 100         # June 11 futures vs actual close

    w_open = implied_wacc(o * SHARES_M)
    w_close = implied_wacc(c * SHARES_M)

    def pct(x, dp=1):
        return f"{x:.{dp}f}"

    L = ["% post-IPO macros -- generated by 09_post_ipo_update.py; do not edit by hand",
         f"\\newcommand{{\\poDate}}{{{d.get('date', '2026-06-12')}}}",
         f"\\newcommand{{\\poOpen}}{{{o:.2f}}}",
         f"\\newcommand{{\\poClose}}{{{c:.2f}}}",
         f"\\newcommand{{\\poPopOpenPct}}{{{pct(pop_open)}}}",
         f"\\newcommand{{\\poPopClosePct}}{{{pct(pop_close)}}}",
         f"\\newcommand{{\\poCapOpenT}}{{{cap_open_t:.2f}}}",
         f"\\newcommand{{\\poCapCloseT}}{{{cap_close_t:.2f}}}",
         f"\\newcommand{{\\poTableB}}{{{table_b:.1f}}}",
         f"\\newcommand{{\\poSharesSoldM}}{{{shares_sold_m:.0f}}}",
         f"\\newcommand{{\\poFloatPct}}{{{shares_sold_m / SHARES_M * 100:.0f}}}",
         f"\\newcommand{{\\poSdUnitsAll}}{{{abs(sd_units_all):.2f}}}",
         f"\\newcommand{{\\poVolM}}{{{vol_m:.0f}}}",
         f"\\newcommand{{\\poVolPctSold}}{{{vol_pct_sold:.0f}}}",
         f"\\newcommand{{\\poTurnoverB}}{{{FT_TURNOVER_B:.0f}}}",
         f"\\newcommand{{\\poMorningstarSh}}{{{MORNINGSTAR_SH}}}",
         f"\\newcommand{{\\poGoldmanXaiB}}{{{GOLDMAN_XAI_2030_B}}}",
         f"\\newcommand{{\\poPredLoT}}{{{PRED_EOD_LO_T}}}",
         f"\\newcommand{{\\poPredHiT}}{{{PRED_EOD_HI_T}}}",
         f"\\newcommand{{\\poPerpGapPct}}{{{perp_gap_pct:.1f}}}",
         f"\\newcommand{{\\poIndHigh}}{{{IND_HIGH}}}",
         f"\\newcommand{{\\poRitterTopB}}{{{RITTER_TOP_US_B}}}",
         f"\\newcommand{{\\poDistBigPp}}{{{abs(dist_big):.1f}}}",
         f"\\newcommand{{\\poWaccOpenPct}}{{{pct(w_open * 100, 2) if w_open else '--'}}}",
         f"\\newcommand{{\\poWaccClosePct}}{{{pct(w_close * 100, 2) if w_close else '--'}}}",
         f"\\newcommand{{\\poErpClosePp}}{{{pct(w_close * 100 - RF, 1) if w_close else '--'}}}",
         # literature constants, macro-driven like every other number
         f"\\newcommand{{\\poRitterMeanPct}}{{{RITTER_MEAN}}}",
         f"\\newcommand{{\\poRitterMedianPct}}{{{RITTER_MEDIAN}}}",
         f"\\newcommand{{\\poRitterNegPct}}{{{RITTER_NEG}}}",
         f"\\newcommand{{\\poRitterNegRecentPct}}{{{RITTER_NEG_RECENT}}}",
         f"\\newcommand{{\\poRitterBigMeanPct}}{{{RITTER_BIG_MEAN}}}",
         f"\\newcommand{{\\poRitterAggB}}{{{RITTER_TABLE_AGG_B}}}",
         f"\\newcommand{{\\poLosMeanPct}}{{{LOS_MEAN:.0f}}}",
         f"\\newcommand{{\\poLosSdPct}}{{{LOS_SD:.0f}}}",
         # the paper's supported value range, translated to dollars per share
         f"\\newcommand{{\\poGroundedLoSh}}{{{_dec['grounded_total_range'][0] / SHARES_M:.0f}}}",
         f"\\newcommand{{\\poGroundedHiSh}}{{{_dec['grounded_total_range'][1] / SHARES_M:.0f}}}"]
    if hi is not None and lo is not None:
        L += [f"\\newcommand{{\\poHigh}}{{{float(hi):.2f}}}",
              f"\\newcommand{{\\poLow}}{{{float(lo):.2f}}}",
              f"\\newcommand{{\\poPopHighPct}}{{{pop_high:.1f}}}",
              f"\\newcommand{{\\poCapHighT}}{{{cap_high_t:.2f}}}"]

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"Day 1: open {o} ({pop_open:+.1f}%), close {c} ({pop_close:+.1f}%), "
          f"cap at close ${cap_close_t:.2f}T")
    print(f"Money on the table: ${table_b:.1f}B on {shares_sold_m:.0f}M shares sold")
    print(f"Implied WACC: open {w_open*100:.2f}%  close {w_close*100:.2f}%  "
          f"(ERP at close {w_close*100-RF:.1f}pp over {RF}% risk-free)")
    print("Macros written:", OUT)


if __name__ == "__main__":
    main()
