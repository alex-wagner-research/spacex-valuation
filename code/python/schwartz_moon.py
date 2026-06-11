"""
schwartz_moon.py  --  standalone replication of the classical real-option baseline.

A faithful minimal replication of Schwartz & Moon (2000, "Rational Pricing of Internet
Companies," Financial Analysts Journal 56(3), 62-75), the model the paper's simulation dynamics
descend from. It values an uncertain growth firm whose downside is truncated by an abandonment option
(limited liability: the firm is walked away from when it runs out of cash). The abandonment option
is the embedded real option, and it is pure DOWNSIDE protection -- it cannot inflate the headline
value -- which is exactly the anti-"bullish-pump" property we want.

Model (the minimal faithful subset, all rates per QUARTER, time stepped in quarters, Dt = 1):
  Two stochastic state variables:
    Revenue rate R_t:            dR/R = (mu - lambda1*sigma) dt + sigma dz1     (risk-adjusted)
    Expected growth mu_t:        d.mu = [kappa(mubar - mu) - lambda2*eta] dt + eta dz2   (mean-reverting)
  Signature feature -- uncertainty about the growth rate RESOLVES over time:
    sigma_t = sigma0 e^{-k1 t} + sigmabar (1 - e^{-k1 t})      (revenue vol decays to a floor)
    eta_t   = eta0 e^{-k2 t}                                   (growth vol decays to zero)
  Cost / thin margin:            Cost_t = (alpha + beta) R_t + F
  Cash (the bankruptcy trigger): X_{t+1} = X_t + after-tax cash flow + interest r*X_t
  Loss carry-forward L_t shields tax until exhausted; tax rate tau_c applies only once L_t = 0.
  Bankruptcy / abandonment:      the FIRST time X_t <= 0 the firm is abandoned, salvage 0.
  Risk-neutral value:            V_0 = E[ e^{-r T} X_T ],  bankrupt paths contribute 0.

We validate the implementation by reproducing the paper's Amazon base case before using it.
Then we run an illustrative SpaceX-flavored parameterization and isolate the value of the
abandonment option (value WITH limited liability minus value WITHOUT), using common random numbers.

Runs in a few seconds with numpy; bounded loops; no external services.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np


# --------------------------------------------------------------------------------------
# Parameters (defaults = Schwartz-Moon 2000 Amazon base case, Exhibit 2). Rates per quarter.
# --------------------------------------------------------------------------------------
@dataclass
class SMParams:
    R0: float = 356.0        # initial revenue rate ($M / quarter)
    X0: float = 906.0        # initial cash balance ($M)
    L0: float = 559.0        # initial loss carry-forward ($M)
    mu0: float = 0.11        # initial expected revenue growth (per quarter)
    sigma0: float = 0.10     # initial revenue volatility (per quarter)
    eta0: float = 0.03       # initial growth-rate volatility (per quarter)
    mubar: float = 0.015     # long-run revenue growth (per quarter, ~6%/yr)
    sigmabar: float = 0.05   # long-run revenue volatility (per quarter)
    kappa: float = 0.07      # mean-reversion speed of growth rate (per quarter)
    k1: float = 0.07         # decay speed of revenue volatility
    k2: float = 0.07         # decay speed of growth-rate volatility
    rho: float = 0.0         # correlation of the two shocks
    alpha: float = 0.75      # COGS as a fraction of revenue
    beta: float = 0.19       # variable other-expense fraction of revenue
    F: float = 75.0          # fixed other expenses ($M / quarter)
    tau_c: float = 0.35      # corporate tax rate (applied only once losses exhausted)
    lambda1: float = 0.01    # market price of risk, revenue factor (per quarter)
    lambda2: float = 0.0     # market price of risk, growth factor
    r_annual: float = 0.05   # risk-free rate (per year)
    horizon_years: float = 25.0
    dt_quarters: float = 1.0  # time step = 1 quarter

    @property
    def r_q(self) -> float:
        return self.r_annual / 4.0           # per-quarter risk-free rate

    @property
    def n_steps(self) -> int:
        return int(round(self.horizon_years * 4 / self.dt_quarters))


# --------------------------------------------------------------------------------------
# Core simulation (vectorised over paths). Common random numbers across the two scenarios.
# --------------------------------------------------------------------------------------
def simulate(p: SMParams, n_paths: int = 100_000, seed: int = 2026):
    """Simulate risk-neutral paths and return value samples WITH and WITHOUT the abandonment option.

    Returns a dict with arrays of length n_paths:
      value_opt   : e^{-rT} * X_T with limited liability (bankrupt -> 0)        [the option is ON]
      value_noopt : e^{-rT} * X_T with NO truncation (X may go negative)        [the option is OFF]
      bankrupt    : bool, whether the path ever hit X <= 0
      bankrupt_q  : quarter index of first bankruptcy (n_steps if never)
    and scalar summaries.
    """
    rng = np.random.default_rng(seed)
    dt = p.dt_quarters
    sqrt_dt = np.sqrt(dt)
    N = n_paths

    R = np.full(N, p.R0)
    mu = np.full(N, p.mu0)
    # Two cash tracks sharing the SAME shocks: one truncates at bankruptcy, one never does.
    X_opt = np.full(N, p.X0)
    X_no = np.full(N, p.X0)
    L_opt = np.full(N, p.L0)
    L_no = np.full(N, p.L0)

    alive = np.ones(N, dtype=bool)            # for the option (limited-liability) track
    bankrupt_q = np.full(N, p.n_steps, dtype=int)

    def cash_flow(R_t, X_t, L_t):
        """After-tax cash flow over one step, with loss-carryforward tax shield. Returns (Y, L_next)."""
        interest = p.r_q * X_t
        pretax = (R_t - ((p.alpha + p.beta) * R_t + p.F)) * dt + interest * dt
        L_next = L_t.copy()
        tax = np.zeros_like(R_t)
        pos = pretax >= 0
        # profitable steps: burn down losses first, tax only the excess
        shielded = np.minimum(L_t, np.where(pos, pretax, 0.0))
        taxable = np.where(pos, pretax - shielded, 0.0)
        tax = p.tau_c * taxable
        L_next = np.where(pos, L_t - shielded, L_t - pretax)   # losses (pretax<0) add to L
        Y = pretax - tax
        return Y, L_next

    for t in range(p.n_steps):
        sigma_t = p.sigma0 * np.exp(-p.k1 * t) + p.sigmabar * (1.0 - np.exp(-p.k1 * t))
        eta_t = p.eta0 * np.exp(-p.k2 * t)

        z1 = rng.standard_normal(N)
        if p.rho != 0.0:
            z2 = p.rho * z1 + np.sqrt(1.0 - p.rho**2) * rng.standard_normal(N)
        else:
            z2 = rng.standard_normal(N)

        # cash-flow update BEFORE rolling state forward (uses current R, X, L)
        Y_opt, L_opt = cash_flow(R, X_opt, L_opt)
        Y_no, L_no = cash_flow(R, X_no, L_no)
        X_opt = np.where(alive, X_opt + Y_opt, X_opt)
        X_no = X_no + Y_no

        # detect new bankruptcies on the option track
        newly = alive & (X_opt <= 0.0)
        bankrupt_q = np.where(newly, t, bankrupt_q)
        alive = alive & (~newly)

        # roll the stochastic state forward.
        # Revenue: risk-adjusted log-Euler with Ito correction (their Eq. 17).
        R = R * np.exp((mu - p.lambda1 * sigma_t - 0.5 * sigma_t**2) * dt + sigma_t * sqrt_dt * z1)
        # Growth rate: EXACT Ornstein-Uhlenbeck update (not plain Euler). This avoids the Dt
        # double-count flagged in the paper's printed Eq. 18 and removes the excess growth-rate
        # variance that otherwise inflates both firm value and the bankruptcy rate.
        ekt = np.exp(-p.kappa * dt)
        mu_mean = ekt * mu + (1.0 - ekt) * (p.mubar - p.lambda2 * eta_t / p.kappa)
        ou_sd = eta_t * np.sqrt((1.0 - np.exp(-2.0 * p.kappa * dt)) / (2.0 * p.kappa))
        mu = mu_mean + ou_sd * z2

    disc = np.exp(-p.r_q * p.n_steps)
    bankrupt = bankrupt_q < p.n_steps
    value_opt = np.where(bankrupt, 0.0, disc * X_opt)
    value_no = disc * X_no                                  # no truncation: X_T may be negative

    return {
        "value_opt": value_opt,
        "value_noopt": value_no,
        "bankrupt": bankrupt,
        "bankrupt_q": bankrupt_q,
        "firm_value_opt": float(value_opt.mean()),
        "firm_value_opt_se": float(value_opt.std(ddof=1) / np.sqrt(N)),
        "firm_value_noopt": float(value_no.mean()),
        "option_value": float(value_opt.mean() - value_no.mean()),
        "prob_bankrupt": float(bankrupt.mean()),
        "first_bankrupt_year": (float(bankrupt_q[bankrupt].min()) / 4.0) if bankrupt.any() else None,
        "n_paths": N,
    }


# --------------------------------------------------------------------------------------
# Illustrative SpaceX-flavoured parameterisation (ROUGH, not a real valuation)
# --------------------------------------------------------------------------------------
def spacex_params() -> SMParams:
    """A deliberately rough SpaceX-flavoured calibration, anchored loosely to the 2026 figures
    (revenue ~ $18.7B/yr -> ~$4.67B/quarter; large cash + IPO proceeds; high but mean-reverting
    growth; thin near-term margin widening over time). This is illustrative scaffolding for the
    real-option mechanics, NOT a valuation of SpaceX."""
    return SMParams(
        R0=4670.0,        # ~$18.7B/yr in revenue
        X0=100_000.0,     # ~$25B cash + ~$75B IPO proceeds
        L0=5_000.0,       # modest accumulated losses
        mu0=0.06,         # ~6%/quarter (~26%/yr) initial growth, high but not Amazon-1999 extreme
        sigma0=0.08,
        eta0=0.025,
        mubar=0.0113,     # ~4.56%/yr long-run (Damodaran's terminal growth)
        sigmabar=0.04,
        alpha=0.55,       # higher gross margin than Amazon (hardware+services blend)
        beta=0.15,
        F=1500.0,         # heavy fixed R&D / capex base ($M/quarter)
        tau_c=0.25,
        r_annual=0.0825,  # Damodaran's WACC-ish discount (used here as the discount rate)
        horizon_years=10.0,
    )


# --------------------------------------------------------------------------------------
# Main: validate against the paper, then the illustrative SpaceX run.
# --------------------------------------------------------------------------------------
def main() -> None:
    print("=" * 74)
    print("Rung 0  --  Schwartz-Moon real-option valuation (classical, no quantum)")
    print("=" * 74)

    # ---- Regression test: reproduce the Amazon base case ----
    base = SMParams()
    rb = simulate(base, n_paths=100_000, seed=2026)
    print("Amazon base-case regression test (paper: ~$5,457M, ~27.9% bankruptcy, onset Year 5)")
    print(f"  firm value (option ON) : ${rb['firm_value_opt']:>10,.0f} M  (MC s.e. +/- ${rb['firm_value_opt_se']:,.0f}M)")
    print(f"  P(bankruptcy)          : {rb['prob_bankrupt']*100:>10.1f} %")
    print(f"  first bankruptcy        : year {rb['first_bankrupt_year']}")
    print(f"  value of abandonment opt: ${rb['option_value']:>10,.0f} M "
          f"(= ON ${rb['firm_value_opt']:,.0f} - OFF ${rb['firm_value_noopt']:,.0f})")
    print("-" * 74)

    # ---- Illustrative SpaceX-flavoured run ----
    sx = spacex_params()
    rs = simulate(sx, n_paths=100_000, seed=2026)
    v = rs["value_opt"]
    print("Illustrative SpaceX-flavoured run (ROUGH scaffolding, NOT a valuation):")
    print(f"  firm value (option ON) : ${rs['firm_value_opt']:>12,.0f} M")
    print(f"  P(abandonment)         : {rs['prob_bankrupt']*100:>12.1f} %")
    print(f"  value of abandonment opt: ${rs['option_value']:>12,.0f} M  (downside protection)")
    print(f"  value distribution: 5th pct ${np.quantile(v,0.05):,.0f}M, "
          f"median ${np.quantile(v,0.5):,.0f}M, 95th pct ${np.quantile(v,0.95):,.0f}M")
    print("=" * 74)

    out = Path(__file__).resolve().parents[2] / "output" / "tables"
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "amazon_base": {k: rb[k] for k in
                        ["firm_value_opt", "firm_value_noopt", "option_value",
                         "prob_bankrupt", "first_bankrupt_year", "n_paths"]},
        "amazon_params": asdict(base),
        "spacex_illustrative": {k: rs[k] for k in
                                ["firm_value_opt", "firm_value_noopt", "option_value",
                                 "prob_bankrupt", "n_paths"]},
        "spacex_params": asdict(sx),
    }
    (out / "rung0_schwartz_moon.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"Results written to: {out / 'rung0_schwartz_moon.json'}")


if __name__ == "__main__":
    main()
