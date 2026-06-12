r"""
08_fig_first_day.py -- where SpaceX's first day lands among well-known large IPOs.

One comparison, one figure, two aligned panels: (a) the first-day return of each deal, with
the literature benchmarks ranked inline as their own rows; (b) the money each deal left on
the table. The pair carries the section's argument: an ordinary return in percent, a record
in dollars.

Named IPOs: offer price, first closing price, and money left on the table from Ritter, "Money
Left on the Table in IPOs by Firm," May 15, 2026 update
(Literature/Ritter_2026_WP_MoneyLeftOnTheTable.pdf); first-day return = close/offer - 1.
Benchmarks: Ritter, "Initial Public Offerings: Updated Statistics," May 18, 2026 (Table 1:
1980-2025 mean 19.0%, median 7.0%; Table 2: mean 13.3% since 2001 for issuers with trailing
sales >= $500M in 2024 dollars); Lowry, Officer, Schwert (2010, JF): 1965-2005 mean 22% with
cross-sectional SD 55% -- the only published dispersion estimate, hence the only row with a
whisker.

SpaceX marker: reads data/raw/post_ipo_day1.json. If the close is filled (after June 12), the
observed first-day return and money on the table are drawn; until then, a clearly-labeled
projected placement is used, from the June 11, 2026 level of the pre-listing perpetual-futures
contracts (~$162 vs the $135 offer; CNBC June 10, 2026, via Money Stuff June 11, 2026).
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
DAY1 = ROOT / "data" / "raw" / "post_ipo_day1.json"
FIGS = ROOT / "paper" / "draft" / "output" / "figures"

OFFER = 135.0

# (label, offer price, first closing price) -- Ritter, Money Left on the Table (May 15, 2026).
# Ritter's listing contains only positive first-day returns by construction (it ranks money left
# on the table), so the negative and near-zero examples below it are sourced separately:
# offer prices verified verbatim from each company's SEC Form 424B4 (Uber: accession
# 0001193125-19-144716, "the initial public offering price is $45.00 per share"; Robinhood:
# 0001628280-21-015076, "$38.00"; Facebook: 0001193125-12-240111, "PRICE $38.00 A SHARE");
# first closing prices from exchange data (Yahoo Finance daily closes: UBER 2019-05-10 41.57,
# HOOD 2021-07-29 34.82, META 2012-05-18 38.23).
DEALS = [
    ("Robinhood (2021)",       38.00,  34.82),
    ("Uber (2019)",            45.00,  41.57),
    ("Facebook (2012)",        38.00,  38.23),
    ("General Motors (2010)",  33.00,  34.19),
    ("Blackstone (2007)",      31.00,  35.06),
    ("Mastercard (2006)",      39.00,  46.00),
    ("Kenvue (2023)",          22.00,  26.90),
    ("Visa (2008)",            44.00,  56.50),
    ("Rivian (2021)",          78.00, 100.73),
    ("Goldman Sachs (1999)",   53.00,  70.375),
    ("UPS (1999)",             50.00,  68.125),
    ("Coupang (2021)",         35.00,  49.25),
    ("Medline (2025)",         29.00,  41.00),
    ("Snap (2017)",            17.00,  24.48),
    ("Twitter (2013)",         26.00,  44.90),
    ("DoorDash (2020)",       102.00, 189.51),
    ("Snowflake (2020)",      120.00, 253.93),
    ("Airbnb (2020)",          68.00, 144.71),
    ("Circle (2025)",          31.00,  83.23),
    ("Figma (2025)",           33.00, 115.50),
]

# Money left on the table, $B -- verbatim dollar amounts from Ritter's listing (May 15, 2026):
# Visa $5,075,000,000; Airbnb $3,937,028,063; Snowflake $3,750,040,000; Rivian $3,477,690,000;
# Figma $3,047,309,018; DoorDash $2,887,830,000; Medline $2,592,413,784; Coupang $1,852,500,000;
# Circle $1,775,820,000; UPS $1,586,300,000; Snap $1,496,000,000; Twitter $1,323,000,000;
# Goldman Sachs $959,100,000 (domestic tranche, as tabulated); Kenvue $846,809,000;
# General Motors $568,820,000; Blackstone $541,328,968; Mastercard $430,646,384.
# Robinhood, Uber, and Facebook are NOT in the listing (it contains only positive amounts by
# construction); their rows carry no bar in panel (b).
MONEY_B = {
    "Visa (2008)": 5.075, "Airbnb (2020)": 3.937, "Snowflake (2020)": 3.750,
    "Rivian (2021)": 3.478, "Figma (2025)": 3.047, "DoorDash (2020)": 2.888,
    "Medline (2025)": 2.592, "Coupang (2021)": 1.853, "Circle (2025)": 1.776,
    "UPS (1999)": 1.586, "Snap (2017)": 1.496, "Twitter (2013)": 1.323,
    "Goldman Sachs (1999)": 0.959, "Kenvue (2023)": 0.847, "General Motors (2010)": 0.569,
    "Blackstone (2007)": 0.541, "Mastercard (2006)": 0.431,
}

# Benchmark rows (ranked inline with the deals): Ritter, Updated Statistics (May 18, 2026);
# the 1965-2005 row is Lowry-Officer-Schwert (2010), the only one with a published SD.
BENCH = [
    ("All-IPO median, 1980-2025", 7.0, None),
    ("Large-issuer mean, 2001-2025", 13.3, None),
    ("All-IPO mean, 1980-2025", 19.0, None),
    ("All-IPO mean, 1965-2005 ($\\pm$SD)", 22.0, 55.0),
]

GOLD, GREEN = "#B8860B", "#2E7D32"


def spacex_day1():
    d = json.loads(DAY1.read_text(encoding="utf-8-sig"))
    shares_m = float(d.get("shares_offered_m") or 555.6)
    if d.get("close") is not None:
        c = float(d["close"])
        return (c / OFFER - 1) * 100, (c - OFFER) * shares_m / 1000, "SpaceX (June 12)"
    return (162.0 / OFFER - 1) * 100, (162.0 - OFFER) * shares_m / 1000, "SpaceX (projected)"


def main():
    sx_ret, sx_money, sx_lab = spacex_day1()
    rows = [(lab, (c / o - 1) * 100, MONEY_B.get(lab), "deal") for lab, o, c in DEALS]
    rows += [(lab, r, sd, "bench") for lab, r, sd in BENCH]
    rows += [(sx_lab, sx_ret, sx_money, "sx")]
    rows.sort(key=lambda r: r[1])

    plt.rcParams.update({"font.size": 12, "axes.spines.top": False, "axes.spines.right": False,
                         "figure.dpi": 120, "savefig.bbox": "tight"})
    fig, (ax, axm) = plt.subplots(1, 2, figsize=(10.6, 9.4), sharey=True,
                                  gridspec_kw={"width_ratios": [2.1, 1.0], "wspace": 0.04})

    for i, (lab, r, extra, kind) in enumerate(rows):
        color = {"sx": GOLD, "bench": GREEN, "deal": "C0"}[kind]
        # ---- panel (a): first-day return ----
        if kind == "bench":
            if extra is not None:                      # the LOS row: mean with +/- SD whisker
                ax.errorbar(r, i, xerr=extra, color=color, fmt="s", ms=5.5,
                            elinewidth=1.0, capsize=3, zorder=4)
            else:
                ax.plot(r, i, marker="s", ms=5.5, color=color, zorder=4)
            ax.text(r + 3, i, f"{r:.0f}%", va="center", fontsize=10, color=color, zorder=6,
                    bbox=dict(facecolor="white", edgecolor="none", pad=0.4, alpha=0.85))
        else:
            ax.hlines(i, 0, r, color=color, lw=1.1, alpha=0.55)
            ax.plot(r, i, marker="D" if kind == "sx" else "o", ms=9 if kind == "sx" else 6,
                    color=color, zorder=5)
            neg = r < 0
            ax.text(r - 3 if neg else r + 3, i, f"{r:+.0f}%", va="center", fontsize=10,
                    ha="right" if neg else "left",
                    color=color if kind == "sx" else "0.25",
                    fontweight="bold" if kind == "sx" else "normal")
        # ---- panel (b): money left on the table ----
        if kind == "deal" and extra is not None:
            axm.barh(i, extra, height=0.62, color="C0", alpha=0.65)
            axm.text(extra + 0.18, i, f"{extra:.1f}", va="center", fontsize=10, color="0.25")
        elif kind == "sx":
            axm.barh(i, extra, height=0.62, color=GOLD, alpha=0.85)
            axm.text(extra + 0.18, i, f"{extra:.1f}", va="center", fontsize=10,
                     color=GOLD, fontweight="bold")

    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([lab for lab, *_ in rows], fontsize=11)
    for tick, (lab, _, _, kind) in zip(ax.get_yticklabels(), rows):
        if kind == "sx":
            tick.set_fontweight("bold")
            tick.set_color(GOLD)
        elif kind == "bench":
            tick.set_style("italic")
            tick.set_color(GREEN)
    ax.axvline(0, color="0.2", lw=0.8)
    ax.set_xlabel("(a) First-day return, offer to first close (percent)")
    ax.set_xlim(-40, max(r for _, r, *_ in rows) * 1.13)
    axm.set_xlabel("(b) Money left on the table ($bn)")
    axm.set_xlim(0, sx_money * 1.14)
    axm.tick_params(left=False)
    FIGS.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGS / "fig_first_day_returns.pdf")
    fig.savefig(FIGS / "fig_first_day_returns.png")
    print("SpaceX:", f"{sx_ret:+.1f}%", f"${sx_money:.1f}B", f"({sx_lab})")
    print("Figure written:", FIGS / "fig_first_day_returns.pdf")


if __name__ == "__main__":
    main()
