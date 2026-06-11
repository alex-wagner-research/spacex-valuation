"""
00_master.py  --  run the full pipeline behind "Valuing SpaceX: Cash Flows versus the Cost of
Capital", in the order the paper uses the outputs.

    python code/python/00_master.py            # everything (skips post-IPO steps until data exists)
    python code/python/00_master.py --from 4   # resume from step 4

Steps, their paper exhibits, and their data dependencies:

  0  fetch prospectus      data/raw/spacex_prospectus_fwp_20260605.htm from SEC EDGAR (if missing)
  1  01_prospectus_text_analysis.py   Figure 2 (term frequencies) + term-count JSON
  2  02_spacex_landscape.py           Figure 1 (valuation landscape) + sourced catalog CSV
  3  03_decomposition.py              Figures 3-4 (abandonment distribution, waterfall) +
                                   decomposition JSON (segments, options, scenarios, validation)
  4  04_inverse_valuation.py          Figure 5 (inverse valuation) + implied-values JSON   [needs 3]
  5  05_physical_implications.py      physical-units JSON for Table 5                      [needs 4]
  6  06_layer3_sampling.py            Figure 6 (joint sampling) + acceptance JSON
  7  07_make_macros.py                paper/draft/output/numbers.tex + Tables 2-5 fragments
                                   [needs 1, 3, 4, 5, 6]
  8  08_fig_first_day.py              Postscript figure (first-day returns; projected marker until
                                   data/raw/post_ipo_day1.json is filled)
  9  09_post_ipo_update.py            Postscript macros [only if post_ipo_day1.json is filled;
                                   fill it via fetch_day1.py after the June 12, 2026 close]

After a full run, compile the paper: in paper/draft/, pdflatex + bibtex + pdflatex x2 on main.tex
(and pdflatex on presentation/valuing_spacex_slides.tex for the deck). The paper's in-text
numbers, tables, and figures are taken from this pipeline's outputs rather than typed by hand.

Requirements: Python 3.11+, numpy, scipy, matplotlib (requirements.txt). Full run takes a few
minutes; step 3 (least-squares Monte Carlo) and step 6 (acceptance sampling) dominate.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

FWP = ROOT / "data" / "raw" / "spacex_prospectus_fwp_20260605.htm"
FWP_URL = ("https://www.sec.gov/Archives/edgar/data/1181412/000162828026041013/"
           "japanfwp_06042026.htm")
DAY1 = ROOT / "data" / "raw" / "post_ipo_day1.json"

STEPS = ["01_prospectus_text_analysis.py", "02_spacex_landscape.py", "03_decomposition.py",
         "04_inverse_valuation.py", "05_physical_implications.py", "06_layer3_sampling.py",
         "07_make_macros.py", "08_fig_first_day.py", "09_post_ipo_update.py"]


def fetch_prospectus():
    if FWP.exists() and FWP.stat().st_size > 1_000_000:
        print(f"[0] prospectus present: {FWP.name} ({FWP.stat().st_size:,} bytes)")
        return
    print(f"[0] downloading prospectus from EDGAR: {FWP_URL}")
    req = urllib.request.Request(FWP_URL, headers={"User-Agent": "ValuingSpaceX replication alexander.wagner@df.uzh.ch"})
    FWP.parent.mkdir(parents=True, exist_ok=True)
    FWP.write_bytes(urllib.request.urlopen(req).read())
    print(f"    saved {FWP.stat().st_size:,} bytes")


def day1_filled() -> bool:
    try:
        d = json.loads(DAY1.read_text(encoding="utf-8-sig"))
        return d.get("open") is not None and d.get("close") is not None
    except FileNotFoundError:
        return False


def main():
    start_from = 0
    if len(sys.argv) >= 3 and sys.argv[1] == "--from":
        start_from = int(sys.argv[2])

    t0 = time.time()
    for d in ["data/raw", "data/clean", "output/figures", "output/tables",
              "paper/draft/output/figures", "paper/draft/output/tables"]:
        (ROOT / d).mkdir(parents=True, exist_ok=True)
    if start_from == 0:
        fetch_prospectus()

    for i, script in enumerate(STEPS, start=1):
        if i < start_from:
            continue
        if script == "09_post_ipo_update.py" and not day1_filled():
            print(f"[{i}] {script}: SKIPPED (post_ipo_day1.json not filled; run fetch_day1.py "
                  "after the June 12, 2026 close)")
            continue
        t = time.time()
        print(f"[{i}] {script} ...")
        r = subprocess.run([sys.executable, str(HERE / script)], cwd=str(ROOT))
        if r.returncode != 0:
            raise SystemExit(f"FAILED at step {i}: {script} (exit {r.returncode})")
        print(f"    done in {time.time() - t:.0f}s")

    print(f"\nPipeline complete in {time.time() - t0:.0f}s.")
    print("Next: compile paper/draft/main.tex (pdflatex + bibtex + pdflatex x2).")


if __name__ == "__main__":
    main()
