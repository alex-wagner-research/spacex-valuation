"""
fetch_series.py -- fill SpaceX (SPCX) daily OHLC in data/raw/post_ipo_series.json from Yahoo.

For each trading day on or after the June 12, 2026 listing, the Yahoo v8 chart API supplies open,
high, low and close. Hand-entered fields in the JSON are NEVER overwritten -- in particular the
official closing prints (which can differ from Yahoo's consolidated last trade, e.g. day 1 was
161.11 official vs 160.95 on Yahoo) stay authoritative; Yahoo only fills missing fields and adds
new days. The current (still-open) session has null fields and is skipped.

The series feeds 10_fig_price_path.py (price OHLC vs implied expected return, by trading day, with
the expected near-term events). Update it at milestones, not in real time; the figure is meant to
stop at the first earnings release (the window_end in the JSON).
"""
from __future__ import annotations

import datetime
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERIES = ROOT / "data" / "raw" / "post_ipo_series.json"
LISTING = "2026-06-12"


def yahoo_ohlc(symbol: str):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=3mo&interval=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 ValuingSpaceX replication"})
    d = json.loads(urllib.request.urlopen(req, timeout=30).read())
    r = d["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    out = {}
    for i, t in enumerate(r["timestamp"]):
        date = datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime("%Y-%m-%d")
        row = {k: (round(q[k][i], 2) if q[k][i] is not None else None)
               for k in ("open", "high", "low", "close")}
        out[date] = row
    return out


def main():
    d = json.loads(SERIES.read_text(encoding="utf-8-sig"))
    bars = {b["date"]: b for b in d["bars"]}
    try:
        fetched = yahoo_ohlc("SPCX")
    except Exception as e:
        print(f"Yahoo fetch failed ({e!r}); series unchanged with {len(d['bars'])} days.")
        return
    added = filled = 0
    for date, row in sorted(fetched.items()):
        if date < LISTING or any(v is None for v in row.values()):
            continue                                   # skip pre-listing and the still-open session
        if date not in bars:
            bars[date] = {"date": date, **row, "close_source": "Yahoo consolidated close"}
            added += 1
        else:                                          # fill only missing fields; never overwrite
            for k in ("open", "high", "low", "close"):
                if bars[date].get(k) is None:
                    bars[date][k] = row[k]
                    filled += 1
    d["bars"] = [bars[k] for k in sorted(bars)]
    SERIES.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
    print(f"added {added} day(s), filled {filled} missing field(s); "
          f"series now {len(d['bars'])} trading days:")
    for b in d["bars"]:
        print(f"  {b['date']}  O {b['open']:>7.2f}  H {b['high']:>7.2f}  "
              f"L {b['low']:>7.2f}  C {b['close']:>7.2f}   {b['close_source']}")


if __name__ == "__main__":
    main()
