"""
03_decomposition.py  --  integrate the pieces: xAI scenarios, salvage & competition sensitivities,
the sum-of-parts comparison, and the decomposition waterfall figure.

Produces, in one run:
  1. xAI segment value under comp-disciplined margin scenarios (sources in paper Section 4):
     "AI infrastructure" 16.5% / Damodaran-boundary 25% / "winning model" 30% terminal margin --
     plus the failure-aware venture-model floor (~$22B, from venture_option.py) as the honest lower
     bound. The xAI spread IS the live disagreement (Message 4/7).
  2. Salvage sensitivity for the xAI abandonment option (Hughes: failed-AI assets redeploy to
     Starlink -> salvage > 0 raises the option value; our salvage=0 was the conservative floor).
  3. Competition haircuts (reduced-form, Grenadier/Smit-Trigeorgis logic): contested segments'
     option UNDERLYINGS eroded (DTC, Starship); Mars proprietary (no haircut). Note: our expansion
     options are already modeled as exercise-at-gate (European), consistent with preemption
     equilibria in which waiting premia are competed away -- the haircut sensitivity covers the
     value-erosion channel.
  4. Sum-of-parts: market-implied premium (IPO price minus core) vs our grounded components.
  5. The waterfall decomposition figure with the landscape reference lines.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from spacex_realoptions import (FirmParams, simulate, dtc_business_value, dtc_expansion_option,
                                starship_expansion_option, mars_sovereign_option)
from venture_option import VentureParams, simulate_paths, value_with_option

ROOT = Path(__file__).resolve().parents[2]
IPO = 1_767_285.0             # exact offer capitalization: $135/share x 13,091M shares


def xai_scenarios(p):
    out = {}
    for label, m in [("infrastructure (16.5%)", 0.165), ("Damodaran-boundary (25%)", 0.25),
                     ("winning model (30%)", 0.30)]:
        q = copy.deepcopy(p)
        for s in q.segments:
            if s.name == "xAI":
                s.margin_target = m
        out[label] = simulate(q, n=1, seed=1, stochastic=False)["seg_values"]["xAI"]
    return out


def abandonment_distribution_figure():
    """Distribution of xAI venture outcomes with vs without the abandonment option (salvage 0).
    The option's effect is in the LEFT TAIL: it truncates the worst outcomes."""
    vp = VentureParams()
    n = 100_000
    R, mu, fcf, tv = simulate_paths(vp, n, seed=2026)
    disc = (1 + vp.r) ** (-np.arange(1, vp.T + 1))
    vfull = (fcf * disc[None, :]).sum(axis=1) + tv * disc[-1]
    pathv, _, _ = value_with_option(vp, R, mu, fcf, tv)

    plt.rcParams.update({"font.size": 10.5, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.alpha": 0.25, "figure.dpi": 120,
                         "legend.frameon": False, "savefig.bbox": "tight"})
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    bins = np.linspace(-30, 80, 110)
    ax.hist(np.clip(vfull / 1000, -30, 80), bins=bins, density=True, alpha=0.45,
            color="C3", label="without abandonment option")
    ax.hist(np.clip(pathv / 1000, -30, 80), bins=bins, density=True, alpha=0.45,
            color="C0", label="with abandonment option")
    for v, c, lab in [(np.quantile(vfull, 0.05) / 1000, "C3", "5th pct, without"),
                      (np.quantile(pathv, 0.05) / 1000, "C0", "5th pct, with")]:
        ax.axvline(v, color=c, ls="--", lw=1.2)
        ax.text(v, ax.get_ylim()[1] * 0.92, f" {lab}: {v:,.0f}", color=c, fontsize=8.5,
                rotation=90, va="top")
    ax.set_xlabel("Present value of the xAI venture (\\$B)")
    ax.set_ylabel("Density")
    ax.set_title("xAI venture outcomes with and without the abandonment option")
    figs = ROOT / "paper" / "draft" / "output" / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    fig.savefig(figs / "fig_abandonment_distribution.pdf")
    fig.savefig(figs / "fig_abandonment_distribution.png")
    print("Figure written:", figs / "fig_abandonment_distribution.pdf")


