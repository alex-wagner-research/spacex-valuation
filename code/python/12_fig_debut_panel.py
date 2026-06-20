r"""
12_fig_debut_panel.py -- the debut of SpaceX against the largest U.S. IPOs, across three debut facts.

Three panels, one row per deal, sorted by first-day return so the panels read top-to-bottom from the
biggest pop down: (a) the first-day return (offer to first close); (b) the continuation over the
first trading week (first close to fifth close), the move AFTER the headline pop; and (c) the
at-the-money, ~30-day implied volatility the options market set on each deal's first day of listed
options. SpaceX is highlighted throughout, with a grey median-of-comparables row at the top.

The continuation window is the first five trading sessions, a fixed ex-ante horizon applied to every
deal, rather than a window pinned to SpaceX's own path; the three-session figure (SpaceX's local
peak) and the two-session figure are kept for the robustness statement that the "did not fade"
contrast does not depend on where the window ends.

The comparison set is OBJECTIVE and ex ante: the largest U.S. common-stock IPOs by gross proceeds,
2000-present (the rule SpaceX itself tops). It is built by code/R/pull_sdc_ipo_raw.R ->
build_ipo_universe_from_raw.py -> code/R/pull_debut_panel_wrds.R, which writes the single file read
here. Drawing prices and implied vol from CRSP and OptionMetrics (not Yahoo) recovers delisted names
(Twitter) and maps options by CUSIP (fixing reused tickers like Visa's). A handful of deals had no
listed options in the OptionMetrics vintage; they keep their return and continuation bars and simply
carry no implied-vol marker in panel (c), and the implied-vol statistics are computed over the rest.

Data:
  * data/clean/ipo_debut_panel.csv -- one row per comparison deal: first-day return, continuation
    to the 2nd / 3rd / 5th close, and first-options-day ATM 30-day implied vol (NA if no options),
    all from CRSP + OptionMetrics via WRDS.
  * SpaceX: first-day return and continuation from post_ipo_series.json (Nasdaq official); implied
    vol from the CBOE snapshot of its first options day (June 16, 2026). SpaceX is not yet in
    CRSP/OptionMetrics, so it is overlaid from these sources rather than read from the panel.

Writes paper/draft/output/figures/fig_debut_panel.pdf|png and paper/draft/output/optionsiv.tex.
"""
from __future__ import annotations

import csv
import datetime
import json
import re
import statistics as st
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / "data" / "clean" / "ipo_debut_panel.csv"
CBOE = ROOT / "data" / "raw" / "options_day1_cboe.json"
SERIES = ROOT / "data" / "raw" / "post_ipo_series.json"
FIGS = ROOT / "paper" / "draft" / "output" / "figures"
OUT_TEX = ROOT / "paper" / "draft" / "output" / "optionsiv.tex"
OUT_LAG = ROOT / "paper" / "draft" / "output" / "optionslag.tex"

BLUE, GREEN, GOLD = "#4C72B0", "#55A868", "#B8860B"   # first-day return / continuation / SpaceX
DISPLAY_N = 25        # paper figure: largest-by-proceeds comparison deals (panel CSV is in that order)
N_SLIDE = 15          # presentation figure: a reduced set (largest by proceeds); the rest are in the paper
CAP_B = 40.0          # panel (b) x-axis cap; extreme continuations run off-scale, labeled at the edge


def _short(label: str) -> str:
    """Trim SDC issuer names to a clean display label."""
    s = re.sub(r"\s+(Inc|Corp|Co|Holdings?|Hldgs?|Hldg|Group|Worldwide|Technologies|Automotive|"
               r"Financial|Markets|Software|Animal Health|Analytics|Resources)\b\.?", " ", label)
    s = re.sub(r"\s+", " ", s).strip().rstrip(",")
    fixes = {"General Motors": "General Motors", "Dun & Bradst": "Dun & Bradstreet",
             "Santander Consumer USA": "Santander Consumer", "AXA Equitable": "AXA Equitable",
             "Citizens": "Citizens Financial", "Kinder Morgan": "Kinder Morgan"}
    return fixes.get(s, s) or label


def spacex_iv_cboe(target_days=30):
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


def _f(x):
    return float(x) if x not in ("", "NA", None) else None


