r"""
11_ipo_aftermarket.py -- how unusual is SpaceX's day-2/day-3 continuation?

The first-day return has a documented distribution (Figure 8 / 08_fig_first_day.py). The days that
follow have one too: this script measures the second-day, third-day, and cumulative (first close to
third close) returns of the large IPOs that appear in Figure~\ref{fig:firstday}, and locates SpaceX
against them. Returns are split-invariant within the three-day window, so vendor split adjustment of
the price level does not affect them.

Data: first three daily closes from the Yahoo v8 chart API, anchored on each deal's listing date and
verified against the first closing price already used in 08_fig_first_day.py. The pulled closes are
cached to data/clean/ipo_aftermarket.csv; if that file exists the script reads it and does not call
Yahoo, so the build is reproducible offline. SpaceX's own path is read from post_ipo_series.json
(Nasdaq official). Twitter (delisted) and any deal without three clean post-listing closes are
dropped and reported.

Writes paper/draft/output/aftermarket.tex (macros) and data/clean/ipo_aftermarket.csv (the panel).
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import statistics as st
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "clean" / "ipo_aftermarket.csv"
SERIES = ROOT / "data" / "raw" / "post_ipo_series.json"
OUT_TEX = ROOT / "paper" / "draft" / "output" / "aftermarket.tex"

# (label, ticker, listing date, first closing price) -- same deals as Figure 8; first closes match
# 08_fig_first_day.py. Listing dates verified from each deal's first trading day.
IPOS = [
    ("Robinhood", "HOOD", "2021-07-29", 34.82), ("Uber", "UBER", "2019-05-10", 41.57),
    ("Facebook", "META", "2012-05-18", 38.23), ("General Motors", "GM", "2010-11-18", 34.19),
    ("Blackstone", "BX", "2007-06-22", 35.06), ("Mastercard", "MA", "2006-05-25", 46.00),
    ("Kenvue", "KVUE", "2023-05-04", 26.90), ("Visa", "V", "2008-03-19", 56.50),
    ("Rivian", "RIVN", "2021-11-10", 100.73), ("Goldman Sachs", "GS", "1999-05-04", 70.375),
    ("UPS", "UPS", "1999-11-10", 68.125), ("Coupang", "CPNG", "2021-03-11", 49.25),
    ("Snap", "SNAP", "2017-03-02", 24.48), ("Twitter", "TWTR", "2013-11-07", 44.90),
    ("DoorDash", "DASH", "2020-12-09", 189.51), ("Snowflake", "SNOW", "2020-09-16", 253.93),
    ("Airbnb", "ABNB", "2020-12-10", 144.71), ("Circle", "CRCL", "2025-06-05", 83.23),
    ("Figma", "FIG", "2025-07-31", 115.50),
]


def _ep(s: str) -> int:
    return int(dt.datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp())


def yahoo_first_closes(tkr: str, listing: str, n: int = 3):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{tkr}"
           f"?period1={_ep(listing) - 3 * 86400}&period2={_ep(listing) + 16 * 86400}&interval=1d")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    d = json.loads(urllib.request.urlopen(req, timeout=30).read())
    r = d["chart"]["result"][0]
    rows = [(dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d"), c)
            for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]) if c is not None]
    i = next((k for k, (day, _) in enumerate(rows) if day >= listing), None)
    if i is None or i + n - 1 >= len(rows):
        return None
    return [round(rows[i + j][1], 4) for j in range(n)]


def build_panel():
    """Return list of (label, c0, c1, c2), pulling from Yahoo and caching, or reading the cache."""
    if CACHE.exists():
        with CACHE.open(newline="") as f:
            return [(r["label"], float(r["c0"]), float(r["c1"]), float(r["c2"]))
                    for r in csv.DictReader(f)]
    panel = []
    for lab, tkr, listing, first in IPOS:
        try:
            cs = yahoo_first_closes(tkr, listing)
        except Exception as e:
            print(f"  {lab:<16} pull failed ({e!r}); dropped")
            continue
        if not cs:
            print(f"  {lab:<16} insufficient post-listing data; dropped")
            continue
        flag = "" if abs(cs[0] / first - 1) < 0.03 else f"  [level split-adjusted: {cs[0]} vs {first}]"
        print(f"  {lab:<16} closes {cs}{flag}")
        panel.append((lab, *cs))
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    with CACHE.open("w", newline="") as f:
        w = csv.writer(f); w.writerow(["label", "c0", "c1", "c2"])
        for row in panel:
            w.writerow(row)
    return panel


def main():
    panel = build_panel()
    d2 = [(lab, (c1 / c0 - 1) * 100) for lab, c0, c1, c2 in panel]
    d3 = [(lab, (c2 / c1 - 1) * 100) for lab, c0, c1, c2 in panel]
    cum = [(lab, (c2 / c0 - 1) * 100) for lab, c0, c1, c2 in panel]
    n = len(panel)

    d = json.loads(SERIES.read_text(encoding="utf-8-sig"))
    bars = d["bars"]
    k = min(2, len(bars) - 1)                       # third trading day (index 2), or latest
    sx_cum = (float(bars[k]["close"]) / float(bars[0]["close"]) - 1) * 100
    sx_d2 = (float(bars[1]["close"]) / float(bars[0]["close"]) - 1) * 100

    exceed = sorted([lab for lab, v in cum if v > sx_cum],
                    key=lambda L: -dict(cum)[L])
    exceed_d2 = [lab for lab, v in d2 if v > sx_d2]

    def names(xs):
        xs = [x.replace("General Motors", "GM") for x in xs]
        return xs[0] if len(xs) == 1 else " and ".join(xs) if len(xs) == 2 \
            else ", ".join(xs[:-1]) + ", and " + xs[-1]

    macros = {
        "amN": f"{n}",
        "amMedDayTwoPct": f"{st.median(v for _, v in d2):.1f}",
        "amMedDayThreePct": f"{st.median(v for _, v in d3):.1f}",
        "amMedCumPct": f"{st.median(v for _, v in cum):.1f}",
        "amMeanCumPct": f"{st.mean(v for _, v in cum):.1f}",
        "amSxCumPct": f"{sx_cum:.1f}",
        "amNExceedCum": f"{len(exceed)}",
        "amExceedNames": names(exceed),
        "amNExceedDayTwo": f"{len(exceed_d2)}",
    }
    L = ["% Auto-generated by 11_ipo_aftermarket.py; do not edit by hand."]
    L += [f"\\newcommand{{\\{k2}}}{{{v}}}" for k2, v in macros.items()]
    OUT_TEX.parent.mkdir(parents=True, exist_ok=True)
    OUT_TEX.write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"\nBenchmark of {n} large IPOs (Figure 8 deals; Twitter dropped, delisted):")
    print(f"  day-2 median {macros['amMedDayTwoPct']}%,  day-3 median {macros['amMedDayThreePct']}%,"
          f"  cumulative d1-d3 median {macros['amMedCumPct']}% (mean {macros['amMeanCumPct']}%)")
    print(f"SpaceX: day-2 {sx_d2:+.1f}%, cumulative d1-d3 {sx_cum:+.1f}% "
          f"-- exceeded by {len(exceed)} of {n} ({names(exceed)})")
    print("Macros written:", OUT_TEX)


if __name__ == "__main__":
    main()