def beta_back_of_envelope(firm_total=1_069_000.0):
    """Back-of-the-envelope: how much does the abandonment option lower the required return?

    Logic: the bundle (venture + abandonment put) has beta_bundle = (dBundle/dV)(V/Bundle) beta_V
    with dBundle/dV = 1 + dP/dV. The put's delta dP/dV is estimated by finite differences,
    revaluing the option after scaling the venture's revenue level by +/-10%. Assuming the
    venture's entire risk premium (12% rate minus 4.56% risk-free) is priced covariance, the
    bundle's premium scales with the beta ratio. Firm-level effect weights by value share.
    Partial-equilibrium and local; reported as an order of magnitude, not an estimate."""
    out = {}
    base = {}
    for tag, scale in [("lo", 0.9), ("base", 1.0), ("hi", 1.1)]:
        vp = VentureParams(R0=3200.0 * scale)
        n = 100_000
        R, mu, fcf, tv = simulate_paths(vp, n, seed=2026)
        disc = (1 + vp.r) ** (-np.arange(1, vp.T + 1))
        v_without = float(((fcf * disc[None, :]).sum(axis=1) + tv * disc[-1]).mean())
        pathv, _, _ = value_with_option(vp, R, mu, fcf, tv)
        base[tag] = {"V": v_without, "P": float(pathv.mean()) - v_without}
    dPdV = (base["hi"]["P"] - base["lo"]["P"]) / (base["hi"]["V"] - base["lo"]["V"])
    V, P = base["base"]["V"], base["base"]["P"]
    beta_ratio = (1 + dPdV) * V / (V + P)
    rf, r_v = 0.0456, 0.12
    prem = r_v - rf
    dr_venture = prem * (1 - beta_ratio)               # required-return reduction on the bundle
    w = (V + P) / firm_total
    dr_firm_bp = dr_venture * w * 1e4                  # firm-level, basis points
    out = {"dPdV": dPdV, "V_venture": V, "P_option": P, "beta_ratio": beta_ratio,
           "dr_venture_pp": dr_venture * 100, "venture_weight": w, "dr_firm_bp": dr_firm_bp}
    print("\nBack-of-envelope, abandonment option and the required return:")
    print(f"  put delta dP/dV = {dPdV:.3f}; beta ratio bundle/venture = {beta_ratio:.2f}")
    print(f"  venture required return falls by ~{dr_venture*100:.1f}pp "
          f"(from 12.0% toward {12 - dr_venture*100:.1f}%)")
    print(f"  firm-level effect at a {w:.1%} value weight: ~{dr_firm_bp:.0f} basis points")
    return out


def salvage_sensitivity():
    out = {}
    for sv in [0.0, 5000.0, 10000.0]:
        vp = VentureParams(salvage=sv)
        n = 100_000
        R, mu, fcf, tv = simulate_paths(vp, n, seed=2026)
        disc = (1 + vp.r) ** (-np.arange(1, vp.T + 1))
        v_without = float(((fcf * disc[None, :]).sum(axis=1) + tv * disc[-1]).mean())
        pathval, abandon_year, _ = value_with_option(vp, R, mu, fcf, tv)
        out[f"salvage ${sv/1000:.0f}B"] = {
            "value_with": float(pathval.mean()),
            "option_value": float(pathval.mean()) - v_without,
            "prob_abandon": float((abandon_year <= vp.T).mean()),
        }
    return out


def competition_sensitivity(p, core_factor, tech):
    """Erode contested option underlyings by haircut h; Mars (proprietary) unaffected."""
    out = {}
    E_dtc = dtc_business_value(p)
    for h in [0.0, 0.15, 0.30]:
        dtc = dtc_expansion_option(p, core_factor, invest=12000.0, E_V_override=E_dtc * (1 - h))
        ss = starship_expansion_option(p, core_factor, V_central=110000.0 * (1 - h),
                                       tech_success=tech)
        mars = mars_sovereign_option(p, tech)     # proprietary: no haircut
        out[f"haircut {h:.0%}"] = {
            "DTC": dtc["option_value"], "Starship": ss["option_value"],
            "Mars": mars["option_value"],
            "total_options": dtc["option_value"] + ss["option_value"] + mars["option_value"],
        }
    return out