def load_panel():
    """rows: (label, first_day_ret%, cont5%, cont3%, cont2%, iv%|None, is_spacex)."""
    rows = []
    with open(PANEL, newline="") as f:
        for r in csv.DictReader(f):
            rows.append((_short(r["label"]),
                         float(r["first_day_ret_pct"]),
                         _f(r.get("cont5_pct")),     # figure window: first trading week
                         _f(r.get("cont3_pct")),     # third close (the peak, discussed in the text)
                         _f(r.get("cont2_pct")),     # second close (window-robustness check)
                         _f(r.get("atm_iv30_pct")),
                         False))
    return rows[:DISPLAY_N]                                 # largest DISPLAY_N by proceeds


def build_optlag_table():
    """Write the options-launch-timing appendix table (booktabs) from the panel + a SpaceX reference
    row, and return the comparables' calendar-day lags (listing -> first listed options) for macros."""
    import datetime as _dt

    def esc(s):
        return s.replace("&", r"\&")

    recs = []                                              # (ipo_date, label, opt_date|None, lag|None)
    with open(PANEL, newline="") as f:
        for r in list(csv.DictReader(f))[:DISPLAY_N]:      # same set shown in Figure 7
            ipo, opt = r["ipo_date"], r.get("first_opt_date", "")
            if opt in ("", "NA"):
                recs.append((ipo, _short(r["label"]), None, None))
            else:
                lag = (_dt.date.fromisoformat(opt) - _dt.date.fromisoformat(ipo)).days
                recs.append((ipo, _short(r["label"]), opt, lag))
    lags = sorted(l for *_, l in recs if l is not None)
    sx = ("2026-06-12", "SpaceX", "2026-06-16",
          (_dt.date(2026, 6, 16) - _dt.date(2026, 6, 12)).days)
    ordered = sorted(recs, key=lambda x: x[0]) + [sx]      # chronological by IPO date; SpaceX last

    L = [r"\begin{tabular}{llcr}", r"\toprule",
         r"Company & IPO date & First listed options & Days to options \\", r"\midrule"]
    for ipo, lab, opt, lag in ordered:
        name = r"\textbf{SpaceX}" if lab == "SpaceX" else esc(lab)
        L.append(f"{name} & {ipo} & {opt if opt else 'none in sample'} & "
                 f"{lag if lag is not None else '---'} \\\\")
    L += [r"\bottomrule", r"\end{tabular}"]
    OUT_LAG.write_text("% Auto-generated by 12_fig_debut_panel.py; do not edit by hand.\n"
                       + "\n".join(L) + "\n", encoding="utf-8")
    return lags


