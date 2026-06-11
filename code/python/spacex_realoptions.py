"""
spacex_realoptions.py  --  the benchmark model and the expansion/Mars claims (paper Sections 4-5,
Appendix A).

The benchmark: a multi-segment, correlated, stochastic DCF of SpaceX. Three operating segments --
Launch, Starlink, and xAI -- each with a stochastic revenue path that grows from its 2025 base
(prospectus figures) toward a 2036 target (Damodaran's June 2026 forecast, the most detailed
public one), an operating margin ramping to a comparables-disciplined terminal level, reinvestment
via a sales-to-capital ratio, and a Gordon terminal value. Segments are correlated through a
common demand factor. Monte Carlo (200,000 paths in the paper's runs) gives the distribution of
equity value; the
paper's Table 1 lists every input, and Appendix A.1 states the dynamics.

Also here: the exercise-at-gate expansion claims (Starlink direct-to-cell; Starship heavy-lift,
gated on a technical trigger) and the Mars sovereign-program state tree, priced on the same paths
(Appendix A.2). Damodaran's deterministic "expansion options" line is deliberately EXCLUDED from
the benchmark segments -- expansion enters as the explicitly priced option claims instead, so the
two are never double-counted.

Every calibration constant carries its source in a comment where it is defined (FirmParams, the
option functions). No parameter is tuned to hit a target value. Monte-Carlo standard errors are
reported throughout.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

import numpy as np


# --------------------------------------------------------------------------------------
# Segment and firm calibration (Damodaran, post-prospectus June 2026)
# --------------------------------------------------------------------------------------
@dataclass
class Segment:
    name: str
    rev0: float          # 2025 revenue ($M)
    rev_target: float    # 2036 target revenue ($M)
    margin0: float       # current operating margin
    margin_target: float # 2036 target operating margin
    s2c: float           # sales-to-capital (reinvestment intensity)
    vol0: float          # initial annual revenue-growth volatility
    volbar: float        # long-run revenue-growth volatility


@dataclass
class FirmParams:
    wacc: float = 0.0825
    g_term: float = 0.0456        # terminal growth = riskfree (Damodaran convention)
    roic_term: float = 0.15       # terminal return on invested capital (sets reinvestment in perpetuity)
    tax_eff: float = 0.10         # current effective tax rate
    tax_marg: float = 0.25        # marginal tax rate (ramped to over the horizon)
    cash: float = 24747.0         # cash ($M)
    debt: float = 22896.0         # debt ($M)
    ipo_proceeds: float = 75000.0
    shares: float = 13091.0       # post-IPO share count (millions): 12,535.3 pre-offering + 555.6
                                  # new primary shares (consistent with $135/sh x 13,091M = $1.77T).
                                  # Musk's ~1,302M unvested restricted award shares are excluded:
                                  # vesting is deemed improbable in the audited notes.
    rho: float = 0.30             # cross-segment correlation (common demand factor)
    k_vol: float = 0.20           # decay rate of growth volatility (uncertainty resolves)
    T: int = 11                   # 2025 -> 2036
    segments: list = field(default_factory=lambda: [
        Segment("Launch",   4086.0,  40000.0, 0.30, 0.45, 3.5, 0.18, 0.08),
        Segment("Starlink", 11387.0, 120000.0, 0.35, 0.60, 4.0, 0.22, 0.10),
        Segment("xAI",      3201.0,  160000.0, -0.30, 0.25, 2.0, 0.40, 0.15),
    ])


def simulate(p: FirmParams, n: int = 100_000, seed: int = 2026, stochastic: bool = True):
    """Monte-Carlo the correlated multi-segment DCF; return equity value samples and summaries."""
    rng = np.random.default_rng(seed)
    T = p.T
    disc = (1 + p.wacc) ** (-np.arange(1, T + 1))
    tax_path = p.tax_eff + (p.tax_marg - p.tax_eff) * (np.arange(1, T + 1) / T)

    # Common demand factor, drawn ONCE per year and SHARED across segments (so the segments are
    # genuinely correlated at rho through this factor, plus an idiosyncratic shock per segment).
    F = rng.standard_normal((T, n)) if stochastic else None
    op_value = np.zeros(n)
    seg_values = {}
    for s in p.segments:
        # expected geometric growth that carries rev0 to rev_target over T years
        g_exp = (s.rev_target / s.rev0) ** (1.0 / T) - 1.0
        drift = np.log(1.0 + g_exp)

        R = np.full(n, s.rev0)
        Rprev = R.copy()
        pv = np.zeros(n)
        margins = s.margin0 + (s.margin_target - s.margin0) * (np.arange(1, T + 1) / T)

        for t in range(1, T + 1):
            vol = (s.vol0 * np.exp(-p.k_vol * t) + s.volbar * (1 - np.exp(-p.k_vol * t))) if stochastic else 0.0
            # correlated shock: shared common factor F[t-1] plus a segment-idiosyncratic component
            if stochastic:
                eps = rng.standard_normal(n)
                z = np.sqrt(p.rho) * F[t - 1] + np.sqrt(1 - p.rho) * eps
            else:
                z = 0.0
            Rprev = R
            R = R * np.exp(drift - 0.5 * vol**2 + vol * z)

            ebit = margins[t - 1] * R
            tax = tax_path[t - 1] * np.maximum(ebit, 0.0)
            reinv = np.maximum(R - Rprev, 0.0) / s.s2c
            fcf = ebit - tax - reinv
            pv += fcf * disc[t - 1]

        # Gordon terminal value on year-T after-tax EBIT, net of perpetuity reinvestment g/ROIC
        ebit_T = margins[-1] * R
        reinv_rate = p.g_term / p.roic_term
        fcff_term = ebit_T * (1 - p.tax_marg) * (1 + p.g_term) * (1 - reinv_rate)
        tv = fcff_term / (p.wacc - p.g_term)
        pv += tv * disc[-1]

        seg_values[s.name] = float(pv.mean())
        op_value += pv

    equity = op_value + p.cash + p.ipo_proceeds - p.debt
    per_share = equity / p.shares
    # standardized aggregate of the common factor (a per-path proxy for how well the core did),
    # used to CORRELATE the expansion business with core success.
    core_factor = (F.sum(axis=0) / np.sqrt(T)) if stochastic else np.zeros(n)
    return {
        "equity": equity,
        "per_share": per_share,
        "equity_mean": float(equity.mean()),
        "equity_se": float(equity.std(ddof=1) / np.sqrt(n)) if n > 1 else 0.0,
        "per_share_mean": float(per_share.mean()),
        "seg_values": seg_values,
        "core_factor": core_factor,
        "n": n,
    }


# --------------------------------------------------------------------------------------
# Expansion real option #1: Starlink direct-to-cell / next-generation constellation
# --------------------------------------------------------------------------------------
# "Invest in" the next-gen, Starship-launched high-capacity constellation + direct-to-cell
# capability, to enter the satellite-to-phone market. The market is forecast anywhere from
# ~$2.6B (narrow D2D, 2030) to ~$12B (smartphone D2D, Omdia 2030) to ~$100B long-run -- a ~40x
# range, which IS the uncertainty the option lives on. We value the gross DTC business as a small
# Schwartz-Moon-style segment, then treat entry as an option: at year tau the firm pays an
# irreversible investment I and unlocks the (uncertain, core-correlated) DTC business only if it is
# worth more than I. Pure growth option; its value comes from NOT investing when DTC fails to scale.
DTC_SEGMENT = Segment("DTC", rev0=500.0, rev_target=15000.0, margin0=-0.20, margin_target=0.55,
                      s2c=4.0, vol0=0.30, volbar=0.12)


def dtc_business_value(p: FirmParams) -> float:
    """Deterministic present value E[V_DTC] of the DTC business if fully pursued (gross of entry I)."""
    one = FirmParams(wacc=p.wacc, g_term=p.g_term, roic_term=p.roic_term, tax_eff=p.tax_eff,
                     tax_marg=p.tax_marg, cash=0.0, debt=0.0, ipo_proceeds=0.0, shares=1.0,
                     segments=[DTC_SEGMENT])
    return simulate(one, n=1, stochastic=False)["seg_values"]["DTC"]


def dtc_expansion_option(p, core_factor, invest, tau=4, sigma_dtc=0.55, rho_dtc=0.5, seed=7,
                         E_V_override=None):
    """Growth option: invest I at year tau iff the (core-correlated) DTC business value exceeds I.

    E_V_override allows sensitivity analysis (e.g., a competition haircut on the DTC business value).
    """
    n = len(core_factor)
    rng = np.random.default_rng(seed)
    E_V = dtc_business_value(p) if E_V_override is None else E_V_override
    u = rng.standard_normal(n)
    shock = np.sqrt(rho_dtc) * core_factor + np.sqrt(1 - rho_dtc) * u
    V = E_V * np.exp(sigma_dtc * shock - 0.5 * sigma_dtc**2)     # lognormal, mean E_V, core-correlated
    disc_tau = (1 + p.wacc) ** (-tau)
    payoff = np.maximum(V - invest, 0.0) * disc_tau              # real option: invest only if V > I
    passive = (V - invest) * disc_tau                            # passive (always invest), for contrast
    return {"E_VDTC": E_V, "invest": invest, "tau": tau, "sigma": sigma_dtc, "rho": rho_dtc,
            "option_value": float(payoff.mean()), "option_se": float(payoff.std(ddof=1) / np.sqrt(n)),
            "passive_value": float(passive.mean()), "prob_invest": float((V > invest).mean())}


# --------------------------------------------------------------------------------------
# Expansion real option #2: Starship-enabled heavy-lift markets (NOT Mars)
# --------------------------------------------------------------------------------------
# The value Starship unlocks is the launch-addressable government + commercial pool of
# ~$14-41B/yr (national-security launch per Congressional Research Service, "National Security
# Space Launch," IF12900; NASA program budgets per NASA OIG documents; commercial constellations
# and nascent cargo per the industry assessments cited in paper Appendix A.3 -- all URLs there).
# That pool capitalizes to a central gross underlying V ~ $110B (range ~$40-250B). The
# irreversible investment I ~ $30B (Starship development spend to date >$15B plus ~$10-25B of
# launch/production infrastructure; sources in Appendix A.3). The option is gated by a TECHNICAL
# trigger not yet met: demonstrated reusable marginal cost <= ~$200/kg AND cadence >= ~25
# launches/yr with upper-stage reuse (the engineering assessments in Appendix A.3); p_tech = 0.60
# is this paper's judgment, varied in the inversion. With probability (1 - p_tech) the trigger
# never fires and I is never sunk -- that gate is the source of the option value. Mars is modeled
# separately (next section) as a sovereign-program claim with no commercial base-case cash flow.
# These defaults flow into the paper through decomposition.json and 07_make_macros.py, so the
# paper's Section 5 and Appendix A quote them via macros -- editing them here updates the paper
# on the next pipeline run.
def starship_expansion_option(p, core_factor, V_central=110000.0, invest=30000.0, p_tech=0.60,
                              tau=5, sigma=0.50, rho=0.40, seed=11, tech_success=None):
    n = len(core_factor)
    rng = np.random.default_rng(seed)
    if tech_success is None:
        tech_success = rng.random(n) < p_tech                # Starship achieves the reusability trigger?
    u = rng.standard_normal(n)
    shock = np.sqrt(rho) * core_factor + np.sqrt(1 - rho) * u
    V = V_central * np.exp(sigma * shock - 0.5 * sigma**2)   # gross value of unlocked launch markets
    disc_tau = (1 + p.wacc) ** (-tau)
    payoff = np.where(tech_success, np.maximum(V - invest, 0.0), 0.0) * disc_tau
    return {"V_central": V_central, "invest": invest, "p_tech": p_tech, "tau": tau, "sigma": sigma,
            "option_value": float(payoff.mean()), "option_se": float(payoff.std(ddof=1) / np.sqrt(n)),
            "prob_exercise": float((tech_success & (V > invest)).mean()),
            "tech_success": tech_success}


# --------------------------------------------------------------------------------------
# Expansion real option #3: Mars as a SOVEREIGN-PROGRAM contractor option (grounded)
# --------------------------------------------------------------------------------------
# The grounded reframe: Mars colonization has no commodity-export business model, but neither does
# Antarctica or the ISS -- and the US has funded both for decades. The right question is what a
# sovereign Mars program would PAY ITS SOLE-CAPABLE PRIME CONTRACTOR. Anchors (all government-grade
# sources; see progress log / research report):
#   * Revealed preference: ISS US share ~$3.1B/yr (OIG); Artemis ~$93B cumulative FY12-25 (~$7.5B/yr,
#     OIG) FOR THE MOON; US Antarctic Program ~$0.5B/yr -- ~$11B/yr of permanent revenue-free
#     sovereign-presence spending already exists.
#   * Crewed-Mars program cost studies: ~$100B (austere, JPL/expert) to ~$500B (NASA-affiliated),
#     with the 1989 SEI (~$450-500B then-year) as the priced-and-refused ceiling. That cost IS the
#     contractor revenue pool.
#   * Capture precedent: SpaceX HLS $2.89B + $1.15B (the Moon-lander prime); MSR commercial-
#     alternative study award 2024; ~$13B NASA contracts over a decade.
#   * Policy now: Congress enacted a "Mars Future Missions" line ($110M, Jan 2026); FY26 request
#     included $1B for crewed-Mars investments. The small state is essentially already realized.
# Structure: compound on the Starship technical gate (SAME tech draws as option #2), then a program-
# size state tree {none, small, medium, large} with sourced annual SpaceX revenue capture, valued as
# a perpetuity at WACC from program start tau, net of Mars-specific co-investment (HLS precedent:
# the government pays development, but the contractor co-invests).
# S-1 cross-checks (paper Section 3): (i) the company's own audited notes deem
# the 1M-person colony milestone "improbable" (ASC 718), consistent with this tree assigning the
# colony state ~zero weight beyond the "large" sovereign program; (ii) Musk's conjunctive award
# transfers ~1B Class B shares (~7% diluted) precisely in colony states, so the extreme tail is
# partially pre-sold to the CEO -- outside shareholders' Mars upside is further dampened; (iii) the
# S-1's use-of-proceeds funds AI compute / launch infra / constellations, NOT Mars -- supporting the
# sovereign-program (not company-funded) channel as the Mars cash-flow model.
def mars_sovereign_option(p, tech_success, tau=10, margin=0.30, seed=13,
                          # state: (annual SpaceX revenue $M/yr, co-investment $M, prob)
                          # small is ~unconditional (robotic line already appropriated);
                          # medium/large REQUIRE the Starship gate.
                          rev_small=500.0, p_small=0.9, inv_small=0.0,
                          rev_med=2500.0, p_med_given_tech=0.25, inv_med=5000.0,
                          rev_large=10000.0, p_large_given_med=0.25, inv_large=15000.0):
    n = len(tech_success)
    rng = np.random.default_rng(seed)
    u1, u2, u3 = rng.random(n), rng.random(n), rng.random(n)

    small = u1 < p_small
    medium = tech_success & (u2 < p_med_given_tech)
    large = medium & (u3 < p_large_given_med)

    def state_value(rev_annual, co_invest):
        cf = rev_annual * margin * (1 - p.tax_marg)          # after-tax cash flow $M/yr
        v = cf / p.wacc                                       # flat perpetuity (ISS ran 25+ yrs)
        return max(v - co_invest, 0.0)                        # exercise only if worth the co-investment

    v_small, v_med, v_large = (state_value(rev_small, inv_small),
                               state_value(rev_med, inv_med),
                               state_value(rev_large, inv_large))
    disc_tau = (1 + p.wacc) ** (-tau)
    # states are nested upgrades: large supersedes medium supersedes small
    payoff = np.where(large, v_large, np.where(medium, v_med, np.where(small, v_small, 0.0))) * disc_tau
    return {"tau": tau, "margin": margin,
            "v_small": v_small, "v_med": v_med, "v_large": v_large,
            "p_states": {"small": float(small.mean()), "medium": float(medium.mean()),
                         "large": float(large.mean())},
            "option_value": float(payoff.mean()),
            "option_se": float(payoff.std(ddof=1) / np.sqrt(n))}


def main():
    p = FirmParams()

    # Deterministic check (vol = 0): should reproduce a Damodaran-style point value (sans Expansion).
    det = simulate(p, n=1, seed=1, stochastic=False)
    sto = simulate(p, n=200_000, seed=2026, stochastic=True)

    print("=" * 78)
    print("SpaceX base-case valuation (3 operating segments, no options yet)")
    print("=" * 78)
    print("Calibration: Damodaran June 2026 segment targets. Excludes the 'Expansion' line")
    print("(that becomes the expansion REAL OPTION in stage 2), so this sits below his ~$1.3T.")
    print("-" * 78)
    print("Deterministic (vol=0) segment operating values ($M):")
    for k, v in det["seg_values"].items():
        print(f"    {k:<10} ${v:>14,.0f}")
    print(f"  deterministic equity value : ${det['equity_mean']:>16,.0f} M  "
          f"(${det['per_share_mean']:.2f}/share)")
    print("-" * 78)
    print("Stochastic Monte Carlo (correlated segments):")
    print(f"  mean equity value          : ${sto['equity_mean']:>16,.0f} M  "
          f"(s.e. +/- ${sto['equity_se']:,.0f}M)")
    print(f"  mean per share             : ${sto['per_share_mean']:>16.2f}")
    eq = sto["equity"]
    print(f"  equity distribution: 5th ${np.quantile(eq,0.05)/1e6:.2f}T, "
          f"median ${np.quantile(eq,0.5)/1e6:.2f}T, 95th ${np.quantile(eq,0.95)/1e6:.2f}T")
    print(f"  P(equity < $1.0T) = {np.mean(eq < 1e6)*100:.1f}%   "
          f"P(equity > $1.8T IPO) = {np.mean(eq > 1.8e6)*100:.1f}%")
    print("-" * 78)

    # ---- Expansion option #1: Starlink direct-to-cell ----
    invest = 12000.0   # ~$12B irreversible next-gen / DTC constellation investment (SpaceX capex scale)
    dtc = dtc_expansion_option(p, sto["core_factor"], invest)
    firm_with = sto["equity_mean"] + dtc["option_value"]
    print("Expansion option #1 -- Starlink direct-to-cell (invest in next-gen constellation):")
    print(f"  E[DTC business value if pursued]   : ${dtc['E_VDTC']:>12,.0f} M")
    print(f"  irreversible investment I          : ${dtc['invest']:>12,.0f} M  at year {dtc['tau']}")
    print(f"  P(optimal to invest)               : {dtc['prob_invest']*100:>12.1f} %")
    print(f"  EXPANSION OPTION VALUE             : ${dtc['option_value']:>12,.0f} M  "
          f"(s.e. +/- ${dtc['option_se']:,.0f}M)")
    print(f"    vs passive 'always invest'       : ${dtc['passive_value']:>12,.0f} M  "
          f"(option avoids ${dtc['option_value']-dtc['passive_value']:,.0f}M of downside)")
    print("-" * 78)

    # ---- Expansion option #2: Starship heavy-lift markets (grounded; Mars = $0 base case) ----
    ss = starship_expansion_option(p, sto["core_factor"])
    print("Expansion option #2 -- Starship heavy-lift markets (grounded; NOT Mars):")
    print(f"  gross value of unlocked markets V  : ${ss['V_central']:>12,.0f} M (central; launch-addressable)")
    print(f"  irreversible investment I          : ${ss['invest']:>12,.0f} M")
    print(f"  P(reusability trigger fires)       : {ss['p_tech']*100:>12.0f} %  (NOT yet demonstrated)")
    print(f"  P(exercise: trigger AND V>I)       : {ss['prob_exercise']*100:>12.1f} %")
    print(f"  STARSHIP OPTION VALUE              : ${ss['option_value']:>12,.0f} M  "
          f"(s.e. +/- ${ss['option_se']:,.0f}M)")
    print("-" * 78)

    # ---- Expansion option #3: Mars as a sovereign-program contractor option (grounded) ----
    mars = mars_sovereign_option(p, ss["tech_success"])
    print("Expansion option #3 -- Mars sovereign-program contractor revenue (grounded):")
    print(f"  state values (perpetuity - co-invest): small ${mars['v_small']:,.0f}M | "
          f"medium ${mars['v_med']:,.0f}M | large ${mars['v_large']:,.0f}M")
    print(f"  state probabilities                : small {mars['p_states']['small']:.0%} | "
          f"medium {mars['p_states']['medium']:.1%} | large {mars['p_states']['large']:.1%}")
    print(f"  MARS OPTION VALUE                  : ${mars['option_value']:>12,.0f} M  "
          f"(s.e. +/- ${mars['option_se']:,.0f}M)")
    print(f"  (Mars commodity-export business    : $0 -- no defensible revenue model; the option's")
    print(f"   underlying is sovereign-program contractor revenue, ISS/Artemis/Antarctica analogs)")
    print("-" * 78)

    total = sto["equity_mean"] + dtc["option_value"] + ss["option_value"] + mars["option_value"]
    print(f"SpaceX value, base + expansion options : ${total:>12,.0f} M")
    print(f"  = base ${sto['equity_mean']:,.0f}M + DTC ${dtc['option_value']:,.0f}M "
          f"+ Starship ${ss['option_value']:,.0f}M + Mars ${mars['option_value']:,.0f}M")
    print(f"  (xAI abandonment + competition layer still to integrate)")
    print("=" * 78)
    print("Reference: Damodaran ~$1.3T (incl. Expansion), ARK ~$2.5T (2030), IPO ~$1.8T.")

    out = Path(__file__).resolve().parents[2] / "output" / "tables"
    out.mkdir(parents=True, exist_ok=True)
    payload = {"params": asdict(p), "deterministic": det["seg_values"],
               "deterministic_equity": det["equity_mean"],
               "stochastic": {k: sto[k] for k in
                              ["equity_mean", "equity_se", "per_share_mean", "seg_values", "n"]}}
    (out / "spacex_base_valuation.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"Results written to: {out / 'spacex_base_valuation.json'}")


if __name__ == "__main__":
    main()