def main():
    p = FirmParams()
    det = simulate(p, n=1, seed=1, stochastic=False)
    sto = simulate(p, n=200_000, seed=2026, stochastic=True)
    seg = det["seg_values"]
    net_cash = p.cash + p.ipo_proceeds - p.debt

    # options at base
    ss = starship_expansion_option(p, sto["core_factor"])
    dtc = dtc_expansion_option(p, sto["core_factor"], invest=12000.0)
    mars = mars_sovereign_option(p, ss["tech_success"])
    opt_total = dtc["option_value"] + ss["option_value"] + mars["option_value"]

    # Standalone closed-form validation of the exercise-at-gate claims (Appendix A): the gate
    # payoff depends only on the marginal lognormal distribution of V, and the technical trigger
    # is drawn independently of V, so each expansion claim has a Black-Scholes-type closed form,
    # p * [M Phi(d1) - I Phi(d2)] (1+r)^-tau. The simulated value must match within MC error.
    def gate_closed_form(M, I, sigma, tau, p_gate=1.0):
        from math import erf, log, sqrt
        Phi = lambda x: 0.5 * (1.0 + erf(x / sqrt(2.0)))
        d1 = (log(M / I) + 0.5 * sigma**2) / sigma
        return p_gate * (M * Phi(d1) - I * Phi(d1 - sigma)) * (1 + p.wacc) ** (-tau)

    closed = {"DTC": gate_closed_form(dtc["E_VDTC"], dtc["invest"], dtc["sigma"], dtc["tau"]),
              "Starship": gate_closed_form(ss["V_central"], ss["invest"], ss["sigma"], ss["tau"],
                                           p_gate=ss["p_tech"]),
              "DTC_se": dtc["option_se"], "Starship_se": ss["option_se"]}
    print("\nClosed-form validation of expansion claims ($M): "
          f"DTC {closed['DTC']:,.0f} vs sim {dtc['option_value']:,.0f} (se {dtc['option_se']:,.0f}); "
          f"Starship {closed['Starship']:,.0f} vs sim {ss['option_value']:,.0f} (se {ss['option_se']:,.0f})")

    xai = xai_scenarios(p)
    sal = salvage_sensitivity()
    comp = competition_sensitivity(p, sto["core_factor"], ss["tech_success"])

    print("=" * 88)
    print("1) xAI segment value under comp-disciplined margin scenarios ($M)")
    for k, v in xai.items():
        print(f"   {k:<28} ${v:>12,.0f}")
    print("   failure-aware venture floor   $      ~22,000  (venture_option.py, 28% abandon prob)")

    print("\n2) xAI abandonment option: salvage sensitivity (Hughes redeployment argument)")
    for k, v in sal.items():
        print(f"   {k:<16} option ${v['option_value']:>8,.0f}M   P(abandon) {v['prob_abandon']:.0%}")

    print("\n3) Competition haircuts on contested option underlyings (Mars proprietary)")
    for k, v in comp.items():
        print(f"   {k:<14} DTC ${v['DTC']:>8,.0f}M  Starship ${v['Starship']:>8,.0f}M  "
              f"Mars ${v['Mars']:>6,.0f}M  total ${v['total_options']:>8,.0f}M")

    # 4) sum-of-parts. The abandonment option is added explicitly to the segment-DCF (upper) end;
    # at the lower end the venture-floor xAI value ALREADY embeds optimal abandonment, so adding it
    # again would double count.
    abandon = sal["salvage $0B"]["option_value"]
    # venture floor wired to the venture model's value-with-option (m12: no hand-typed 22,000)
    vp0 = VentureParams()
    Rv0, muv0, fcfv0, tvv0 = simulate_paths(vp0, 100_000, seed=2026)
    discv0 = (1 + vp0.r) ** (-np.arange(1, vp0.T + 1))
    pathv0, _, _ = value_with_option(vp0, Rv0, muv0, fcfv0, tvv0)
    venture_floor = float(pathv0.mean())
    core = seg["Launch"] + seg["Starlink"]
    print("\n4) Sum-of-parts vs the market-implied premium ($B)")
    print(f"   our core (Launch+Starlink)     {core/1000:>8,.0f}   "
          f"[Morningstar 611, PitchBook ~1,000]")
    print(f"   + xAI scenarios                {min(xai.values())/1000:>8,.0f} - {max(xai.values())/1000:,.0f}   "
          f"[venture floor ~22]")
    print(f"   + net cash (incl. IPO)         {net_cash/1000:>8,.0f}")
    print(f"   + expansion options            {opt_total/1000:>8,.0f}")
    print(f"   + xAI abandonment option       {abandon/1000:>8,.1f}   (embedded in the venture floor at the low end)")
    lo = core + venture_floor + net_cash + opt_total
    hi = core + max(xai.values()) + net_cash + opt_total + abandon
    print(f"   = benchmark total              {lo/1000:>8,.0f} - {hi/1000:,.0f}")
    print(f"   IPO price                      {IPO/1000:>8,.0f}")
    print(f"   unexplained premium            {(IPO-hi)/1000:>8,.0f} - {(IPO-lo)/1000:,.0f}")

    # 5) waterfall figure
    plt.rcParams.update({"font.size": 10.5, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.alpha": 0.25, "figure.dpi": 120,
                         "legend.frameon": False, "savefig.bbox": "tight"})
    fig, ax = plt.subplots(figsize=(9.2, 5.4))
    labels = ["Launch", "Starlink", "xAI\n(scenarios)", "Net\ncash",
              "Real\noptions", "Total"]
    vals = [seg["Launch"], seg["Starlink"], xai["Damodaran-boundary (25%)"], net_cash,
            opt_total + abandon]
    cum = np.concatenate([[0], np.cumsum(vals)])
    total_base = cum[-1]
    for i, v in enumerate(vals):
        ax.bar(i, v / 1e6, bottom=cum[i] / 1e6, width=0.62,
               color="C0" if i < 3 else ("0.6" if i == 3 else "C2"))
    ax.bar(len(vals), total_base / 1e6, width=0.62, color="0.3")
    # xAI scenario whiskers on its bar
    x_lo = cum[2] + venture_floor   # the computed venture-model floor for xAI
    x_hi = cum[2] + max(xai.values())
    ax.plot([2, 2], [x_lo / 1e6, x_hi / 1e6], "k-", lw=1.6)
    ax.plot([1.85, 2.15], [x_lo / 1e6] * 2, "k-", lw=1.2)
    ax.plot([1.85, 2.15], [x_hi / 1e6] * 2, "k-", lw=1.2)
    # reference lines
    for y, lab, col in [(0.78, "Morningstar", "C3"), (1.30, "Damodaran", "C2"),
                        (1.77, "IPO $1.77T", "k"), (2.30, "Polymarket first-day", "C4")]:
        ax.axhline(y, ls="--", lw=0.9, color=col, alpha=0.6)
        ax.text(len(vals) + 0.45, y, lab, fontsize=8.5, color=col, va="bottom", ha="left")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Equity value (\\$T)")
    ax.set_title("Benchmark value decomposition (whisker: xAI scenario range)")
    ax.set_xlim(-0.6, len(vals) + 2.2)
    figs = ROOT / "paper" / "draft" / "output" / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    fig.savefig(figs / "fig_decomposition_waterfall.pdf")
    fig.savefig(figs / "fig_decomposition_waterfall.png")
    print("\nFigure written:", figs / "fig_decomposition_waterfall.pdf")

    abandonment_distribution_figure()
    bote = beta_back_of_envelope(firm_total=sto["equity_mean"] + opt_total + abandon)

    payload = {"segments": seg, "net_cash": net_cash, "bote": bote,
               "venture_floor": venture_floor, "options":
               {"DTC": dtc["option_value"], "Starship": ss["option_value"],
                "Mars": mars["option_value"], "Abandonment": abandon},
               # the claim parameters as actually used, so the paper can quote them via macros
               # (single source of truth: the defaults in spacex_realoptions.py)
               "option_params": {
                   "DTC": {k: dtc[k] for k in ("E_VDTC", "invest", "tau", "sigma", "rho")},
                   "Starship": {k: ss[k] for k in ("V_central", "invest", "p_tech", "tau", "sigma")}},
               "options_closed_form": closed,
               "xai_scenarios": xai, "salvage_sensitivity": sal,
               "competition_sensitivity": comp,
               "grounded_total_range": [lo, hi], "ipo": IPO}
    (ROOT / "output" / "tables" / "decomposition.json").write_text(json.dumps(payload, indent=2))
    print("Results written:", ROOT / "output" / "tables" / "decomposition.json")


if __name__ == "__main__":
    main()