def draw(rows, med_ret, med_ct, med_iv, out_stem):
    """Render the three-panel debut figure for `rows` (SpaceX included, sorted by first-day return)
    and the full-set medians, to FIGS/<out_stem>.pdf|png. Used for both the full paper figure and a
    reduced presentation figure."""
    n = len(rows)
    plt.rcParams.update({"font.size": 12, "axes.spines.top": False, "axes.spines.right": False,
                         "figure.dpi": 120, "savefig.bbox": "tight"})
    fig, (axr, axc, axv) = plt.subplots(
        1, 3, figsize=(9.0, 0.34 * n + 1.6), sharey=True,
        gridspec_kw={"width_ratios": [1.45, 1.0, 1.35], "wspace": 0.10})

    for i, (lab, ret, ct, ct3, ct2, ivv, sx) in enumerate(rows):
        if sx:
            for a in (axr, axc, axv):
                a.axhspan(i - 0.5, i + 0.5, color=GOLD, alpha=0.13, zorder=0)
        edge = dict(edgecolor=GOLD, linewidth=2.2) if sx else dict(edgecolor="none")
        axr.barh(i, ret, height=0.6, color=GOLD if sx else BLUE, alpha=0.9 if sx else 0.6,
                 zorder=3, **edge)
        axr.text(ret + (2.5 if ret >= 0 else -2.5), i, f"{ret:+.0f}%", va="center",
                 ha="left" if ret >= 0 else "right", fontsize=11,
                 color=GOLD if sx else "0.3", fontweight="bold" if sx else "normal")
        if ct is not None:
            axc.barh(i, ct, height=0.6, color=GOLD if sx else GREEN, alpha=0.9 if sx else 0.65,
                     zorder=3, **edge)
            if sx:
                axc.text(ct + 1, i, f"{ct:+.0f}%", va="center", ha="left", fontsize=11,
                         color=GOLD, fontweight="bold")
            elif ct > CAP_B:                               # off-scale continuation, labeled at the edge
                axc.text(CAP_B * 0.97, i, f"{ct:+.0f}%", va="center", ha="right",
                         fontsize=9.5, color="0.2", fontweight="bold")
        if ivv is not None:
            axv.hlines(i, 0, ivv, color=GOLD if sx else BLUE, lw=1.3, alpha=0.6)
            axv.plot(ivv, i, marker="D" if sx else "o", ms=11 if sx else 7,
                     color=GOLD if sx else BLUE, zorder=5)
            axv.text(ivv + 4, i, f"{ivv:.0f}%", va="center", ha="left", fontsize=11,
                     color=GOLD if sx else "0.3", fontweight="bold" if sx else "normal")

    # ---- median-of-comparables row, above the deals and separated by a rule ----
    GREY = "0.55"
    y_med = n + 0.55
    axr.barh(y_med, med_ret, height=0.6, color=GREY, zorder=3)
    axr.text(med_ret + 2.5, y_med, f"{med_ret:+.0f}%", va="center", ha="left", fontsize=11, color="0.3")
    axc.barh(y_med, med_ct, height=0.6, color=GREY, zorder=3)
    axc.text(med_ct + (1 if med_ct >= 0 else -1), y_med, f"{med_ct:+.0f}%", va="center",
             ha="left" if med_ct >= 0 else "right", fontsize=11, color="0.3")
    axv.hlines(y_med, 0, med_iv, color=GREY, lw=1.3, alpha=0.7)
    axv.plot(med_iv, y_med, marker="s", ms=8, color=GREY, zorder=5)
    axv.text(med_iv + 4, y_med, f"{med_iv:.0f}%", va="center", ha="left", fontsize=11, color="0.3")
    for a in (axr, axc, axv):
        a.axhline(n - 0.2, color="0.7", lw=0.8)

    axr.set_yticks(list(range(n)) + [y_med])
    axr.set_yticklabels([lab for lab, *_ in rows] + ["Median"], fontsize=11.5)
    for tick, r in zip(axr.get_yticklabels(), rows):
        if r[6]:
            tick.set_fontweight("bold"); tick.set_color(GOLD)
    axr.get_yticklabels()[-1].set_style("italic"); axr.get_yticklabels()[-1].set_color("0.35")
    axr.set_ylim(-0.7, y_med + 0.7)
    axr.axvline(0, color="0.2", lw=0.8)
    axr.set_xlabel("(a) First-day return\n(offer to first close)")
    axr.set_xlim(min(0, min(r[1] for r in rows) * 1.1), max(r[1] for r in rows) * 1.18)

    axc.axvline(0, color="0.2", lw=0.8)
    axc.set_xlabel("(b) Continuation\n(first close to day 5)")
    cl = [r[2] for r in rows if r[2] is not None]
    axc.set_xlim(min(cl) * 1.25, min(CAP_B, max(cl) * 1.2))

    axv.set_xlabel("(c) Implied vol at options launch\n(ATM, $\\sim$30-day)")
    axv.set_xlim(0, max([r[5] for r in rows if r[5] is not None]) * 1.14)

    FIGS.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGS / f"{out_stem}.pdf")
    fig.savefig(FIGS / f"{out_stem}.png")
    plt.close(fig)


