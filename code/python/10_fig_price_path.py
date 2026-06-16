r"""
10_fig_price_path.py -- the share-price path and the expected return it implies, by trading day.

Reads data/raw/post_ipo_series.json (offer + daily OHLC bars + expected near-term events). For
each price it inverts the model -- operating inputs and the option layer held at base, exactly as
04_inverse_valuation.py and 09_post_ipo_update.py -- for the discount rate that equates the model
value to that capitalization. The figure shows, on a calendar axis that runs from the offer to the
first expected earnings release:
  * left axis: the daily price as an open-high-low-close bar (and the offer as a point);
  * right axis: the implied expected return at each close (with a whisker for the intraday range),
    against the 8.25 percent baseline cost of capital;
  * vertical markers for the expected near-term events (listed options, index inclusion, earnings).
Both axes start at zero. The message is the inverse co-movement: a higher price is a lower implied
return and a lower price a higher one, each move a repricing of risk rather than a cash-flow
revision. The window ends at the first earnings release, after which new fundamentals break the
hold-fundamentals-fixed inversion.

Writes paper/draft/output/figures/fig_price_path.pdf|png and paper/draft/output/pricepath.tex.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_valuation import implied_wacc as _solve          # noqa: E402
from spacex_realoptions import FirmParams                 # noqa: E402

SERIES = ROOT / "data" / "raw" / "post_ipo_series.json"
FIGS = ROOT / "paper" / "draft" / "output" / "figures"
OUT_TEX = ROOT / "paper" / "draft" / "output" / "pricepath.tex"
RF = 4.56
BASELINE = 8.25
PMAX = 270.0          # left-axis top: double the $135 offer
RMAX = 9.0            # right-axis top: headroom above the 8.25% baseline
NAVY, ORANGE = "#2E4057", "#E85D04"

_dec = json.loads((ROOT / "output" / "tables" / "decomposition.json").read_text())
OPT_BASE = sum(v for k, v in _dec["options"].items() if k != "Abandonment")


def implied_pct(price: float, sh: float):
    w = _solve(FirmParams(), price * sh, OPT_BASE)
    return w * 100 if w else None


def D(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d")


def main():
    d = json.loads(SERIES.read_text(encoding="utf-8-sig"))
    offer = float(d["offer_price"]); sh = float(d["shares_m"])
    odate = D(d["offer_date"]); wend = D(d["window_end"])
    bars = d["bars"]; events = d.get("events", [])

    plt.rcParams.update({"font.size": 10.5, "figure.dpi": 120, "savefig.bbox": "tight"})
    fig, axp = plt.subplots(figsize=(9.2, 5.4))
    axr = axp.twinx()
    for ax in (axp, axr):
        ax.spines["top"].set_visible(False)

    tw = timedelta(days=0.9)                              # OHLC open/close tick length

    # ---- left axis: price ----
    # offer point + faint close-trajectory line
    cx = [odate] + [D(b["date"]) for b in bars]
    cc = [offer] + [float(b["close"]) for b in bars]
    axp.plot(cx, cc, "-", color=NAVY, lw=1.0, alpha=0.35, zorder=2)
    axp.plot(odate, offer, "o", color=NAVY, ms=6, zorder=4)
    axp.annotate(f"Offer\n\\${offer:.0f}", (odate, offer), textcoords="offset points",
                 xytext=(0, -10), ha="center", va="top", fontsize=8.5, color=NAVY)
    # OHLC bars
    for b in bars:
        x = D(b["date"])
        axp.vlines(x, b["low"], b["high"], color=NAVY, lw=1.4, zorder=3)
        axp.plot([x - tw, x], [b["open"], b["open"]], color=NAVY, lw=1.4, zorder=3)
        axp.plot([x, x + tw], [b["close"], b["close"]], color=NAVY, lw=1.4, zorder=3)
        axp.annotate(f"\\${b['close']:.0f}", (x, b["high"]), textcoords="offset points",
                     xytext=(0, 5), ha="center", fontsize=8.5, color=NAVY)
    axp.set_ylabel("Share price (\\$)", color=NAVY)
    axp.tick_params(axis="y", labelcolor=NAVY)
    axp.set_ylim(0, PMAX)

    # ---- right axis: implied expected return ----
    rc = [implied_pct(offer, sh)] + [implied_pct(float(b["close"]), sh) for b in bars]
    axr.plot(cx, rc, "--s", color=ORANGE, lw=1.4, ms=6, zorder=4)
    axr.annotate(f"{rc[0]:.2f}%", (odate, rc[0]), textcoords="offset points", xytext=(0, 8),
                 ha="center", fontsize=8.5, color=ORANGE)
    for j, b in enumerate(bars):
        x = D(b["date"])
        r_hi = implied_pct(float(b["high"]), sh)         # at intraday high price -> lower return
        r_lo = implied_pct(float(b["low"]), sh)          # at intraday low price  -> higher return
        axr.vlines(x, r_hi, r_lo, color=ORANGE, lw=1.0, alpha=0.4, zorder=2)
        if j == len(bars) - 1:                           # label only the latest, into open space
            rcl = implied_pct(float(b["close"]), sh)
            axr.annotate(f"{rcl:.2f}%", (x, rcl), textcoords="offset points", xytext=(9, 0),
                         ha="left", va="center", fontsize=8.5, color=ORANGE)
    axr.axhline(BASELINE, color="0.55", lw=0.9, ls=":", zorder=1)
    axr.annotate(f"baseline cost of capital {BASELINE:.2f}%", (wend, BASELINE),
                 textcoords="offset points", xytext=(-3, 3), ha="right", va="bottom",
                 fontsize=8, color="0.45")
    axr.set_ylabel("Implied expected return (cost of capital), percent", color=ORANGE)
    axr.tick_params(axis="y", labelcolor=ORANGE)
    axr.set_ylim(0, RMAX)

    # ---- expected-event markers ----
    for e in events:                                     # in the empty lower band, reading upward
        x = D(e["date"])
        if not (odate <= x <= wend):
            continue
        axp.axvline(x, color="0.6", lw=0.8, ls="--", zorder=1)
        axp.annotate(e["label"], (x, 6), rotation=90, va="bottom", ha="center",
                     fontsize=7.2, color="0.45")

    # ---- x axis ----
    axp.set_xlim(odate - timedelta(days=1), wend + timedelta(days=1))
    axp.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
    axp.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    fig.autofmt_xdate(rotation=0, ha="center")

    FIGS.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIGS / "fig_price_path.pdf")
    fig.savefig(FIGS / "fig_price_path.png")

    # ---- macros ----
    last = bars[-1]
    last_w = implied_pct(float(last["close"]), sh)
    L = ["% Auto-generated by 10_fig_price_path.py; do not edit by hand.",
         f"\\newcommand{{\\ppFirstDate}}{{June 12}}",
         f"\\newcommand{{\\ppLastDate}}{{{D(last['date']).strftime('%B ') + str(int(last['date'][-2:]))}}}",
         f"\\newcommand{{\\ppNDays}}{{{len(bars)}}}",
         f"\\newcommand{{\\ppLatestPrice}}{{{float(last['close']):.2f}}}",
         f"\\newcommand{{\\ppLatestCapT}}{{{float(last['close']) * sh / 1e6:.2f}}}",
         f"\\newcommand{{\\ppLatestWaccPct}}{{{last_w:.2f}}}",
         f"\\newcommand{{\\ppLatestErpPp}}{{{last_w - RF:.2f}}}",
         f"\\newcommand{{\\ppOfferWaccPct}}{{{implied_pct(offer, sh):.2f}}}"]
    OUT_TEX.write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"path ({len(bars)} trading days + offer):")
    print(f"  Offer    ${offer:>7.2f}  implied {implied_pct(offer, sh):.2f}%")
    for b in bars:
        print(f"  {b['date']}  ${float(b['close']):>7.2f}  implied {implied_pct(float(b['close']), sh):.2f}%")
    print("Figure:", FIGS / "fig_price_path.pdf")


if __name__ == "__main__":
    main()
