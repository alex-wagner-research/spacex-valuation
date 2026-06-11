r"""
08_fig_first_day.py -- where SpaceX's first-day return lands among well-known large IPOs.

One figure, one job: locate the SpaceX first-day return among the first-day returns of
well-known large U.S. IPOs, against the literature benchmarks (all-IPO median and mean,
large-issuer mean).

Named IPOs: offer price and first closing price from Ritter, "Money Left on the Table in IPOs
by Firm," May 15, 2026 update (Literature/Ritter_2026_WP_MoneyLeftOnTheTable.pdf); first-day
return computed as close/offer - 1. Reference lines from Ritter, "Initial Public Offerings:
Updated Statistics," May 18, 2026 (Table 1: 1980-2025 mean 19.0%, median 7.0%; Table 2: mean
13.3% since 2001 for issuers with trailing sales >= $500M in 2024 dollars).

SpaceX marker: reads data/raw/post_ipo_day1.json. If the close is filled (after June 12), the
observed first-day return is drawn; until then, a clearly-labeled projected placement is used,
from the June 11, 2026 level of the pre-listing perpetual-futures contracts (~$162 on
Hyperliquid/Binance vs the $135 offer, i.e. about +20 percent; CNBC June 10, 2026, via Money
Stuff June 11, 2026, archived in documents/).
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

# Reference lines: Ritter, Updated Statistics (May 18, 2026)
MEDIAN_ALL, MEAN_ALL, MEAN_BIG = 7.0, 19.0, 13.3


def spacex_return():
    d = json.loads(DAY1.read_text(encoding="utf-8-sig"))
    if d.get("close") is not None:
        return (float(d["close"]) / OFFER - 1) * 100, "SpaceX (June 12)"
    return (162.0 / OFFER - 1) * 100, "SpaceX (projected)"


def main():
    rows = sorted([(lab, (c / o - 1) * 100) for lab, o, c in DEALS], key=lambda r: r[1])
    sx_ret, sx_lab = spacex_return()
    rows_all = sorted(rows + [(sx_lab, sx_ret)], key=lambda r: r[1])

    plt.rcParams.update({"font.size": 10.5, "axes.spines.top": False, "axes.spines.right": False,
                         "figure.dpi": 120, "savefig.bbox": "tight"})
    fig, ax = plt.subplots(figsize=(7.6, 5.6))
    for i, (lab, r) in enumerate(rows_all):
        is_sx = lab.startswith("SpaceX")
        color = "#B8860B" if is_sx else "C0"
        ax.hlines(i, 0, r, color=color, lw=1.1, alpha=0.55)
        ax.plot(r, i, marker="D" if is_sx else "o", ms=9 if is_sx else 6,
                color=color, zorder=5)
        ax.text(r + 3, i, f"{r:+.0f}%", va="center", fontsize=8.5,
                color=color if is_sx else "0.25",
                fontweight="bold" if is_sx else "normal")
    ax.set_yticks(range(len(rows_all)))
    ax.set_yticklabels([lab for lab, _ in rows_all],
                       fontsize=9.5)
    for tick, (lab, _) in zip(ax.get_yticklabels(), rows_all):
        if lab.startswith("SpaceX"):
            tick.set_fontweight("bold")
            tick.set_color("#B8860B")
    for x, txt in [(MEDIAN_ALL, "all-IPO median 7%"),
                   (MEAN_BIG, "large-issuer mean 13.3%"),
                   (MEAN_ALL, "all-IPO mean 19%")]:
        ax.axvline(x, color="0.55", lw=0.9, ls="--", zorder=1)
        ax.text(x + 2.0, len(rows_all) - 0.55, txt, rotation=90, va="top", ha="left",
                fontsize=7.5, color="0.45")
    ax.axvline(0, color="0.2", lw=0.8)
    ax.set_xlabel("First-day return (offer price to first closing price, percent)")
    ax.set_xlim(-15, max(r for _, r in rows_all) * 1.12)
    fig.tight_layout()
    FIGS.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGS / "fig_first_day_returns.pdf")
    fig.savefig(FIGS / "fig_first_day_returns.png")
    print("SpaceX marker:", f"{sx_ret:+.1f}%", f"({sx_lab})")
    print("Figure written:", FIGS / "fig_first_day_returns.pdf")


if __name__ == "__main__":
    main()
