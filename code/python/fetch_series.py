"""
fetch_series.py -- populate and cross-check SpaceX (SPCX) daily OHLC in
data/raw/post_ipo_series.json, fully automatically (no hand-entry).

SOURCE OF RECORD: the Nasdaq official historical API (api.nasdaq.com) -- the listing exchange's own
published daily open / high / low / close / volume. The closing price is the Nasdaq official close.
The historical endpoint only returns SETTLED trading days, so a still-open session is never written.

CROSS-CHECK: an independent session OHLC is recomputed from Yahoo 1-minute bars (a different vendor
and code path). The reconciliation panel prints Nasdaq vs Yahoo for every day and flags any
disagreement beyond tolerance, so a corrupted figure cannot pass silently.

SAME-DAY FALLBACK: right after the close, Nasdaq's historical record can lag by a few hours. If the
market has closed (>= 16:05 ET) and Nasdaq does not yet carry today but Yahoo has a complete 1-minute
session, today is written PROVISIONALLY from Yahoo and tagged as such; the next run replaces it with
the Nasdaq official bar automatically.

Workflow: run `python fetch_series.py` after the close. Run `python fetch_series.py --check` anytime
to reconcile without writing. Feeds 10_fig_price_path.py.
"""
from __future__ import annotations

import datetime
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERIES = ROOT / "data" / "raw" / "post_ipo_series.json"
LISTING = "2026-06-12"
ET_OFFSET = datetime.timedelta(hours=-4)           # June 2026 is EDT (UTC-4); for session grouping
CLOSE_TOL = 0.005                                  # 0.5%: flag a close disagreement above this
OHLC_TOL = 0.01                                    # 1.0%: flag an O/H/L disagreement above this
NASDAQ_SRC = "Nasdaq official historical (api.nasdaq.com)"

_NASDAQ_HDR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
               "Accept": "application/json, text/plain, */*", "Accept-Language": "en-US,en;q=0.9",
               "Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"}


def _get(url: str, headers: dict):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(url, headers=headers), timeout=30).read())


def _num(s):
    return float(str(s).replace("$", "").replace(",", "").strip())


def nasdaq_daily(symbol: str, fromdate: str, todate: str) -> dict:
    """Official daily OHLC + volume from Nasdaq, keyed by YYYY-MM-DD (settled days only)."""
    url = (f"https://api.nasdaq.com/api/quote/{symbol}/historical?assetclass=stocks"
           f"&fromdate={fromdate}&todate={todate}&limit=9999")
    d = _get(url, _NASDAQ_HDR)
    rows = ((d.get("data") or {}).get("tradesTable") or {}).get("rows") or []
    out = {}
    for r in rows:
        m, day, y = r["date"].split("/")
        out[f"{y}-{m}-{day}"] = {"open": round(_num(r["open"]), 2), "high": round(_num(r["high"]), 2),
                                 "low": round(_num(r["low"]), 2), "close": round(_num(r["close"]), 2),
                                 "volume": int(_num(r["volume"]))}
    return out


def yahoo_intraday(symbol: str) -> dict:
    """Independent session OHLC recomputed from Yahoo 1-minute bars (regular session, ET-grouped)."""
    d = _get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
             f"?range=5d&interval=1m&includePrePost=false", {"User-Agent": "Mozilla/5.0"})
    r = d["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    by_day: dict[str, list] = {}
    for i, t in enumerate(r["timestamp"]):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c):
            continue
        et = datetime.datetime.fromtimestamp(t, datetime.timezone.utc) + ET_OFFSET
        by_day.setdefault(et.strftime("%Y-%m-%d"), []).append((t, o, h, l, c))
    out = {}
    for date, rows in by_day.items():
        rows.sort()
        out[date] = {"open": round(rows[0][1], 2), "high": round(max(x[2] for x in rows), 2),
                     "low": round(min(x[3] for x in rows), 2), "close": round(rows[-1][4], 2)}
    return out


def settled_today() -> bool:
    now_et = datetime.datetime.now(datetime.timezone.utc) + ET_OFFSET
    return now_et.time() >= datetime.time(16, 5)


def _flag(a, b, tol):
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)) or a == 0:
        return ""
    return "  <-- DIFF" if abs(a - b) / abs(a) > tol else ""


def reconcile(bars: dict, nasdaq: dict, intra: dict):
    print("\nRECONCILIATION  (source of record = Nasdaq official; Yahoo 1-minute is the cross-check)\n")
    for date in sorted(set(bars) | {x for x in nasdaq if x >= LISTING} | {x for x in intra if x >= LISTING}):
        nd, it = nasdaq.get(date), intra.get(date)
        src = (bars.get(date) or {}).get("close_source", "")
        print(f"  {date}   [{src}]")
        for k in ("open", "high", "low", "close"):
            nv = nd.get(k) if nd else None
            iv = it.get(k) if it else None
            tol = CLOSE_TOL if k == "close" else OHLC_TOL
            sd = lambda v: f"{v:>8.2f}" if isinstance(v, (int, float)) else f"{'--':>8}"
            print(f"      {k:<5}  nasdaq {sd(nv)}   yahoo-1m {sd(iv)}{_flag(nv, iv, tol)}")
    print()


def main():
    dry = "--check" in sys.argv
    d = json.loads(SERIES.read_text(encoding="utf-8-sig"))
    today_et = (datetime.datetime.now(datetime.timezone.utc) + ET_OFFSET).strftime("%Y-%m-%d")
    try:
        nasdaq = nasdaq_daily("SPCX", d.get("offer_date", LISTING), today_et)
    except Exception as e:
        print(f"Nasdaq fetch failed ({e!r}); series unchanged with {len(d['bars'])} days.")
        return
    try:
        intra = yahoo_intraday("SPCX")
    except Exception as e:
        print(f"(Yahoo 1-minute cross-check unavailable: {e!r})")
        intra = {}

    # Build the authoritative bar set: Nasdaq official for every settled day it carries.
    bars: dict[str, dict] = {}
    for date, row in nasdaq.items():
        if date < LISTING:
            continue
        bars[date] = {"date": date, **{k: row[k] for k in ("open", "high", "low", "close")},
                      "volume": row["volume"], "close_source": NASDAQ_SRC}

    # Same-day fallback: market closed, Nasdaq not yet updated, but Yahoo has a full session.
    prov = 0
    if today_et >= LISTING and today_et not in bars and settled_today() and today_et in intra:
        it = intra[today_et]
        bars[today_et] = {"date": today_et, **it,
                          "close_source": "Yahoo 1-minute (PROVISIONAL; Nasdaq official pending)"}
        prov = 1

    if dry:
        print(f"[--check] read-only; nothing written. Nasdaq carries {len(bars)} settled day(s).")
    else:
        d["bars"] = [bars[k] for k in sorted(bars)]
        SERIES.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {len(d['bars'])} trading day(s) from Nasdaq official"
              + (f" (+{prov} provisional from Yahoo, pending Nasdaq)" if prov else "") + ":")
        for b in d["bars"]:
            print(f"  {b['date']}  O {b['open']:>7.2f}  H {b['high']:>7.2f}  L {b['low']:>7.2f}  "
                  f"C {b['close']:>7.2f}   {b['close_source']}")
    reconcile(bars if not dry else {b["date"]: b for b in d["bars"]}, nasdaq, intra)


if __name__ == "__main__":
    main()
