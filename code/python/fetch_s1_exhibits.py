"""
fetch_s1_exhibits.py -- download the complete SpaceX Form S-1 document set from EDGAR.

Fetches every .htm document of accession 0001628280-26-036936 (Form S-1, filed 2026-05-20):
the main S-1 body and all exhibits, fully searchable HTML, into data/raw/s1_exhibits/.
Also writes a README.md index there with the official exhibit descriptions parsed from the
EDGAR filing-index page. The R*.htm XBRL renderings are skipped (financial-data viewer
artifacts, not filing documents).

The free-writing prospectus (accession 0001628280-26-041013), which carries the full
preliminary prospectus text, lives separately at data/raw/spacex_prospectus_fwp_20260605.htm.
"""

from __future__ import annotations

import re
import time
import html
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "data" / "raw" / "s1_exhibits"
BASE = "https://www.sec.gov/Archives/edgar/data/1181412/000162828026036936"
INDEX = f"{BASE}/0001628280-26-036936-index.htm"
UA = {"User-Agent": "Research alexander.wagner@df.uzh.ch"}


def get(url: str) -> bytes:
    with urlopen(Request(url, headers=UA)) as r:
        return r.read()


def main():
    DEST.mkdir(parents=True, exist_ok=True)

    # 1) Parse the filing index: document name -> (type, description)
    idx = get(INDEX).decode("utf-8", errors="ignore")
    docs = {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", idx, re.S):
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        m = re.search(r'href="[^"]*/([\w\-.]+\.htm)"', row)
        if m and len(cells) >= 4:
            # EDGAR index columns: Seq | Description | Document | Type | Size
            docs[m.group(1)] = (cells[3] if len(cells) > 3 else "", cells[1])

    # 2) Download every filing .htm (main body + exhibits; skip XBRL viewer R*.htm)
    names = [n for n in docs if not re.match(r"R\d+\.htm$", n)]
    lines = ["# SpaceX Form S-1 -- complete document set (searchable HTML)", "",
             f"Source: SEC EDGAR accession 0001628280-26-036936 (Form S-1, filed 2026-05-20),",
             f"downloaded from {BASE}/ .", "",
             "The full preliminary prospectus text (with financial-statement notes) is in the",
             "free-writing prospectus at `../spacex_prospectus_fwp_20260605.htm` (searchable HTML;",
             "an illustrated PDF rendering is next to it). Prospectus page images are in",
             "`../prospectus/`.", "", "| File | Type | Description |", "|---|---|---|"]
    for n in sorted(names):
        typ, desc = docs[n]
        out = DEST / n
        if not out.exists() or out.stat().st_size == 0:
            out.write_bytes(get(f"{BASE}/{n}"))
            time.sleep(0.4)
        lines.append(f"| {n} | {typ} | {desc} |")
        print(f"{n:<34} {out.stat().st_size:>10,}  {typ:<10} {desc[:70]}")
    (DEST / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\nIndex written:", DEST / "README.md")


if __name__ == "__main__":
    main()