def main():
    if not PANEL.exists():
        print(f"debut panel skipped: needs {PANEL} (build it via pull_sdc_ipo_raw.R -> "
              "build_ipo_universe_from_raw.py -> pull_debut_panel_wrds.R).")
        return

    comps = load_panel()                                # largest DISPLAY_N by proceeds (proceeds order)

    d = json.loads(SERIES.read_text(encoding="utf-8-sig"))
    offer = float(d["offer_price"]); bars = d["bars"]

    def sxc(k):                                         # SpaceX continuation to its kth daily close
        return (float(bars[min(k - 1, len(bars) - 1)]["close"]) / float(bars[0]["close"]) - 1) * 100

    sx_ret = (float(bars[0]["close"]) / offer - 1) * 100
    sx_c5, sx_c3, sx_c2 = sxc(5), sxc(3), sxc(2)        # five-session window; three is the peak
    sx_iv = spacex_iv_cboe()
    sx_row = ("SpaceX", sx_ret, sx_c5, sx_c3, sx_c2, sx_iv, True)
    rows = sorted(comps + [sx_row], key=lambda r: r[1])  # full figure, biggest pop at the top

    iv_vals = sorted(r[5] for r in comps if r[5] is not None)
    med_iv = st.median(iv_vals)
    med_ret = st.median(r[1] for r in comps)
    med_ct = st.median(r[2] for r in comps if r[2] is not None)         # 5-session median
    n_iv_above = sum(1 for v in iv_vals if v > sx_iv)
    n_cont_above = sum(1 for r in comps if r[2] is not None and r[2] > sx_c5)
    n_faded5 = sum(1 for r in comps if r[2] is not None and r[2] < 0)
    n_faded3 = sum(1 for r in comps if r[3] is not None and r[3] < 0)
    n_faded2 = sum(1 for r in comps if r[4] is not None and r[4] < 0)

    # full figure for the paper, and a reduced one for the deck (largest N_SLIDE by proceeds, the
    # rest noted as "in the paper"); both use the full-set medians for the grey median row
    draw(rows, med_ret, med_ct, med_iv, "fig_debut_panel")
    rows_slide = sorted(comps[:N_SLIDE] + [sx_row], key=lambda r: r[1])
    draw(rows_slide, med_ret, med_ct, med_iv, "fig_debut_panel_slide")

    # ---- macros (names unchanged so the prose keeps resolving) ----
    above = [r[0] for r in sorted([r for r in comps if r[2] is not None and r[2] > sx_c5],
                                  key=lambda r: -r[2])]
    above_names = ("no comparable deal" if not above else above[0] if len(above) == 1
                   else " and ".join(above) if len(above) == 2
                   else ", ".join(above[:-1]) + ", and " + above[-1])

    def ordn(k):                                   # 1->1st, 2->2nd, 3->3rd, 4->4th, 11->11th, ...
        suf = "th" if 10 <= k % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(k % 10, "th")
        return f"{k}{suf}"

    n_noopt = sum(1 for r in comps if r[5] is None)
    lags = build_optlag_table()                            # options-launch appendix table + lag stats
    macros = {"ivN": f"{len(iv_vals)}", "ivMedPct": f"{med_iv:.0f}", "ivSxPct": f"{sx_iv:.0f}",
              "optLagMed": f"{int(st.median(lags))}", "optLagMin": f"{min(lags)}",
              "optLagMax": f"{max(lags)}",
              "ivSxRank": f"{n_iv_above + 1}", "ivSxRankOrd": ordn(n_iv_above + 1),
              "ivNTotal": f"{len(iv_vals) + 1}",
              # continuation: 5-session window is the figure/headline; 3-session is the peak
              "contSxPct": f"{sx_c5:.0f}", "contSxPeakPct": f"{sx_c3:.0f}",
              "contSxRank": f"{n_cont_above + 1}", "contSxRankOrd": ordn(n_cont_above + 1),
              "contN": f"{len(comps)}", "contAboveNames": above_names,
              "contMedPct": f"{med_ct:.0f}",
              "contNFaded": f"{n_faded5}", "contNFadedTwo": f"{n_faded2}",
              "contNFadedThree": f"{n_faded3}", "contWindowDays": "5",
              "debutNTotal": f"{len(comps)}", "debutNoOptN": f"{n_noopt}",
              "debutNShown": f"{min(N_SLIDE, len(comps))}"}   # count in the reduced presentation figure
    OUT_TEX.write_text("% Auto-generated by 12_fig_debut_panel.py; do not edit by hand.\n"
                       + "\n".join(f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in macros.items()) + "\n",
                       encoding="utf-8")
    print(f"{len(comps)} comparison IPOs ({len(iv_vals)} with options IV; {n_noopt} without).")
    print(f"SpaceX first week: +{sx_c5:.0f}% (5-session; peak +{sx_c3:.0f}% at day 3, +{sx_c2:.0f}% at day 2), "
          f"#{n_cont_above + 1} of {len(comps) + 1} by 5-session continuation; above only: {above_names}.")
    print(f"Faded (continuation<0): {n_faded2}/{len(comps)} by day 2, {n_faded3}/{len(comps)} by day 3, "
          f"{n_faded5}/{len(comps)} by day 5. SpaceX faded at none.")
    print(f"IV {sx_iv:.0f}% (#{n_iv_above + 1} of {len(iv_vals) + 1}, median {med_iv:.0f}%). "
          f"Median comparable first-day {med_ret:+.0f}%, 5-session continuation {med_ct:+.0f}%.")
    print("Figure:", FIGS / "fig_debut_panel.pdf")


if __name__ == "__main__":
    main()
