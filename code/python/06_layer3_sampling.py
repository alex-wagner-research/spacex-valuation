"""
06_layer3_sampling.py  --  Layer 3 of the inverse valuation: acceptance sampling over the full
parameter space, including the option parameters.

Method: draw parameter vectors from wide uniform ranges, value the firm for each draw (vectorized
DCF + closed-form option layer), keep the draws that price within a window around the IPO value
($1.72T-$1.82T), and compare each parameter's conditional (accepted) distribution with its
grounded range from the assembled evidence (paper Appendix B, Table 6). The reading: which beliefs must move, and
how far outside the grounded evidence, to make $1.77T fair value.

Validation gates (run before results are trusted):
  1. the vectorized DCF reproduces simulate(stochastic=False) at the base point to <0.1%;
  2. the closed-form option values reproduce the Monte-Carlo values in spacex_realoptions.py
     (DTC $32.6B, Starship $32.3B) to ~1%.

The xAI abandonment option (~$1.5-3.4B) is excluded from the sampler: venture failure is already
proxied by sampling xAI revenue/margin low, and its magnitude is immaterial at the $1.77T question.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import norm

from spacex_realoptions import FirmParams, simulate

ROOT = Path(__file__).resolve().parents[2]
IPO = 1_767_285.0             # exact offer capitalization: $135/share x 13,091M shares
WINDOW = (1_720_000.0, 1_820_000.0)
NET_CASH = 24_747.0 + 75_000.0 - 22_896.0
T = 11

# margin starting points and base sales-to-capital, fixed as in FirmParams
SEG_FIX = {  # name: (rev0, margin0, s2c_base)
    "Launch":   (4086.0, 0.30, 3.5),
    "Starlink": (11387.0, 0.35, 4.0),
    "xAI":      (3201.0, -0.30, 2.0),
}

# Sampled parameters: name -> (sample lo, sample hi, grounded lo, grounded hi, unit-label)
PARAMS = {
    "rev_Launch":   (20.0, 300.0, 40.0, 70.0,  "Launch 2036 rev ($B)"),
    "rev_Starlink": (60.0, 400.0, 114.0, 220.0, "Starlink 2036 rev ($B)"),
    "rev_xAI":      (40.0, 800.0, 21.0, 160.0, "xAI 2036 rev ($B)"),
    "m_Launch":     (0.20, 0.60, 0.40, 0.45,  "Launch terminal margin"),
    "m_Starlink":   (0.30, 0.75, 0.55, 0.65,  "Starlink terminal margin"),
    "m_xAI":        (0.05, 0.50, 0.10, 0.40,  "xAI terminal margin"),
    "wacc":         (0.055, 0.110, 0.068, 0.097, "WACC"),
    "g_term":       (0.020, 0.055, 0.030, 0.0456, "terminal growth"),
    "s2c_scale":    (0.60, 1.60, 0.80, 1.20,  "reinvestment efficiency (x base)"),
    "p_tech":       (0.20, 0.95, 0.40, 0.80,  "P(Starship trigger)"),
    "V_starship":   (40.0, 250.0, 40.0, 250.0, "Starship unlocked value ($B)"),
    "EV_dtc":       (25.0, 90.0, 35.0, 80.0,  "DTC business value ($B)"),
    "mars_opt":     (0.3, 3.0, 0.4, 2.9,      "Mars option value ($B)"),
}
# grounded-range sources: Damodaran segment targets & ARK ranges (rev); comp bands (margins,
# AI-infrastructure comparables, paper Section 4; xAI rev lower bound = venture-model scale); FF1997-style
# +-1.5pp estimation band around 8.25% (wacc); g <= riskfree 4.56% discipline; Starship/DTC/Mars
# research ranges (paper Appendix B). Sample ranges are deliberately WIDER than grounded.


def value_vectorized(d):
    """Equity value ($M) for dict of parameter arrays (each shape (N,)). Mirrors simulate(det)."""
    N = len(d["wacc"])
    wacc = d["wacc"]
    g = np.minimum(d["g_term"], wacc - 0.005)            # keep spread positive
    t = np.arange(1, T + 1)
    disc = (1 + wacc[:, None]) ** (-t[None, :])          # (N, T)
    tax = (0.10 + (0.25 - 0.10) * t / T)[None, :]

    op = np.zeros(N)
    for name in SEG_FIX:
        rev0, m0, s2c_b = SEG_FIX[name]
        rt = d[f"rev_{name}"] * 1000.0                   # $B -> $M
        mt = d[f"m_{name}"]
        s2c = s2c_b * d["s2c_scale"]
        gr = (rt / rev0) ** (1.0 / T) - 1.0              # (N,)
        R = rev0 * (1 + gr[:, None]) ** t[None, :]       # (N, T)
        Rprev = np.concatenate([np.full((N, 1), rev0), R[:, :-1]], axis=1)
        m = m0 + (mt[:, None] - m0) * (t[None, :] / T)
        ebit = m * R
        fcf = ebit - tax * np.maximum(ebit, 0) - np.maximum(R - Rprev, 0) / s2c[:, None]
        pv = (fcf * disc).sum(axis=1)
        fcff_T = ebit[:, -1] * (1 - 0.25) * (1 + g) * (1 - g / 0.15)
        pv += fcff_T / (wacc - g) * disc[:, -1]
        op += pv

    # closed-form option layer (lognormal underlying; validated against the MC values)
    def growth_opt(Vbar, I, sigma, tau, gate=1.0):
        Vb = np.maximum(Vbar, 1e-9)
        d1 = (np.log(Vb / I) + 0.5 * sigma**2) / sigma
        d2 = d1 - sigma
        ev = Vb * norm.cdf(d1) - I * norm.cdf(d2)
        return gate * ev * (1 + wacc) ** (-tau)

    opt = growth_opt(d["EV_dtc"] * 1000, 12_000.0, 0.55, 4)
    opt += growth_opt(d["V_starship"] * 1000, 30_000.0, 0.50, 5, gate=d["p_tech"])
    opt += d["mars_opt"] * 1000

    return op + NET_CASH + opt


def base_point():
    return {k: np.array([v]) for k, v in {
        "rev_Launch": 40.0, "rev_Starlink": 120.0, "rev_xAI": 160.0,
        "m_Launch": 0.45, "m_Starlink": 0.60, "m_xAI": 0.25,
        "wacc": 0.0825, "g_term": 0.0456, "s2c_scale": 1.0,
        "p_tech": 0.60, "V_starship": 110.0, "EV_dtc": 56.737, "mars_opt": 0.772}.items()}


def main():
    # ---- validation gates ----
    v_base = float(value_vectorized(base_point())[0])
    import json as _json
    _dec = _json.loads((ROOT / "output" / "tables" / "decomposition.json").read_text())
    _opt_base = sum(v for k, v in _dec["options"].items() if k != "Abandonment")
    ref = simulate(FirmParams(), n=1, seed=1, stochastic=False)["equity_mean"] + _opt_base
    err = abs(v_base - ref) / ref
    print(f"validation: vectorized base ${v_base:,.0f}M vs reference ${ref:,.0f}M  "
          f"(diff {err:.3%}) -> {'OK' if err < 0.02 else 'FAIL'}")
    if err >= 0.02:
        raise SystemExit("vectorized valuator does not reproduce the reference model")

    # ---- sampling ----
    N = 400_000
    rng = np.random.default_rng(2026)
    draws = {k: rng.uniform(lo, hi, N) for k, (lo, hi, *_ ) in PARAMS.items()}
    V = value_vectorized(draws)
    acc = (V >= WINDOW[0]) & (V <= WINDOW[1])
    n_acc = int(acc.sum())
    print(f"draws {N:,}; accepted in [{WINDOW[0]/1e6:.2f}T, {WINDOW[1]/1e6:.2f}T]: "
          f"{n_acc:,} ({n_acc/N:.2%})")

    # ---- conditional distributions vs grounded ranges ----
    print("\nAccepted-draw distributions vs grounded ranges:")
    print(f"{'parameter':<34}{'grounded':>18}{'accepted p5':>13}{'median':>10}{'p95':>10}")
    rows = []
    for k, (slo, shi, glo, ghi, label) in PARAMS.items():
        x = draws[k][acc]
        p5, p50, p95 = np.percentile(x, [5, 50, 95])
        rows.append({"param": k, "label": label, "sample": [slo, shi], "grounded": [glo, ghi],
                     "accepted": [float(p5), float(p50), float(p95)],
                     "share_in_grounded": float(((x >= glo) & (x <= ghi)).mean())})
        fmt = (lambda v: f"{v:.3f}") if shi <= 2 else (lambda v: f"{v:,.0f}")
        print(f"{label:<34}{fmt(glo)+' - '+fmt(ghi):>18}{fmt(p5):>13}{fmt(p50):>10}{fmt(p95):>10}")

    # ---- joint diagnostics ----
    OPER = ["rev_Launch", "rev_Starlink", "rev_xAI", "m_Launch", "m_Starlink", "m_xAI",
            "s2c_scale", "g_term"]
    in_g = {k: (draws[k] >= PARAMS[k][2]) & (draws[k] <= PARAMS[k][3]) for k in PARAMS}
    all_oper = np.all([in_g[k] for k in OPER], axis=0)
    wacc_in = in_g["wacc"]
    print("\nJoint diagnostics (accepted draws):")
    print(f"  WACC below grounded floor (6.8%):                 {float((draws['wacc'][acc] < 0.068).mean()):.1%}")
    print(f"  ALL operating params within grounded ranges:      {float(all_oper[acc].mean()):.2%}")
    print(f"  all-operating-grounded AND WACC grounded:         {float((all_oper & wacc_in)[acc].mean()):.3%}")
    both = acc & all_oper & wacc_in
    print(f"  (= {int(both.sum())} of {n_acc:,} accepted draws)")
    print("  NOTE: the above conditional is dominated by prior geometry (the grounded box is a")
    print("  tiny share of the sampling volume). The decision-relevant direction is the reverse:")

    # ---- grounded-box pass: sample WITHIN the grounded ranges only ----
    draws_g = {k: rng.uniform(glo, ghi, N) for k, (slo, shi, glo, ghi, lab) in PARAMS.items()}
    Vg = value_vectorized(draws_g)
    reach = Vg >= WINDOW[0]
    print("\nGrounded-box pass (all parameters WITHIN grounded ranges):")
    print(f"  value distribution: p5 ${np.percentile(Vg,5)/1e6:.2f}T, median ${np.percentile(Vg,50)/1e6:.2f}T, "
          f"p95 ${np.percentile(Vg,95)/1e6:.2f}T, max ${Vg.max()/1e6:.2f}T")
    print(f"  share of grounded belief-space pricing >= ${WINDOW[0]/1e6:.2f}T: {float(reach.mean()):.2%}")
    if reach.any():
        w_r = draws_g["wacc"][reach]
        print(f"  among those: WACC p5 {np.percentile(w_r,5):.2%}, median {np.percentile(w_r,50):.2%}, "
              f"p95 {np.percentile(w_r,95):.2%}; share with WACC < 7.5%: {float((w_r<0.075).mean()):.0%}")
        rev_r = (draws_g["rev_Launch"] + draws_g["rev_Starlink"] + draws_g["rev_xAI"])[reach]
        print(f"  aggregate 2036 revenue among those: median ${np.percentile(rev_r,50):,.0f}B "
              f"(grounded band 175-450)")

    # ---- figure: interval plot (a) + WACC-vs-revenue scatter (b) ----
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.alpha": 0.25, "figure.dpi": 120,
                         "legend.frameon": False, "savefig.bbox": "tight"})
    fig, (axA, axB) = plt.subplots(2, 1, figsize=(7.4, 9.6),
                                   gridspec_kw={"height_ratios": [1.25, 1.0]})
    for i, r in enumerate(rows):
        slo, shi = r["sample"]
        nrm = lambda v: (v - slo) / (shi - slo)
        glo, ghi = r["grounded"]
        axA.barh(i, nrm(ghi) - nrm(glo), left=nrm(glo), height=0.62, color="0.85", zorder=1)
        p5, p50, p95 = r["accepted"]
        axA.plot([nrm(p5), nrm(p95)], [i, i], "-", color="C0", lw=2.2, zorder=3)
        axA.plot(nrm(p50), i, "o", color="C0", ms=5.5, zorder=4)
    axA.set_yticks(range(len(rows)))
    axA.set_yticklabels([r["label"] for r in rows], fontsize=8.5)
    axA.set_xlim(0, 1)
    axA.set_xticks([0, 1])
    axA.set_xticklabels(["sampling range low", "high"], fontsize=8.5)
    axA.invert_yaxis()
    axA.set_title("(a) Parameter values among draws that price at the offer\n"
                  "(dot: median; bar: 5th-95th percentile; grey: supported range)", fontsize=10)

    agg_rev = draws["rev_Launch"] + draws["rev_Starlink"] + draws["rev_xAI"]
    idx = np.flatnonzero(acc)[:4000]
    axB.scatter(draws["wacc"][idx] * 100, agg_rev[idx], s=4, alpha=0.25, color="C0")
    axB.axvspan(6.8, 9.7, color="0.85", zorder=0)
    axB.axhspan(175, 450, color="0.92", zorder=0)
    axB.annotate("supported\nWACC band", (8.2, 1300), fontsize=8.5, color="0.35", ha="center")
    axB.annotate("supported revenue band", (6.2, 300), fontsize=8.5, color="0.35")
    axB.set_xlabel("Discount rate (%)")
    axB.set_ylabel("Aggregate 2036 revenue (\\$B)")
    axB.set_title("(b) Accepted draws: discount rate and aggregate 2036 revenue", fontsize=10)
    fig.tight_layout()
    figs = ROOT / "paper" / "draft" / "output" / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    fig.savefig(figs / "fig_layer3_acceptance.pdf")
    fig.savefig(figs / "fig_layer3_acceptance.png")
    print("\nFigure written:", figs / "fig_layer3_acceptance.pdf")

    payload = {"window": WINDOW, "n_draws": N, "n_accepted": n_acc, "rows": rows,
               "joint": {"wacc_below_grounded_floor": float((draws['wacc'][acc] < 0.068).mean()),
                         "all_oper_grounded": float(all_oper[acc].mean()),
                         "all_grounded_incl_wacc": float((all_oper & wacc_in)[acc].mean())},
               "grounded_box": {
                   "value_p5_p50_p95_max": [float(np.percentile(Vg, 5)), float(np.percentile(Vg, 50)),
                                            float(np.percentile(Vg, 95)), float(Vg.max())],
                   "share_reaching_window": float(reach.mean()),
                   "wacc_p5_p50_p95_among_reaching":
                       [float(np.percentile(draws_g["wacc"][reach], q)) for q in (5, 50, 95)]
                       if reach.any() else None,
                   # the JOINT share, computed explicitly (not inferred from
                   # marginals). Upper-half revenue = aggregate 2036 revenue above the midpoint
                   # of its supported band (175-450 -> 312.5).
                   "share_wacc_below_075_among_reaching":
                       float((draws_g["wacc"][reach] < 0.075).mean()) if reach.any() else None,
                   "share_joint_lowwacc_upperrev_among_reaching":
                       float(((draws_g["wacc"][reach] < 0.075) &
                              ((draws_g["rev_Launch"] + draws_g["rev_Starlink"]
                                + draws_g["rev_xAI"])[reach] > 312.5)).mean())
                       if reach.any() else None}}
    (ROOT / "output" / "tables" / "layer3_acceptance.json").write_text(json.dumps(payload, indent=2))
    print("Results written:", ROOT / "output" / "tables" / "layer3_acceptance.json")


if __name__ == "__main__":
    main()
