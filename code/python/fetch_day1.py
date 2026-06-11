r"""
fetch_day1.py -- pull SpaceX's first-day OHLC from Yahoo's chart API into post_ipo_day1.json.

Run after the June 12, 2026 close:
    python code/python/fetch_day1.py            # fetches SPCX for 2026-06-12, fills the JSON
    python code/python/fetch_day1.py AAPL 2026-06-10   # test mode: any ticker/date, print only

Yahoo's daily bar for an IPO day starts at the opening cross (the first trade), which is the
"open" the postscript uses. New tickers normally appear on Yahoo on listing day; if SPCX is
missing or numbers look off, fill data/raw/post_ipo_day1.json by hand from Nasdaq's official
summary instead. After the JSON is filled: run 09_post_ipo_update.py and 08_fig_first_day.py, flip
\postipotrue in main.tex, recompile with bibtex.
"""

from __future__ import annotations

import datetime
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DAY1 = ROOT / "data" / "raw" / "post_ipo_day1.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def day_ohlc(ticker: str, day: datetime.date) -> dict | None:
    d0 = int(datetime.datetime(day.year, day.month, day.day,
                               tzinfo=datetime.timezone.utc).timestamp())
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
           f"?period1={d0 - 86400}&period2={d0 + 172800}&interval=1d")
    r = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA)).read())
    res = r["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    for i, ts in enumerate(res["timestamp"]):
        if datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).date() == day:
            return {"open": round(q["open"][i], 2), "intraday_high": round(q["high"][i], 2),
                    "intraday_low": round(q["low"][i], 2), "close": round(q["close"][i], 2),
                    "volume_mshares": round(q["volume"][i] / 1e6, 1)}
    return None


def main():
    if len(sys.argv) >= 3:                                   # test mode
        ticker, day = sys.argv[1], datetime.date.fromisoformat(sys.argv[2])
        print(ticker, day, "->", day_ohlc(ticker, day))
        return
    ticker, day = "SPCX", datetime.date(2026, 6, 12)
    bar = day_ohlc(ticker, day)
    if bar is None:
        raise SystemExit(f"No {ticker} bar for {day} on Yahoo yet -- fill {DAY1} by hand "
                         "from Nasdaq's official summary.")
    d = json.loads(DAY1.read_text(encoding="utf-8-sig"))
    d.update(bar)
    d["date"] = str(day)
    DAY1.write_text(json.dumps(d, indent=2), encoding="utf-8")
    print(f"SPCX {day}: open {bar['open']}  high {bar['intraday_high']}  "
          f"low {bar['intraday_low']}  close {bar['close']}  vol {bar['volume_mshares']}M")
    print("Written:", DAY1)
    print("Next: run 09_post_ipo_update.py and 08_fig_first_day.py, flip \\postipotrue, recompile.")


if __name__ == "__main__":
    main()
