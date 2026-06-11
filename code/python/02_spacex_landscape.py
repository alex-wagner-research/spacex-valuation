"""
02_spacex_landscape.py  --  the market's range of SpaceX valuations over time (Paper 1 figure).

A catalog of publicly reported SpaceX valuations (private rounds, tender/secondary marks, the IPO,
independent intrinsic valuations, and forward growth-model valuations), compiled June 2026, plotted
as total-company valuation over time. Per the 5-for-1 split (May 4, 2026), ONLY total valuations are
comparable across time -- never per-share. Forward valuations (ARK 2030, Sacra 2028) are plotted at
their TARGET year and marked distinctly, never mixed with current-equity points.

Key finding for the paper: of the sources catalogued, NONE uses a formal real-options model
(Morningstar probability-weights the AI unit; ARK simulates Mars as contingent upside -- both
adjacent to, but not, real options). That gap motivates this paper.

Outputs a CSV (data/clean/) and a figure. Each row carries its category, method, and a
confidence flag; MEDIUM/LOW rows were re-verified against their sources before publication.
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]

# (category, source, decimal_date, value_$B, low_$B, high_$B, target_year_or_None, method, real_opt, confidence)
DATA = [
    ("round",       "Sequoia/Coatue round",  2021.10,    74, None, None, None, "Negotiated round", "No", "high"),
    ("round",       "Mirae-led round",       2022.50,   127, None, None, None, "Negotiated round", "No", "med"),
    ("round",       "a16z round",            2023.05,   137, None, None, None, "Negotiated round", "No", "high"),
    ("tender",      "Tender offer",          2023.95,   180, None, None, None, "Tender price", "No", "med"),
    ("tender",      "Tender offer",          2024.50,   210, None, None, None, "Tender price", "No", "high"),
    ("tender",      "Tender offer",          2024.95,   350, None, None, None, "Tender price", "No", "high"),
    ("tender",      "Round + tender",        2025.52,   400, None, None, None, "Round/tender", "No", "high"),
    ("tender",      "Secondary sale",        2025.95,   800, None, None, None, "Tender price", "No", "high"),
    ("merger",      "xAI merger (SpaceX standalone)", 2026.09, 1000, None, None, None, "Negotiated merger", "No", "high"),
    ("secondary",   "Notice.co",             2026.36,  1300, None, None, None, "Order-book mark", "No", "med"),
    ("secondary",   "Forge Global",          2026.44,  1714, None, None, None, "Forge Price (verified)", "No", "high"),
    ("secondary",   "Nasdaq Private Market", 2026.40,  1663, None, None, None, "Platform mark (verified)", "No", "high"),
    ("secondary",   "Hiive",                 2026.36,  1800, None, None, None, "Order-book mark", "No", "med"),
    ("independent", "Morningstar",           2026.42,   780,  611,  950, None, "DCF + prob-weighted AI", "Partial", "high"),
    ("independent", "Doug Kass",             2026.44,   910, None, None, None, "Scenario range", "No", "med"),
    ("independent", "Damodaran",             2026.42,  1300, 1250, 1350, None, "3-segment DCF", "No", "high"),
    ("independent", "Sacra (2028 target)",   2028.00,  1321,  587, 2673, 2028, "Revenue multiple", "No", "high"),
    ("ipo",         "IPO price",             2026.42,  1770, None, None, None, "Fixed-price offering", "No", "high"),
    ("prediction",  "Polymarket (early June)",2026.43, 2300, None, None, None, "Market-implied", "No", "med"),
    # Pre-listing perpetual futures ~$162/share on Hyperliquid and Binance, June 11 (CNBC, June
    # 10, 2026, via Matt Levine, "Money Stuff," Bloomberg Opinion, June 11, 2026).
    # Cash-settled on the LISTED price -> converted at 13,091M post-offering shares, the same
    # basis as the $1.77T offer: 162 x 13,091M = $2,121B.
    ("prediction",  "Perpetual futures (June 11)", 2026.44, 2121, None, None, None, "Derivatives-implied", "No", "high"),
    ("forward",     "ARK/Mach33 (2030 EV)",  2030.00,  2500, 1700, 3100, 2030, "Monte Carlo x18 EBITDA", "Implicit", "high"),
]

STYLE = {  # category -> (marker, color, label)
    "round":       ("o", "0.45", "Private round"),
    "tender":      ("o", "0.45", "Tender / secondary sale"),
    "merger":      ("o", "0.45", "_nolegend_"),
    "secondary":   ("s", "C0",   "Secondary-market mark"),
    "independent": ("D", "C3",   "Independent intrinsic (DCF)"),
    "ipo":         ("*", "k",    "IPO price"),
    "prediction":  ("v", "C4",   "Prediction market"),
    "forward":     ("P", "C2",   "Forward valuation (target yr)"),
}


ARK_COST_OF_EQUITY = 0.10   # OUR assumed rate to present-value ARK's 2030 figure (ARK gives none)
CROSS_DATE = 2026.42        # the IPO-time cross-section snapshot


def ark_present_value():
    """ARK's 2030 EV (and bear/bull) discounted to the cross-section date at our assumed rate."""
    ark = next(d for d in DATA if d[0] == "forward")
    years = ark[6] - CROSS_DATE
    f = (1 + ARK_COST_OF_EQUITY) ** years
    return (f"ARK 2030 (PV @{ARK_COST_OF_EQUITY:.0%})", ark[3] / f, ark[4] / f, ark[5] / f)


