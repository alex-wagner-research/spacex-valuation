"""
05_physical_implications.py  --  the bottom level of the inverse-valuation zoom tree.

The inverse exercise (04_inverse_valuation.py) says which revenues/margins/rates justify $1.77T.
This exhibit translates those implied revenues into PHYSICAL units -- subscribers, launches per
day, gigawatts -- where beliefs become checkable against engineering and market reality. This is
the anti-vacuity device: "terminal FCF and discounting" is generic; "360 million broadband
subscribers" is not.

Parameter sources (each reported across a range as bounded sensitivity):
  Starlink: ARPU ~$66/mo (S-1/Q1-26 via Damodaran post-S-1 read; down from $99/mo 2024); premium
    case $120/mo. Subscribers today 10.3M (Q1-26). Cell "coverage assurance" is a DIFFERENT product:
    PitchBook-style bull 1.1B subs by 2040 at low ARPU (we use $5-15/mo, flagged estimate).
  Launch: Starship price/launch $150M (ARK saved state; F9 $62.5M). Achieved Starship cadence ~12
    flights TOTAL 2023-26 (~4/yr); licensed Starbase cadence 25/yr.
  AI: revenue per MW-year for AI clouds $1-5M (CoreWeave FY25 $5.13B revenue on ~1-1.3GW contracted;
    Nebius ~$0.94M ARR/MW active; sources in paper Section 4). US data-center load
    ~30-50GW (2025 estimates); total US generating capacity ~1,250GW.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Implied 2036 revenues from the one-lever-at-a-time inverse (inverse_valuation.json)
inv = json.loads((ROOT / "output" / "tables" / "inverse_valuation.json").read_text())
implied = {r["parameter"]: r["implied"] for r in inv["implied"]}
R_starlink = implied["Starlink 2036 revenue ($B)"]        # ~285 $B
R_xai = implied["xAI 2036 revenue ($B)"]                  # ~642 $B
R_launch = implied["Launch 2036 revenue ($B)"]            # ~267 $B


def fmt(x, nd=0):
    return f"{x:,.{nd}f}"


def main():
    rows = []

    # ---- Starlink: subscribers required ----
    for label, arpu_mo in [("at current broadband ARPU ($66/mo)", 66.0),
                           ("at premium broadband ARPU ($120/mo)", 120.0),
                           ("at cell coverage ARPU ($10/mo, est.)", 10.0)]:
        subs_M = R_starlink * 1e9 / (arpu_mo * 12) / 1e6
        rows.append(("Starlink", f"${R_starlink:,.0f}B", f"subscribers {label}",
                     f"{subs_M:,.0f}M", "10.3M today; ~100-400M unserved/rural broadband households"
                     " (verify); PitchBook bull 1.1B CELL subs by 2040"))

    # ---- Launch: cadence required ----
    for label, price_M in [("at $150M per Starship launch", 150.0),
                           ("at $62.5M per Falcon-9 launch", 62.5)]:
        n = R_launch * 1e9 / (price_M * 1e6)
        rows.append(("Launch", f"${R_launch:,.0f}B", f"launches/year {label}",
                     f"{n:,.0f} (= {n/365:.1f}/day)",
                     "achieved Starship: ~12 flights TOTAL 2023-26; licensed 25/yr"))

    # ---- xAI: compute capacity required ----
    for label, rev_per_MW in [("at $5M revenue/MW-yr (CoreWeave-like)", 5.0),
                              ("at $1M revenue/MW-yr (Nebius-like)", 1.0)]:
        gw = R_xai * 1e9 / (rev_per_MW * 1e6) / 1000
        rows.append(("xAI", f"${R_xai:,.0f}B", f"AI compute {label}",
                     f"{gw:,.0f} GW",
                     "US data-center load ~30-50GW; TOTAL US generating capacity ~1,250GW"))

    print("=" * 100)
    print("PHYSICAL IMPLICATIONS of the one-lever revenues that alone justify $1.77T")
    print("=" * 100)
    print(f"{'Segment':<9}{'Implied 2036 rev':<18}{'Physical requirement':<46}{'Quantity':<22}")
    print("-" * 100)
    for seg, rev, req, qty, ref in rows:
        print(f"{seg:<9}{rev:<18}{req:<46}{qty:<22}")
        print(f"{'':<9}{'':<18}  vs reality: {ref}")
    print("=" * 100)

    out = ROOT / "output" / "tables" / "physical_implications.json"
    out.write_text(json.dumps(
        [{"segment": s, "implied_rev": r, "requirement": q, "quantity": v, "reality": ref}
         for s, r, q, v, ref in rows], indent=2))
    print("Written:", out)


if __name__ == "__main__":
    main()
