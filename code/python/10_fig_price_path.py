r"""
10_fig_price_path.py -- the share-price path and the expected return it implies, by trading day.

Reads data/raw/post_ipo_series.json (offer + daily OHLC bars from the Nasdaq official record, plus
expected near-term events). For each price it inverts the model -- operating inputs and the option
layer held at base, exactly as 04_inverse_valuation.py and 09_post_ipo_update.py -- for the discount
rate that equates the model value to that capitalization.

The horizontal axis counts TRADING DAYS (business-day index from the offer), so weekends do not
open gaps between sessions. The marked future events are weeks out, so the axis is also BROKEN: a
wide left panel for the trading-day region and a narrow right panel for the future-events region,
joined by a zig-zag cut that signals the omitted span. Fonts are sized for print legibility.

  * left price axis (dark): the daily price as an open-high-low-close bar (and the offer as a point);
  * right return axis (orange): the implied expected return at each close (whisker = intraday range),
    against the 8.25 percent baseline cost of capital;
  * dashed verticals mark the expected near-term events.

Writes paper/draft/output/figures/fig_price_path.pdf|png and paper/draft/output/pricepath.tex.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
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
MAROON = "#9E2A2B"    # the counterfactual "median IPO path"
GREY = "0.38"
TW = 0.30             # OHLC open/close tick half-length, in trading-day units

_dec = json.loads((ROOT / "output" / "tables" / "decomposition.json").read_text())
OPT_BASE = sum(v for k, v in _dec["options"].items() if k != "Abandonment")


def implied_pct(price: float, sh: float):
    w = _solve(FirmParams(), price * sh, OPT_BASE)
    return w * 100 if w else None


def D(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d")


def bidx(odate: datetime, d: datetime) -> int:
    """Business-day (trading-day) index of d, counting the offer date as 0."""
    n, cur = 0, odate
    while cur.date() < d.date():
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            n += 1
    return n


def zigzag(ax, x, n=17, amp=0.010, color=GREY, lw=1.2):
    """A vertical zig-zag at axes-x = x (spanning y 0..1), marking a broken axis."""
    ys = [i / (n - 1) for i in range(n)]
    xs = [x + (amp if i % 2 else -amp) for i in range(n)]
    ax.plot(xs, ys, transform=ax.transAxes, color=color, lw=lw,
            clip_on=False, zorder=30, solid_capstyle="round")


def draw_prices(axp, axr, bars, bx, offer, sh):
    """Price OHLC bars + offer point on axp; implied-return markers + whiskers on axr."""
    cx = [0] + bx
    cc = [offer] + [float(b["close"]) for b in bars]
    axp.plot(cx, cc, "-", color=NAVY, lw=1.0, alpha=0.30, zorder=2)
    axp.plot(0, offer, "o", color=NAVY, ms=7, zorder=4)
    axp.annotate(f"Offer \\${offer:.0f}", (0, offer), textcoords="offset points",
                 xytext=(0, -12), ha="center", va="top", fontsize=13,color=NAVY)
    for b, x in zip(bars, bx):
        axp.vlines(x, b["low"], b["high"], color=NAVY, lw=2.0, zorder=3)
        axp.plot([x - TW, x], [b["open"], b["open"]], color=NAVY, lw=2.0, zorder=3)
        axp.plot([x, x + TW], [b["close"], b["close"]], color=NAVY, lw=2.0, zorder=3)
        axp.annotate(f"\\${b['close']:.0f}", (x, b["high"]), textcoords="offset points",
                     xytext=(0, 7), ha="center", fontsize=13,color=NAVY, fontweight="bold")

    rc = [implied_pct(offer, sh)] + [implied_pct(float(b["close"]), sh) for b in bars]
    axr.plot(cx, rc, "--s", color=ORANGE, lw=1.8, ms=7, zorder=4)
    axr.annotate(f"{rc[0]:.2f}%", (0, rc[0]), textcoords="offset points", xytext=(0, 10),
                 ha="center", fontsize=13,color=ORANGE)
    for j, (b, x) in enumerate(zip(bars, bx)):
        axr.vlines(x, implied_pct(float(b["high"]), sh), implied_pct(float(b["low"]), sh),
                   color=ORANGE, lw=1.3, alpha=0.45, zorder=2)
        if j == len(bars) - 1:
            rcl = implied_pct(float(b["close"]), sh)
            axr.annotate(f"{rcl:.2f}%", (x, rcl), textcoords="offset points", xytext=(11, 0),
                         ha="left", va="center", fontsize=13,color=ORANGE, fontweight="bold")


def mark_events(axp, events, odate, lo, hi):
    """Dashed vertical for each event in [lo, hi], with a horizontal label below the date axis.
    Labels alternate onto a second row so neighbours in a narrow panel do not collide."""
    inrange = [e for e in events if lo <= bidx(odate, D(e["date"])) <= hi]
    for k, e in enumerate(inrange):
        x = bidx(odate, D(e["date"]))
        axp.axvline(x, color=GREY, lw=1.0, ls="--", zorder=1)
        frac = (x - lo) / (hi - lo) if hi > lo else 0.5
        ha = "left" if frac < 0.22 else ("right" if frac > 0.78 else "center")
        dy = -30 - 15 * (k % 2)
        axp.annotate(e["label"], xy=(x, 0), xycoords=("data", "axes fraction"),
                     xytext=(0, dy), textcoords="offset points", ha=ha, va="top",
                     fontsize=11.5, color="0.32", annotation_clip=False)


def main():
    d = json.loads(SERIES.read_text(encoding="utf-8-sig"))
    offer = float(d["offer_price"]); sh = float(d["shares_m"])
    odate = D(d["offer_date"]); wend = D(d["window_end"])
    bars = d["bars"]; events = d.get("events", [])
    bx = [bidx(odate, D(b["date"])) for b in bars]
    last_x = bx[-1] if bx else 0

    plt.rcParams.update({"font.size": 15, "figure.dpi": 130, "savefig.bbox": "tight"})

    # Partition: the trading-day region (left) and the far future events (right).
    left_cut = last_x + 1.5
    ev_x = {e["label"]: bidx(odate, D(e["date"])) for e in events}
    right_evs = [e for e in events if left_cut < ev_x[e["label"]] <= bidx(odate, wend)]
    broken = bool(right_evs)

    if broken:
        right_idx = [ev_x[e["label"]] for e in right_evs]
        right_lo, right_hi = min(right_idx) - 2, max(right_idx) + 1.6
        fig, (axL, axR) = plt.subplots(
            1, 2, sharey=True, figsize=(12.4, 7.1),
            gridspec_kw={"width_ratios": [3.0, 1.25], "wspace": 0.06})
        axLr, axRr = axL.twinx(), axR.twinx()
    else:
        fig, axL = plt.subplots(figsize=(11.6, 7.1))
        axLr = axL.twinx(); axR = axRr = None

    draw_prices(axL, axLr, bars, bx, offer, sh)

    # counterfactual: where the price would stand had SpaceX followed the median post-listing drift
    # of the large IPOs in Figure 8 -- anchored at the first close, applying their median day-2 and
    # day-3 returns (computed from the same cached panel as 11_ipo_aftermarket.py).
    try:
        import importlib.util
        import statistics as _st
        _spec = importlib.util.spec_from_file_location(
            "ipo_am", Path(__file__).resolve().parent / "11_ipo_aftermarket.py")
        _am = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_am)
        _panel = _am.build_panel()
        _meds = [_st.median((c1 / c0 - 1) for _, c0, c1, c2 in _panel),
                 _st.median((c2 / c1 - 1) for _, c0, c1, c2 in _panel)]
        cf = [float(bars[0]["close"])]
        for m in _meds[:len(bars) - 1]:
            cf.append(cf[-1] * (1 + m))
        cfx = bx[:len(cf)]
        axL.plot(cfx, cf, ":o", color=MAROON, lw=1.9, ms=6, zorder=3)
        axL.annotate("median IPO price path", (cfx[-1], cf[-1]), textcoords="offset points",
                     xytext=(5, -10), ha="left", va="top", fontsize=12.5, color=MAROON)
    except Exception as _e:                                # never let the reference path break the figure
        print(f"  (counterfactual median-IPO path skipped: {_e!r})")

    axL.set_ylim(0, PMAX); axLr.set_ylim(0, RMAX)
    axL.set_ylabel("Share price (\\$)", color=NAVY, fontsize=16)
    axL.tick_params(axis="y", labelcolor=NAVY, labelsize=14)
    axL.tick_params(axis="x", labelsize=14)
    axL.set_xlim(-0.7, left_cut + 0.8)

    # trading-day ticks, labelled by date (no weekend gaps)
    left_ticks = {0: odate}
    for b, x in zip(bars, bx):
        left_ticks[x] = D(b["date"])
    for e in events:
        if ev_x[e["label"]] <= left_cut:
            left_ticks[ev_x[e["label"]]] = D(e["date"])
    axL.set_xticks(sorted(left_ticks))
    axL.set_xticklabels([left_ticks[k].strftime("%b %d") for k in sorted(left_ticks)])

    # baseline cost of capital (return axis), label parked top-left, clear of the event labels
    return_axes = [axLr] + ([axRr] if broken else [])
    for ar in return_axes:
        ar.axhline(BASELINE, color="0.55", lw=1.0, ls=":", zorder=1)
    axLr.annotate(f"baseline cost of capital {BASELINE:.2f}%", (-0.6, BASELINE),
                  textcoords="offset points", xytext=(0, 4), ha="left", va="bottom",
                  fontsize=13,color="0.40")

    mark_events(axL, events, odate, -0.7, left_cut + 0.8)

    if broken:
        axR.set_ylim(0, PMAX); axRr.set_ylim(0, RMAX)
        axR.set_xlim(right_lo, right_hi)
        rticks = sorted({ev_x[e["label"]]: D(e["date"]) for e in right_evs}.items())
        axR.set_xticks([k for k, _ in rticks])
        axR.set_xticklabels([v.strftime("%b %d") for _, v in rticks])
        axR.tick_params(axis="x", labelsize=14)
        axR.tick_params(axis="y", left=False, labelleft=False)
        axLr.tick_params(axis="y", right=False, labelright=False)
        axRr.set_ylabel("Implied expected return (cost of capital), percent",
                        color=ORANGE, fontsize=15)
        axRr.tick_params(axis="y", labelcolor=ORANGE, labelsize=14)
        mark_events(axR, events, odate, right_lo, right_hi)
        for sp in ("top", "right"):
            axL.spines[sp].set_visible(False); axLr.spines[sp].set_visible(False)
        for sp in ("top", "left"):
            axR.spines[sp].set_visible(False); axRr.spines[sp].set_visible(False)
        axLr.set_zorder(axL.get_zorder() + 1); axLr.patch.set_visible(False)
        zigzag(axL, 1.0); zigzag(axR, 0.0)
    else:
        axLr.set_ylabel("Implied expected return (cost of capital), percent",
                        color=ORANGE, fontsize=15)
        axLr.tick_params(axis="y", labelcolor=ORANGE, labelsize=14)
        for ax in (axL, axLr):
            ax.spines["top"].set_visible(False)

    FIGS.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGS / "fig_price_path.pdf")
    fig.savefig(FIGS / "fig_price_path.png")

    # ---- macros ----
    last_b = bars[-1]
    last_w = implied_pct(float(last_b["close"]), sh)
    L = ["% Auto-generated by 10_fig_price_path.py; do not edit by hand.",
         f"\\newcommand{{\\ppFirstDate}}{{June 12}}",
         f"\\newcommand{{\\ppLastDate}}{{{D(last_b['date']).strftime('%B ') + str(int(last_b['date'][-2:]))}}}",
         f"\\newcommand{{\\ppNDays}}{{{len(bars)}}}",
         f"\\newcommand{{\\ppLatestPrice}}{{{float(last_b['close']):.2f}}}",
         f"\\newcommand{{\\ppLatestCapT}}{{{float(last_b['close']) * sh / 1e6:.2f}}}",
         f"\\newcommand{{\\ppLatestWaccPct}}{{{last_w:.2f}}}",
         f"\\newcommand{{\\ppLatestErpPp}}{{{last_w - RF:.2f}}}",
         f"\\newcommand{{\\ppOfferWaccPct}}{{{implied_pct(offer, sh):.2f}}}",
         f"\\newcommand{{\\ppLatestCumPct}}{{{(float(last_b['close']) / offer - 1) * 100:.1f}}}",
         f"\\newcommand{{\\ppLatestHigh}}{{{float(last_b['high']):.2f}}}"]
    if len(bars) >= 2:
        prev_c = float(bars[-2]["close"])
        L += [f"\\newcommand{{\\ppSecondDayPct}}{{{(float(bars[1]['close']) / float(bars[0]['close']) - 1) * 100:.1f}}}",
              f"\\newcommand{{\\ppLatestDayPct}}{{{(float(last_b['close']) / prev_c - 1) * 100:.1f}}}",
              f"\\newcommand{{\\ppLatestHighRetPct}}{{{(float(last_b['high']) / prev_c - 1) * 100:.1f}}}"]
    OUT_TEX.write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"path ({len(bars)} trading days + offer):")
    print(f"  Offer    ${offer:>7.2f}  implied {implied_pct(offer, sh):.2f}%   (t-day 0)")
    for b, x in zip(bars, bx):
        print(f"  {b['date']}  ${float(b['close']):>7.2f}  implied {implied_pct(float(b['close']), sh):.2f}%   (t-day {x})")
    print("Figure:", FIGS / "fig_price_path.pdf")


if __name__ == "__main__":
    main()