def main():
    plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.alpha": 0.25, "figure.dpi": 120,
                         "legend.frameon": False, "savefig.bbox": "tight"})
    fig, (axA, axB) = plt.subplots(2, 1, figsize=(9.0, 8.6),
                                   gridspec_kw={"height_ratios": [1.0, 1.25]})

    # ---------- Panel (a): valuation trajectory over time, LINEAR scale ----------
    traj = sorted([d for d in DATA if d[0] in ("round", "tender", "merger", "ipo")], key=lambda d: d[2])
    xs = [d[2] for d in traj]
    ys = [d[3] / 1000 for d in traj]
    axA.plot(xs, ys, "-o", color="0.45", ms=5, lw=1.2)
    # label every transaction mark directly with its value (so the small early rounds are legible)
    for d in traj:
        if d[0] == "ipo":
            continue                       # the IPO gets its own bold annotation below
        v = d[3]
        txt = f"${v/1000:.2f}T" if v >= 1000 else f"${v}B"
        dy = 9 if v < 1000 else 9
        axA.annotate(txt, (d[2], v / 1000), textcoords="offset points", xytext=(0, dy),
                     ha="center", fontsize=8, color="0.3")
    axA.annotate("IPO\n$1.77T", (2026.42, 1.77), textcoords="offset points", xytext=(-2, 6),
                 ha="right", fontsize=8.5, color="k", fontweight="bold")
    axA.set_xlabel("Year")
    axA.set_ylabel("Total valuation (\\$ trillion)")
    axA.set_title("(a) SpaceX private-market and IPO valuation trajectory")
    axA.set_xlim(2020.7, 2026.9)
    axA.set_ylim(0, 2.0)

    # ---------- Panel (b): the IPO-time cross-section, labeled, with ranges (candles) ----------
    cross = [(d[1], d[3], d[4], d[5]) for d in DATA
             if d[6] is None and d[2] >= 2026.3
             and d[0] in ("independent", "ipo", "secondary", "prediction")]
    cross.append(ark_present_value())                          # add present-valued ARK
    cross.sort(key=lambda r: r[1])
    names = [r[0] for r in cross]
    yy = np.arange(len(cross))
    for i, (src, val, lo, hi) in enumerate(cross):
        if lo is not None and hi is not None:                  # the "candle": a range whisker
            axB.plot([lo / 1000, hi / 1000], [i, i], "-", color="0.55", lw=2.0, alpha=0.7, zorder=1)
        is_ipo = src == "IPO price"
        axB.scatter([val / 1000], [i], s=150 if is_ipo else 80,
                    marker="*" if is_ipo else "o",
                    color="k" if is_ipo else "C0", edgecolor="white", linewidth=0.6, zorder=3)
    axB.axvline(1.77, color="k", ls="--", lw=0.9, alpha=0.5)
    axB.text(1.79, 0.1, "IPO price", fontsize=8.5, color="0.3", va="bottom", ha="left")
    axB.set_yticks(yy)
    axB.set_yticklabels(names, fontsize=9)
    axB.set_xlabel("Total equity valuation at the IPO (\\$ trillion)")
    axB.set_title("(b) Who values SpaceX at what, June 2026 (range = stated bear/bull)")
    axB.set_xlim(0, 2.6)

    fig.tight_layout()
    figs = ROOT / "paper" / "draft" / "output" / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    fig.savefig(figs / "spacex_valuation_landscape.pdf")
    fig.savefig(figs / "spacex_valuation_landscape.png")
    print("Figure written:", figs / "spacex_valuation_landscape.pdf")
    print(f"ARK 2030 present-valued at {ARK_COST_OF_EQUITY:.0%}: ${ark_present_value()[1]/1000:.2f}T")

    # save the dataset
    clean = ROOT / "data" / "clean"
    clean.mkdir(parents=True, exist_ok=True)
    with open(clean / "spacex_valuation_landscape.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["category", "source", "date", "value_Bn", "low_Bn", "high_Bn",
                    "target_year", "method", "real_options", "confidence"])
        w.writerows(DATA)
    print("Data written:", clean / "spacex_valuation_landscape.csv")

    # quick summary
    cur = [d[3] for d in DATA if d[2] >= 2026.3 and d[0] in ("independent", "ipo", "secondary", "prediction")
           and d[6] is None]
    print(f"\nJune-2026 current-equity cross-section: min ${min(cur)/1000:.2f}T, max ${max(cur)/1000:.2f}T "
          f"({max(cur)/min(cur):.1f}x spread)")
    print("None of the catalogued valuations uses a formal real-options model.")


if __name__ == "__main__":
    main()
