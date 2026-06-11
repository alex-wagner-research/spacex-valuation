"""
venture_option.py  --  the xAI abandonment option (paper Section 5.2, Appendix A.2).

The economically relevant flexibility in SpaceX is not whole-firm bankruptcy (the firm is too
cash-rich to go insolvent), but the option to abandon a money-losing venture. xAI is modeled as a
stand-alone uncertain venture with Schwartz-Moon-style dynamics (stochastic revenue,
mean-reverting growth with declining volatility, a large fixed cost so the venture is unprofitable
until revenue scales past breakeven), and the firm holds an annual option to stop funding it
rather than carry it to the horizon. The option is valued by Longstaff-Schwartz (2001) two-pass
least-squares Monte Carlo.

Reported objects:
  * value WITH the option  (optimal abandonment),
  * value WITHOUT the option (the venture is funded to the horizon),
  * the option value = WITH - WITHOUT  (pure downside protection, >= 0),
  * how often / when the venture is optimally abandoned.

The WITHOUT value doubles as a governance benchmark: a controlling owner who never abandons
realises the WITHOUT value, so the WITH-WITHOUT gap is what optimal exercise is worth (paper
Section 5.4). Calibration: VentureParams below, each input sourced in its comment (xAI 2025
figures from the prospectus; targets and rates per the paper's Section 4 sources). Real-world
drift discounted at a risk-adjusted venture cost of capital, the practitioner convention.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np


@dataclass
class VentureParams:
    # Calibrated to xAI per Damodaran's June-2026 numbers: 2025 revenue ~$3.2B, 2036 target ~$160B
    # (high but declining growth), operating margin cut to 25% under intense competition (OpenAI/
    # Anthropic/Google), and ~$14B of 2025 reinvestment (capex + R&D) -> a large fixed cost revenue
    # must scale past to profit. Competition is the engine of the downside: paths that stall below
    # breakeven are "lost the AI race," and the abandonment option is the value of cutting those losses.
    R0: float = 3200.0       # xAI 2025 revenue ($M)
    mu0: float = 0.40        # initial annual revenue growth (~40%, toward the $160B-2036 target)
    mubar: float = 0.05      # long-run growth
    kappa: float = 0.35      # growth mean-reversion speed
    sigma0: float = 0.35     # initial revenue volatility (high: intense AI competition)
    sigmabar: float = 0.15   # long-run revenue volatility
    eta0: float = 0.15       # initial growth-rate volatility
    k1: float = 0.20         # decay of revenue volatility
    k2: float = 0.35         # decay of growth-rate volatility (uncertainty resolves)
    cm: float = 0.60         # contribution margin on revenue
    fixed_cost: float = 5000.0    # annual FIXED cost ($M): ongoing R&D/baseline compute (~xAI's R&D). The ~$9B data-center capex is GROWTH investment, captured via reinvestment, NOT fixed. Breakeven ~ F/cm = $8.3B
    s2c: float = 2.0         # sales-to-capital (reinvestment intensity)
    tau: float = 0.25        # tax rate (Damodaran's marginal rate)
    r: float = 0.12          # venture cost of capital (above the firm WACC; xAI is riskier)
    g_term: float = 0.0456   # terminal growth (= riskfree, Damodaran)
    salvage: float = 0.0     # recovery on abandonment (conservative lower bound)
    T: int = 11              # 2025 -> 2036 horizon / annual decisions


def simulate_paths(p: VentureParams, n: int, seed: int):
    """Simulate annual (R, mu) paths and the implied free cash flows and terminal value."""
    rng = np.random.default_rng(seed)
    R = np.empty((n, p.T + 1))
    mu = np.empty((n, p.T + 1))
    R[:, 0] = p.R0
    mu[:, 0] = p.mu0
    for t in range(1, p.T + 1):
        sig = p.sigma0 * np.exp(-p.k1 * t) + p.sigmabar * (1 - np.exp(-p.k1 * t))
        eta = p.eta0 * np.exp(-p.k2 * t)
        z1 = rng.standard_normal(n)
        z2 = rng.standard_normal(n)
        # revenue grows at last year's expected growth, with Ito correction
        R[:, t] = R[:, t - 1] * np.exp((mu[:, t - 1] - 0.5 * sig**2) + sig * z1)
        # exact-OU update of the expected growth rate
        ek = np.exp(-p.kappa)
        ou_sd = eta * np.sqrt((1 - np.exp(-2 * p.kappa)) / (2 * p.kappa))
        mu[:, t] = ek * mu[:, t - 1] + (1 - ek) * p.mubar + ou_sd * z2

    # Operating leverage: contribution margin on revenue minus a large fixed cost. The venture
    # only becomes profitable once revenue scales past breakeven (~ fixed_cost / cm); paths whose
    # revenue stalls below that stay perpetual money-losers -- which is what the option abandons.
    Rt = R[:, 1:]                       # revenue in years 1..T
    dR = np.maximum(R[:, 1:] - R[:, :-1], 0.0)
    ebit = p.cm * Rt - p.fixed_cost
    tax = p.tau * np.maximum(ebit, 0.0)
    reinv = dR / p.s2c
    fcf = ebit - tax - reinv            # free cash flow, years 1..T (negative until revenue scales)

    # terminal going-concern value at T (Gordon), floored at 0 (you would abandon a negative one)
    ebit_T_aftertax = ebit[:, -1] * (1 - p.tau)
    tv = np.maximum(0.0, ebit_T_aftertax * (1 + p.g_term) / (p.r - p.g_term))

    return R, mu, fcf, tv


def _basis(Rprev, muprev, R0):
    """Polynomial regression basis in (log-revenue, growth), standardized for conditioning."""
    x = np.log(np.maximum(Rprev, 1e-6) / R0)
    m = muprev
    cols = [np.ones_like(x), x, m, x**2, m**2, x * m, x**3]
    return np.column_stack(cols)


def value_with_option(p: VentureParams, R, mu, fcf, tv):
    """Two-pass Longstaff-Schwartz: backward to learn the abandon policy, forward to apply it."""
    n, T = fcf.shape
    disc = (1 + p.r) ** (-np.arange(1, T + 1))      # PV factors for years 1..T

    # ---- Pass 1: backward induction to estimate continuation-value coefficients ----
    coefs = [None] * (T + 1)
    vtg = np.zeros(n)                               # value-to-go (PV@0) from after the horizon
    for t in range(T, 0, -1):
        cf_pv = fcf[:, t - 1] * disc[t - 1]
        tv_pv = tv * disc[T - 1] if t == T else 0.0
        cont_realized = cf_pv + tv_pv + vtg         # PV@0 of operating year t then acting optimally
        X = _basis(R[:, t - 1], mu[:, t - 1], p.R0)
        coef, *_ = np.linalg.lstsq(X, cont_realized, rcond=None)
        coefs[t] = coef
        cont_hat = X @ coef
        operate = cont_hat > p.salvage              # abandon (take salvage) if expected continue < salvage
        vtg = np.where(operate, cont_realized, p.salvage)

    # ---- Pass 2: forward application of the learned policy (gives value + abandonment timing) ----
    alive = np.ones(n, dtype=bool)
    pathval = np.zeros(n)
    abandon_year = np.full(n, T + 1)                # T+1 = never abandoned
    for t in range(1, T + 1):
        X = _basis(R[:, t - 1], mu[:, t - 1], p.R0)
        cont_hat = X @ coefs[t]
        decide_abandon = alive & (cont_hat <= p.salvage)
        pathval = np.where(decide_abandon, pathval + p.salvage * disc[t - 1], pathval)
        abandon_year = np.where(decide_abandon, t, abandon_year)
        alive = alive & (~decide_abandon)
        # operating paths collect this year's FCF (and TV at the horizon)
        pathval = np.where(alive, pathval + fcf[:, t - 1] * disc[t - 1], pathval)
        if t == T:
            pathval = np.where(alive, pathval + tv * disc[T - 1], pathval)

    return pathval, abandon_year, float(vtg.mean())


def main():
    p = VentureParams()
    n = 100_000
    R, mu, fcf, tv = simulate_paths(p, n, seed=2026)
    disc = (1 + p.r) ** (-np.arange(1, p.T + 1))

    # WITHOUT the option: fund the venture all the way to the horizon (no abandonment).
    value_full = (fcf * disc[None, :]).sum(axis=1) + tv * disc[-1]
    v_without = float(value_full.mean())

    # WITH the option: optimal abandonment via Longstaff-Schwartz.
    pathval, abandon_year, v_with_backward = value_with_option(p, R, mu, fcf, tv)
    v_with = float(pathval.mean())
    se_with = float(pathval.std(ddof=1) / np.sqrt(n))

    abandoned = abandon_year <= p.T
    option_value = v_with - v_without

    print("=" * 76)
    print("Rung 0 for SpaceX  --  xAI abandonment option (classical Longstaff-Schwartz)")
    print("=" * 76)
    print(f"Illustrative xAI venture: R0=${p.R0:,.0f}M, growth {p.mu0:.0%}->{p.mubar:.0%}, "
          f"contribution margin {p.cm:.0%}, fixed cost ${p.fixed_cost:,.0f}M "
          f"(breakeven rev ~${p.fixed_cost/p.cm:,.0f}M), discount {p.r:.0%}, horizon {p.T}y")
    print("-" * 76)
    print(f"  Value WITHOUT option (fund to horizon)   : ${v_without:>12,.0f} M")
    print(f"  Value WITH option (optimal abandonment)  : ${v_with:>12,.0f} M  (s.e. +/- ${se_with:,.0f}M)")
    print(f"    [backward-induction cross-check]       : ${v_with_backward:>12,.0f} M")
    print(f"  ABANDONMENT OPTION VALUE                 : ${option_value:>12,.0f} M  (downside protection)")
    print(f"  P(abandon within horizon)                : {abandoned.mean()*100:>12.1f} %")
    if abandoned.any():
        print(f"  median abandonment year (when abandoned) : {np.median(abandon_year[abandoned]):>12.0f}")
    print(f"  value distribution WITH option: 5th ${np.quantile(pathval,0.05):,.0f}M, "
          f"median ${np.quantile(pathval,0.5):,.0f}M, 95th ${np.quantile(pathval,0.95):,.0f}M")
    print("=" * 76)

    out = Path(__file__).resolve().parents[2] / "output" / "tables"
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "params": asdict(p),
        "value_without_option": v_without,
        "value_with_option": v_with,
        "value_with_option_se": se_with,
        "option_value": option_value,
        "prob_abandon": float(abandoned.mean()),
        "n_paths": n,
    }
    (out / "rung0_xai_option.json").write_text(json.dumps(payload, indent=2))
    print(f"Results written to: {out / 'rung0_xai_option.json'}")


if __name__ == "__main__":
    main()
