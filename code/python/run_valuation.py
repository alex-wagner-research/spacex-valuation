r"""
run_valuation.py -- value SpaceX under your own assumptions.

This is the player-oriented entry point: one self-contained driver around the two model modules
(spacex_realoptions.py: the three-segment stochastic DCF, the expansion claims, the Mars tree;
venture_option.py: the xAI abandonment option). It values the firm, prints the decomposition,
and can invert the model for the discount rate a given share price implies. For reproducing the
paper's full exhibit set instead, run 00_master.py.

    python code/python/run_valuation.py                      # the paper's base case
    python code/python/run_valuation.py --wacc 0.07          # your discount rate
    python code/python/run_valuation.py --xai-rev 300 --xai-margin 0.30
    python code/python/run_valuation.py --invert 135         # implied discount rate at $135/share
    python code/python/run_valuation.py --n 20000            # faster, noisier

Overrides (all optional; defaults are the paper's Table 1):
    --wacc            discount rate (decimal, e.g. 0.07)
    --g-term          terminal growth (decimal)
    --launch-rev / --starlink-rev / --xai-rev          2036 revenue targets ($B)
    --launch-margin / --starlink-margin / --xai-margin  terminal operating margins (decimal)
    --n               Monte-Carlo paths (default 100,000)
    --invert PRICE    also solve for the discount rate at which the model value equals
                      PRICE dollars per share (cash flows and the option layer held fixed)
"""

from __future__ import annotations

import argparse
import copy
from math import erf, log, sqrt

import numpy as np

from spacex_realoptions import (FirmParams, simulate, dtc_expansion_option,
                                starship_expansion_option, mars_sovereign_option)
from venture_option import VentureParams, simulate_paths, value_with_option

SHARES_M = 13091.0      # post-offering share count (millions); see FirmParams.shares


def build_params(a) -> FirmParams:
    p = FirmParams()
    if a.wacc is not None:
        p.wacc = a.wacc
    if a.g_term is not None:
        p.g_term = a.g_term
    for s in p.segments:
        key = s.name.lower()
        rev = getattr(a, f"{key}_rev", None)
        mar = getattr(a, f"{key}_margin", None)
        if rev is not None:
            s.rev_target = rev * 1000.0          # $B -> $M
        if mar is not None:
            s.margin_target = mar
    return p


def gate_closed_form(M, I, sigma, tau, r, p_gate=1.0):
    """Standalone closed form of an exercise-at-gate claim (paper Appendix A.2)."""
    Phi = lambda x: 0.5 * (1.0 + erf(x / sqrt(2.0)))
    d1 = (log(M / I) + 0.5 * sigma**2) / sigma
    return p_gate * (M * Phi(d1) - I * Phi(d1 - sigma)) * (1 + r) ** (-tau)


def abandonment_option(n: int):
    """xAI abandonment option value ($M), salvage zero (paper Section 5.2)."""
    vp = VentureParams()
    R, mu, fcf, tv = simulate_paths(vp, n, seed=2026)
    with_opt, abandon_year, _ = value_with_option(vp, R, mu, fcf, tv)
    disc = (1 + vp.r) ** (-np.arange(1, vp.T + 1))
    without = (fcf * disc).sum(axis=1) + tv * disc[-1]
    return float(with_opt.mean() - without.mean()), float((abandon_year <= vp.T).mean())


