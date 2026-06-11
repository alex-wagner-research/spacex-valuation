"""
04_inverse_valuation.py  --  "What $1.77T requires you to believe" (reverse valuation).

Instead of defending our value, characterize the SET of parameter beliefs consistent with the IPO
price (expectations-investing logic, Mauboussin-Rappaport; Damodaran's implied-expectations
exercises). The feasible set {theta : V(theta) = $1.77T} is a high-dimensional surface; we flatten
it three honest ways:

  Layer 1 (implied-value table): one parameter at a time, holding all else at base, solve for the
          value that alone delivers the IPO price. Some parameters have NO feasible value -- that is
          itself the finding.
  Layer 2 (two figures): (a) the sufficient-statistic projection -- iso-price curves in (aggregate
          2036 revenue, blended terminal margin) space, the two composites through which the
          dominant terminal value actually depends on the many primitives; (b) the decision-relevant
          slice -- the (xAI 2036 revenue, xAI terminal margin) pairs that rationalize the price,
          against the comp-disciplined margin bands (AI-infrastructure 10-25%, winning-model 25-40%;
          sources in paper Section 4).
  Layer 3 (acceptance sampling over the full space incl. option parameters): 06_layer3_sampling.py.

Approximations, stated: the DCF is evaluated deterministically (vol=0; the stochastic mean differs
by ~0.1%), and the real-option layer is held at its base value of ~$66B (DTC + Starship + Mars).
Strictly the option values shift with the DCF parameters; given the options are ~6% of base value
and the gap to be explained is ~$700B, this is second-order for the inverse question. The paper
states both approximations.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from spacex_realoptions import FirmParams, simulate

ROOT = Path(__file__).resolve().parents[2]

TARGET = 1_767_285.0          # the exact offer capitalization, $M: $135/share x 13,091M shares
# Option layer held constant, wired to the decomposition results (no hand-typed constants):
import json as _json
_dec = _json.loads((ROOT / "output" / "tables" / "decomposition.json").read_text())
OPTIONS_BASE = sum(v for k, v in _dec["options"].items() if k != "Abandonment")


def clone(p: FirmParams, **kw) -> FirmParams:
    q = copy.deepcopy(p)
    for k, v in kw.items():
        setattr(q, k, v)
    return q


def det_value(p: FirmParams) -> float:
    """Deterministic (vol=0) equity value + base option layer, $M."""
    return simulate(p, n=1, seed=1, stochastic=False)["equity_mean"] + OPTIONS_BASE


def solve_scalar(make_params, lo, hi, target=TARGET, tol=500.0, maxit=80):
    """Bisection for lambda with V(make_params(lambda)) = target. Returns None if not bracketed."""
    f_lo, f_hi = det_value(make_params(lo)) - target, det_value(make_params(hi)) - target
    if f_lo * f_hi > 0:
        return None
    for _ in range(maxit):
        mid = 0.5 * (lo + hi)
        f_mid = det_value(make_params(mid)) - target
        if abs(f_mid) < tol:
            return mid
        if f_lo * f_mid <= 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return mid


def set_seg(p, name, field, value):
    q = copy.deepcopy(p)
    for s in q.segments:
        if s.name == name:
            setattr(s, field, value)
    return q


def implied_table(p: FirmParams):
    """Layer 1: one-at-a-time implied values."""
    base_v = det_value(p)
    rows = []

    def add(label, base_val, solver, fmt, feasible_cap=None):
        lam = solver()
        feas = lam is not None and (feasible_cap is None or lam <= feasible_cap)
        rows.append({"parameter": label, "base": base_val,
                     "implied": lam, "feasible": feas, "fmt": fmt})

    add("Starlink 2036 revenue ($B)", 120.0,
        lambda: solve_scalar(lambda x: set_seg(p, "Starlink", "rev_target", x * 1000), 120, 3000) ,
        lambda v: f"{v:,.0f}")
    add("xAI 2036 revenue ($B)", 160.0,
        lambda: solve_scalar(lambda x: set_seg(p, "xAI", "rev_target", x * 1000), 160, 5000),
        lambda v: f"{v:,.0f}")
    add("Launch 2036 revenue ($B)", 40.0,
        lambda: solve_scalar(lambda x: set_seg(p, "Launch", "rev_target", x * 1000), 40, 5000),
        lambda v: f"{v:,.0f}")
    add("Starlink terminal margin", 0.60,
        lambda: solve_scalar(lambda x: set_seg(p, "Starlink", "margin_target", x), 0.60, 3.0),
        lambda v: f"{v:.0%}", feasible_cap=0.95)
    add("xAI terminal margin", 0.25,
        lambda: solve_scalar(lambda x: set_seg(p, "xAI", "margin_target", x), 0.25, 3.0),
        lambda v: f"{v:.0%}", feasible_cap=0.95)
    add("WACC (terminal growth fixed)", p.wacc,
        lambda: solve_scalar(lambda x: clone(p, wacc=x), p.g_term + 0.003, p.wacc),
        lambda v: f"{v:.2%}")
    add("Terminal growth (WACC fixed)", p.g_term,
        lambda: solve_scalar(lambda x: clone(p, g_term=x), p.g_term, p.wacc - 0.003),
        lambda v: f"{v:.2%}")
    add("All 2036 revenues x k", 1.0,
        lambda: solve_scalar(
            lambda k: set_seg(set_seg(set_seg(p, "Starlink", "rev_target", 120000 * k),
                                      "xAI", "rev_target", 160000 * k),
                              "Launch", "rev_target", 40000 * k), 1.0, 12.0),
        lambda v: f"x{v:.2f}")

    print("=" * 86)
    print(f"LAYER 1 -- What must each lever be, ALONE, to justify ${TARGET/1e6:.2f}T?")
    print(f"(base model value: ${base_v/1e6:.3f}T = DCF + options; all other parameters at base)")
    print("=" * 86)
    print(f"{'Parameter':<34}{'Base':>12}{'Implied by $1.77T':>22}{'Feasible?':>12}")
    print("-" * 86)
    for r in rows:
        if r["implied"] is None:
            imp, feas = "no value exists", "NO"
        else:
            imp = r["fmt"](r["implied"])
            feas = "yes" if r["feasible"] else "NO (>95% margin)"
        base_s = r["fmt"](r["base"]) if not isinstance(r["base"], str) else r["base"]
        print(f"{r['parameter']:<34}{base_s:>12}{imp:>22}{feas:>12}")
    print("=" * 86)
    return rows, base_v


def figure(p: FirmParams):
    """Layer 2: (a) sufficient-statistic projection; (b) the xAI slice with comp bands."""
    plt.rcParams.update({"font.size": 10.5, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.alpha": 0.25, "figure.dpi": 120,
                         "legend.frameon": False, "savefig.bbox": "tight"})
    fig, (axA, axB) = plt.subplots(2, 1, figsize=(7.2, 9.4))

    # ---- Panel (a): iso-value curves in (aggregate 2036 revenue, blended terminal margin) ----
    base_revs = {"Launch": 40000.0, "Starlink": 120000.0, "xAI": 160000.0}
    R_base = sum(base_revs.values())                            # 320,000 $M
    m_base = sum(base_revs[s.name] * s.margin_target for s in p.segments) / R_base  # blended

    def value_at(k_rev, s_margin):
        q = copy.deepcopy(p)
        for s in q.segments:
            s.rev_target = base_revs[s.name] * k_rev
            s.margin_target = min(s.margin_target * s_margin, 0.99)
        return det_value(q)

    ks = np.linspace(0.5, 4.0, 36)
    targets = [(1.0e6, "C0", "$1.0T"), (1.3e6, "C2", "$1.3T (published DCF)"),
               (TARGET, "k", "$1.77T (IPO)"), (2.5e6, "C3", "$2.5T (ARK 2030)")]
    for tval, col, lab in targets:
        xs, ys = [], []
        for k in ks:
            sm = solve_scalar(lambda s: None or _wrap(p, base_revs, k, s), 0.2, 2.49, target=tval)
            if sm is not None and m_base * sm <= 0.99:
                xs.append(R_base * k / 1000)
                ys.append(m_base * sm)
        axA.plot(xs, ys, "-", color=col, lw=1.6, label=lab)
    axA.scatter([R_base / 1000], [m_base], marker="o", s=70, color="C0", zorder=5)
    axA.annotate("our base", (R_base / 1000, m_base), textcoords="offset points",
                 xytext=(8, -12), fontsize=8.5)
    dam_R, dam_m = 420.0, (40 * .45 + 120 * .60 + 160 * .25 + 100 * .30) / 420  # incl. Expansion line
    axA.scatter([dam_R], [dam_m], marker="D", s=55, color="C2", zorder=5)
    axA.annotate("published forecast", (dam_R, dam_m), textcoords="offset points", xytext=(8, 4), fontsize=8.5)
    axA.set_xlabel("Aggregate 2036 revenue (\\$B)")
    axA.set_ylabel("Blended terminal operating margin")
    axA.set_title("(a) Iso-value curves in the two composites")
    axA.set_ylim(0.1, 1.0)
    axA.legend(loc="upper right", fontsize=8)

    # ---- Panel (b): the xAI slice against comp-disciplined margin bands ----
    ms = np.linspace(0.05, 0.60, 23)
    xs, ys = [], []
    for m in ms:
        r = solve_scalar(lambda x: set_seg(set_seg(p, "xAI", "margin_target", m),
                                           "xAI", "rev_target", x * 1000), 100, 20000)
        if r is not None:
            xs.append(r)
            ys.append(m)
    axB.plot(xs, ys, "-", color="k", lw=1.8, label="(rev, margin) pairs giving \\$1.77T")
    axB.axhspan(0.10, 0.25, color="C0", alpha=0.15)
    axB.axhspan(0.25, 0.40, color="C2", alpha=0.15)
    axB.text(0.985, 0.175, "margins of listed AI-infrastructure firms (10-25%)",
             transform=axB.get_yaxis_transform(), ha="right", va="center", fontsize=8.5, color="C0")
    axB.text(0.985, 0.325, "margins of mature software and cloud franchises (25-40%)",
             transform=axB.get_yaxis_transform(), ha="right", va="center", fontsize=8.5, color="C2")
    axB.scatter([160], [0.25], marker="D", s=55, color="C2", zorder=5)
    axB.annotate("base target\n(160, 25%)", (160, 0.25), textcoords="offset points",
                 xytext=(8, -22), fontsize=8.5)
    axB.set_xlabel("xAI 2036 revenue (\\$B)  --  all other segments at base")
    axB.set_ylabel("xAI terminal operating margin")
    axB.set_title("(b) What \\$1.77T requires of the AI business")
    axB.set_xlim(0, max(xs) * 1.05 if xs else 5000)
    axB.legend(loc="upper right", fontsize=8)

    fig.tight_layout()
    figs = ROOT / "paper" / "draft" / "output" / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    fig.savefig(figs / "fig_inverse_valuation.pdf")
    fig.savefig(figs / "fig_inverse_valuation.png")
    print("Figure written:", figs / "fig_inverse_valuation.pdf")
    return {"panelB_curve": [{"rev_B": x, "margin": y} for x, y in zip(xs, ys)]}


def _wrap(p, base_revs, k_rev, s_margin):
    q = copy.deepcopy(p)
    for s in q.segments:
        s.rev_target = base_revs[s.name] * k_rev
        s.margin_target = min(s.margin_target * s_margin, 0.99)
    return q


def main():
    p = FirmParams()
    rows, base_v = implied_table(p)
    fig_data = figure(p)

    out = ROOT / "output" / "tables" / "inverse_valuation.json"
    payload = {"target": TARGET, "base_value": base_v, "options_base": OPTIONS_BASE,
               "implied": [{k: v for k, v in r.items() if k != "fmt"} for r in rows],
               **fig_data}
    out.write_text(json.dumps(payload, indent=2))
    print("Results written:", out)


if __name__ == "__main__":
    main()
