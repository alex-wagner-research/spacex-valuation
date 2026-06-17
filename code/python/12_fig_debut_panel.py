r"""
12_fig_debut_panel.py -- the debut of SpaceX against large IPOs, across four debut facts.

Combines what the first-day figure already showed -- first-day return and money left on the table --
with two additions: how each deal's price moved AFTER the first day (the continuation, first close to
third close), and the implied volatility the options market set on each deal's first day of listed
options. The deals are sorted by first-day return, so the panels read left to right from the headline
pop to the dollars at stake; SpaceX is highlighted throughout.

The story the panels tell together: SpaceX's first-day RETURN is ordinary (panel a, left bars), but
unlike the blockbuster debuts -- which mostly gave back ground over the next two sessions -- it kept
CLIMBING (panel a, right bars); the options market prices its UNCERTAINTY in the top tier of all
large IPOs (panel b); and the DOLLARS it left on the table are a record (panel c). The headline pop
is not where the action is.

Data:
  * first-day return and money: imported from 08_fig_first_day.py (same deals).
  * continuation (first close -> third close): data/clean/ipo_aftermarket.csv (11_ipo_aftermarket.py).
  * first-day-of-options ATM 30-day implied vol: data/clean/ipo_options_iv.csv (OptionMetrics IvyDB
    US, via code/R/pull_optionmetrics_iv.R).
  * SpaceX: first-day return and money from post_ipo_day1.json; continuation from post_ipo_series.json
    (Nasdaq official); implied vol from the CBOE snapshot of its first options day (June 16, 2026).
  Deals lacking any of these (Twitter, Visa, Circle) are omitted; the figure keeps the 16 with all of
  return, continuation, and options IV.

Writes paper/draft/output/figures/fig_debut_panel.pdf|png and paper/draft/output/optionsiv.tex.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import re
import statistics as st
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
IVCSV = ROOT / "data" / "clean" / "ipo_options_iv.csv"
AMCSV = ROOT / "data" / "clean" / "ipo_aftermarket.csv"
CBOE = ROOT / "data" / "raw" / "options_day1_cboe.json"
SERIES = ROOT / "data" / "raw" / "post_ipo_series.json"
FIGS = ROOT / "paper" / "draft" / "output" / "figures"
OUT_TEX = ROOT / "paper" / "draft" / "output" / "optionsiv.tex"

BLUE, GREEN = "#4C72B0", "#55A868"           # first-day return, continuation


def _load_first_day():
    spec = importlib.util.spec_from_file_location(
        "fd", Path(__file__).resolve().parent / "08_fig_first_day.py")
    fd = importlib.util.module_from_spec(spec); spec.loader.exec_module(fd)
    return fd


def _read_map(path, key, val):
    out = {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            try:
                out[r[key]] = val(r)
            except (ValueError, KeyError):
                pass
    return out


def spacex_iv_cboe(target_days=30):
    import datetime
    data = json.loads(CBOE.read_text())["data"]
    px = float(data["current_price"])
    rows = [(m.group(1), int(m.group(3)) / 1000.0, float(o["iv"]))
            for o in data["options"]
            if (m := re.search(r"(\d{6})([CP])(\d{8})", o.get("option", ""))) and o.get("iv")]
    base = datetime.date(2026, 6, 16)
    exps = sorted({y for y, _, _ in rows})
    exp = min(exps, key=lambda y: abs(
        (datetime.date(2000 + int(y[:2]), int(y[2:4]), int(y[4:])) - base).days - target_days))
    atm = [iv for y, k, iv in rows if y == exp and abs(k - px) <= 7.5]
    return st.mean(atm) * 100


def main():
    if not (IVCSV.exists() and AMCSV.exists()):
        print("debut panel skipped: needs data/clean/ipo_options_iv.csv (OptionMetrics IvyDB US via "
              "WRDS; run code/R/pull_optionmetrics_iv.R) and data/clean/ipo_aftermarket.csv (run "
              "11_ipo_aftermarket.py).")
        return
    fd = _load_first_day()
    iv = _read_map(IVCSV, "label", lambda r: float(r["atm_iv30_pct"]))
    cont = _read_map(AMCSV, "label", lambda r: (float(r["c2"]) / float(r["c0"]) - 1) * 100)

    rows = []                                    # (display, firstday%, cont%, iv%, money$B|None, sx)
    for lab, offer, close in fd.DEALS:
        base = lab.split(" (")[0]
        if base not in iv or base not in cont:
            continue
        rows.append((lab, (close / offer - 1) * 100, cont[base], iv[base], fd.MONEY_B.get(lab), False))
    sx_ret, sx_money, _ = fd.spacex_day1()
    bars = json.loads(SERIES.read_text(encoding="utf-8-sig"))["bars"]
    sx_cont = (float(bars[min(2, len(bars) - 1)]["close"]) / float(bars[0]["close"]) - 1) * 100
    sx_iv = spacex_iv_cboe()
    rows.append(("SpaceX (2026)", sx_ret, sx_cont, sx_iv, sx_money, True))
    rows.sort(key=lambda r: r[1])                # sort by first-day return (ascending -> top = largest)

    iv_b = sorted(r[3] for r in rows if not r[5])
    med_iv = st.median(iv_b)
    n_iv_above = sum(1 for v in iv_b if v > sx_iv)
    cont_b = [r[2] for r in rows if not r[5]]
    n_cont_above = sum(1 for v in cont_b if v > sx_cont)
    n_faded = sum(1 for v in cont_b if v < 0)
    med_ret = st.median(r[1] for r in rows if not r[5])      # comparable medians, for the summary row
    med_ct = st.median(cont_b)

    plt.rcParams.update({"font.size": 14, "axes.spines.top": False, "axes.spines.right": False,
                         "figure.dpi": 120, "savefig.bbox": "tight"})
    fig, (axr, axc, axv) = plt.subplots(
        1, 3, figsize=(8.8, 10.2), sharey=True,
        gridspec_kw={"width_ratios": [1.45, 1.0, 1.35], "wspace": 0.10})
    GOLD = fd.GOLD

    for i, (lab, ret, ct, ivv, money, sx) in enumerate(rows):
        if sx:
            for a in (axr, axc, axv):
                a.axhspan(i - 0.5, i + 0.5, color=GOLD, alpha=0.13, zorder=0)
        col = GOLD if sx else BLUE
        edge = dict(edgecolor=GOLD, linewidth=2.2) if sx else dict(edgecolor="none")
        # (a) first-day return
        axr.barh(i, ret, height=0.6, color=col, alpha=0.9 if sx else 0.6, zorder=3, **edge)
        axr.text(ret + (3 if ret >= 0 else -3), i, f"{ret:+.0f}%", va="center",
                 ha="left" if ret >= 0 else "right", fontsize=11.5,
                 color=GOLD if sx else "0.3", fontweight="bold" if sx else "normal")
        # (b) continuation, first close -> third close
        axc.barh(i, ct, height=0.6, color=GOLD if sx else GREEN, alpha=0.9 if sx else 0.65,
                 zorder=3, **edge)
        if sx:
            axc.text(ct + 1, i, f"{ct:+.0f}%", va="center", ha="left", fontsize=11.5,
                     color=GOLD, fontweight="bold")
        # (c) implied vol at options launch
        axv.hlines(i, 0, ivv, color=col, lw=1.3, alpha=0.6)
        axv.plot(ivv, i, marker="D" if sx else "o", ms=11 if sx else 7, color=col, zorder=5)
        axv.text(ivv + 5, i, f"{ivv:.0f}%", va="center", ha="left", fontsize=12,
                 color=GOLD if sx else "0.3", fontweight="bold" if sx else "normal")

    # ---- median-of-comparables summary row, above the deals and separated by a rule ----
    GREY = "0.55"
    y_med = len(rows) + 0.55
    axr.barh(y_med, med_ret, height=0.6, color=GREY, zorder=3)
    axr.text(med_ret + 3, y_med, f"{med_ret:+.0f}%", va="center", ha="left", fontsize=11.5, color="0.3")
    axc.barh(y_med, med_ct, height=0.6, color=GREY, zorder=3)
    axc.text(med_ct + (1 if med_ct >= 0 else -1), y_med, f"{med_ct:+.0f}%", va="center",
             ha="left" if med_ct >= 0 else "right", fontsize=11.5, color="0.3")
    axv.hlines(y_med, 0, med_iv, color=GREY, lw=1.3, alpha=0.7)
    axv.plot(med_iv, y_med, marker="s", ms=8, color=GREY, zorder=5)
    axv.text(med_iv + 5, y_med, f"{med_iv:.0f}%", va="center", ha="left", fontsize=12, color="0.3")
    for a in (axr, axc, axv):
        a.axhline(len(rows) - 0.2, color="0.7", lw=0.8)

    axr.set_yticks(list(range(len(rows))) + [y_med])
    axr.set_yticklabels([lab for lab, *_ in rows] + ["Median"], fontsize=13)
    for tick, r in zip(axr.get_yticklabels(), rows):
        if r[5]:
            tick.set_fontweight("bold"); tick.set_color(GOLD)
    axr.get_yticklabels()[-1].set_style("italic"); axr.get_yticklabels()[-1].set_color("0.35")
    axr.set_ylim(-0.7, y_med + 0.7)
    axr.axvline(0, color="0.2", lw=0.8)
    axr.set_xlabel("(a) First-day return\n(offer to first close)")
    axr.set_xlim(min(0, min(r[1] for r in rows) * 1.1), max(r[1] for r in rows) * 1.16)

    axc.axvline(0, color="0.2", lw=0.8)
    axc.set_xlabel("(b) Continuation\n(first close to day 3)")
    cl = [r[2] for r in rows]
    axc.set_xlim(min(cl) * 1.25, max(cl) * 1.2)

    axv.set_xlabel("(c) Implied vol at options launch\n(ATM, $\\sim$30-day)")
    axv.set_xlim(0, max(r[3] for r in rows) * 1.12)

    FIGS.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGS / "fig_debut_panel.pdf")
    fig.savefig(FIGS / "fig_debut_panel.png")

    above = [r[0].split(" (")[0] for r in sorted(
        [r for r in rows if not r[5] and r[2] > sx_cont], key=lambda r: -r[2])]
    above_names = ("no comparable deal" if not above else above[0] if len(above) == 1
                   else " and ".join(above) if len(above) == 2
                   else ", ".join(above[:-1]) + ", and " + above[-1])
    macros = {"ivN": f"{len(iv_b)}", "ivMedPct": f"{med_iv:.0f}", "ivSxPct": f"{sx_iv:.0f}",
              "ivSxRank": f"{n_iv_above + 1}", "ivNTotal": f"{len(iv_b) + 1}",
              "contSxPct": f"{sx_cont:.0f}", "contSxRank": f"{n_cont_above + 1}",
              "contNFaded": f"{n_faded}", "contN": f"{len(cont_b)}", "contAboveNames": above_names}
    OUT_TEX.write_text("% Auto-generated by 12_fig_debut_panel.py; do not edit by hand.\n"
                       + "\n".join(f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in macros.items()) + "\n",
                       encoding="utf-8")
    print(f"SpaceX: first-day {sx_ret:+.0f}%, continuation {sx_cont:+.0f}% (#{n_cont_above + 1} of "
          f"{len(cont_b) + 1}; {n_faded} of {len(cont_b)} comparables faded), IV {sx_iv:.0f}% "
          f"(#{n_iv_above + 1} of {len(iv_b) + 1}, median {med_iv:.0f}%)")
    print("Figure:", FIGS / "fig_debut_panel.pdf")


if __name__ == "__main__":
    main()