def implied_wacc(p: FirmParams, target_musd: float, opt_total: float):
    """Bisect for the discount rate at which deterministic value + options = target ($M)."""
    def value(w):
        q = copy.deepcopy(p)
        q.wacc = w
        return simulate(q, n=1, seed=1, stochastic=False)["equity_mean"] + opt_total
    lo, hi = p.g_term + 0.003, 0.30
    if (value(lo) - target_musd) * (value(hi) - target_musd) > 0:
        return None
    for _ in range(60):                       # full bisection: interval -> ~1e-19, no early exit
        mid = 0.5 * (lo + hi)
        if value(mid) > target_musd:          # value decreases in the discount rate
            lo = mid
        else:
            hi = mid
    return mid


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wacc", type=float)
    ap.add_argument("--g-term", type=float, dest="g_term")
    for seg in ["launch", "starlink", "xai"]:
        ap.add_argument(f"--{seg}-rev", type=float, dest=f"{seg}_rev")
        ap.add_argument(f"--{seg}-margin", type=float, dest=f"{seg}_margin")
    ap.add_argument("--n", type=int, default=200_000)
    ap.add_argument("--invert", type=float, metavar="PRICE")
    a = ap.parse_args()

    p = build_params(a)
    print("=" * 78)
    print("INPUTS (paper Table 1 unless overridden)")
    for s in p.segments:
        print(f"  {s.name:<9} rev 2025 ${s.rev0:>8,.0f}M -> 2036 target ${s.rev_target:>9,.0f}M; "
              f"terminal margin {s.margin_target:.0%}; sales-to-capital {s.s2c}")
    print(f"  WACC {p.wacc:.2%}; terminal growth {p.g_term:.2%}; shares {p.shares:,.0f}M; "
          f"cash ${p.cash:,.0f}M + proceeds ${p.ipo_proceeds:,.0f}M - debt ${p.debt:,.0f}M")

    # ---- benchmark DCF ----
    # Deterministic segment values (the paper's Table 1 Value column and the waterfall) and the
    # stochastic distribution, exactly as in 03_decomposition.py (n = 200,000, seed 2026).
    det = simulate(p, n=1, seed=1, stochastic=False)
    sto = simulate(p, n=a.n, seed=2026, stochastic=True)
    eq = sto["equity"]
    print("=" * 78)
    print("BENCHMARK DCF")
    for name, v in det["seg_values"].items():
        print(f"  {name:<9} operating value  ${v:>10,.0f}M   (deterministic)")
    print(f"  Equity value, deterministic: ${det['equity_mean']:,.0f}M "
          f"(${det['equity_mean']/SHARES_M:.0f}/share)")
    print(f"  Monte Carlo ({a.n:,} paths): mean ${eq.mean():,.0f}M "
          f"(MC se ${sto['equity_se']:,.0f}M); "
          f"p5 ${np.quantile(eq, 0.05):,.0f}M | median ${np.quantile(eq, 0.5):,.0f}M "
          f"| p95 ${np.quantile(eq, 0.95):,.0f}M")

    # ---- real options ----
    dtc = dtc_expansion_option(p, sto["core_factor"], invest=12000.0)
    ss = starship_expansion_option(p, sto["core_factor"])
    mars = mars_sovereign_option(p, ss["tech_success"])
    aband, prob_ab = abandonment_option(100_000)   # the paper's venture-model run size
    cf_dtc = gate_closed_form(dtc["E_VDTC"], dtc["invest"], dtc["sigma"], dtc["tau"], p.wacc)
    cf_ss = gate_closed_form(ss["V_central"], ss["invest"], ss["sigma"], ss["tau"], p.wacc,
                             p_gate=ss["p_tech"])
    opt_total = dtc["option_value"] + ss["option_value"] + mars["option_value"]
    print("=" * 78)
    print("REAL OPTIONS")
    print(f"  Starlink direct-to-cell  ${dtc['option_value']:>9,.0f}M  "
          f"(closed form ${cf_dtc:,.0f}M; P(exercise) {dtc['prob_invest']:.0%})")
    print(f"  Starship heavy lift      ${ss['option_value']:>9,.0f}M  "
          f"(closed form ${cf_ss:,.0f}M; P(exercise) {ss['prob_exercise']:.0%})")
    print(f"  Mars sovereign program   ${mars['option_value']:>9,.0f}M")
    print(f"  xAI abandonment          ${aband:>9,.0f}M  (P(abandon) {prob_ab:.0%}; salvage 0)")
    total = eq.mean() + opt_total + aband
    print(f"  Equity + expansion claims + abandonment: ${total:,.0f}M "
          f"(${total/SHARES_M:.0f}/share)")

    # ---- inversion ----
    if a.invert is not None:
        w = implied_wacc(p, a.invert * SHARES_M, opt_total)
        print("=" * 78)
        if w is None:
            print(f"IMPLIED DISCOUNT RATE at ${a.invert}/share: not bracketed in "
                  f"({p.g_term + 0.003:.2%}, 30%)")
        else:
            print(f"IMPLIED DISCOUNT RATE at ${a.invert}/share "
                  f"(${a.invert * SHARES_M / 1e6:.2f}T): {w:.2%}"
                  f"  (cash flows fixed; option layer held at ${opt_total:,.0f}M)")
    print("=" * 78)


if __name__ == "__main__":
    main()
