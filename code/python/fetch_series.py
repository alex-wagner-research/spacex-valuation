"""
fetch_series.py -- append SpaceX (SPCX) daily closes to data/raw/post_ipo_series.json.

Pulls daily bars from the Yahoo v8 chart API and adds any finalized trading day on or after the
June 12, 2026 listing that is not already in the series. Existing dates are NEVER overwritten, so
the hand-entered official closes (which can differ from Yahoo's consolidated last trade -- e.g.
day 1 was 161.11 official vs 160.95 on Yahoo) stay authoritative; Yahoo only fills forward. The
current (still-open) session has a null close and is skipped.

The series feeds 10_fig_price_path.py (price vs implied expected return, by trading day). Update it
at milestones (e.g. the day-21 reading, the first earnings release), not in real time; the figure
is meant to stop at the first earnings release.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERIES = ROOT / "data" / "raw" / "post_ipo_series.json"
LISTING = "2026-06-12"


def yahoo_daily(symbol: str):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?range=2mo&interval=1d")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 ValuingSpaceX replication"})
    d = json.loads(urllib.request.urlopen(req, timeout=30).read())
    r = d["chart"]["result"][0]
    import datetime
    out = []
    for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]):
        date = datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime("%Y-%m-%d")
        out.append((date, c))
    return out


def main():
    d = json.loads(SERIES.read_text(encoding="utf-8-sig"))
    have = {c["date"] for c in d["closes"]}
    added = 0
    try:
        fetched = yahoo_daily("SPCX")
    except Exception as e:
        print(f"Yahoo fetch failed ({e!r}); series unchanged with {len(d['closes'])} days.")
        return
    for date, close in fetched:
        if date >= LISTING and date not in have and close is not None:
            d["closes"].append({"date": date, "close": round(float(close), 2),
                                "source": "Yahoo consolidated close"})
            have.add(date)
            added += 1
    d["closes"].sort(key=lambda c: c["date"])
    SERIES.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
    print(f"added {added} day(s); series now {len(d['closes'])} trading days:")
    for c in d["closes"]:
        print(f"  {c['date']}  {c['close']:>8.2f}   {c['source']}")


if __name__ == "__main__":
    main()
