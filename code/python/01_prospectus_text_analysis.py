"""
01_prospectus_text_analysis.py  --  what does the SpaceX prospectus actually talk about?

Counts exact term/concept frequencies in the SpaceX prospectus text (from the June 5, 2026 FWP,
SEC EDGAR accession 0001628280-26-041013, which embeds the full prospectus including the financial-
statement notes; the FWP wrapper for the Japanese tranche adds negligible English text). Produces:
  1. exact counts for a curated set of concepts (Mars vs AI vs Starlink vs ...),
  2. the top content words overall (stopwords removed) -- "what the document is about",
  3. a figure: horizontal bar chart of concept frequencies for the paper,
  4. a JSON with all counts for macro-driven numbers.

NOTE for the paper: rerun on the final 424(b) prospectus once it is filed; counts here are from the
FWP copy of the preliminary prospectus. Multi-word concepts are counted with regex word boundaries,
case-insensitive; "AI" is counted as the standalone token (word-boundary, so 'said'/'aim' excluded).
"""

from __future__ import annotations

import json
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "raw" / "spacex_prospectus_fwp_20260605.htm"


class TextExtract(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def extract_text(path: Path) -> str:
    html = path.read_text(encoding="utf-8", errors="ignore")
    p = TextExtract()
    p.feed(html)
    text = " ".join(p.parts)
    return re.sub(r"\s+", " ", text)


# Concepts: label -> regex (case-insensitive, word-bounded). Multiple variants OR'd together.
CONCEPTS = {
    "AI / artificial intelligence": r"\bAI\b|\bartificial intelligence\b",
    "Starlink":                     r"\bStarlink\b",
    "satellite(s)":                 r"\bsatellites?\b",
    "launch(es)":                   r"\blaunch(?:es|ed|ing)?\b",
    "Starship":                     r"\bStarship\b",
    "compute / data center":        r"\bcompute\b|\bdata cent(?:er|re)s?\b",
    "Grok / xAI":                   r"\bGrok\b|\bxAI\b",
    "risk(s)":                      r"\brisks?\b",
    "competition / competitors":    r"\bcompetit(?:ion|ors?|ive)\b",
    "government":                   r"\bgovernment(?:al|s)?\b",
    "NASA":                         r"\bNASA\b",
    "defense / military":           r"\bdefen[cs]e\b|\bmilitary\b",
    "Musk":                         r"\bMusk\b",
    "Moon / lunar":                 r"\bmoon\b|\blunar\b",
    "Mars":                         r"\bMars\b",
    "Martian":                      r"\bMartian\b",
    "colony / colonization":        r"\bcolon(?:y|ies|ization|izing)\b",
    "multiplanetary":               r"\bmulti-?planetary\b",
    "subscriber(s)":                r"\bsubscribers?\b",
    "revenue(s)":                   r"\brevenues?\b",
}

STOP = set("""the of and to in a for or that on as with we our by is are be will from this any not
have has Ð±Ñ‹Ð»Ð¾ may which such it its an at if other these those than under more no all could would
should can were been other's including i ii iii us you your they their there per upon also was
into during between each both about against further then once here when where how only own same so
some nor most must shall might out over after before above below up down off again do does did
doing because until while what whom whose s t d ll m o re ve y ain aren couldn didn doesn hadn
hasn haven isn ma mightn mustn needn shan shouldn wasn weren won wouldn page table contents item
part form note notes million billion december march january year years ended period periods
company common stock shares share class months three amount amounts total certain related
respectively approximately number based following included include includes primarily""".split())


def main():
    text = extract_text(SRC)
    n_chars = len(text)

    # 1) concept counts
    counts = {label: len(re.findall(rx, text, flags=re.IGNORECASE)) for label, rx in CONCEPTS.items()}
    # Mars is case-sensitive-meaningful (the planet is capitalized); recount strictly:
    counts["Mars"] = len(re.findall(r"\bMars\b", text))
    counts["Martian"] = len(re.findall(r"\bMartian\b", text))

    # 2) top content words
    words = re.findall(r"[a-z][a-z\-]{2,}", text.lower())
    content = Counter(w for w in words if w not in STOP)
    top30 = content.most_common(30)

    print(f"Document: {SRC.name}  ({n_chars:,} chars of extracted text)")
    print("\n=== Concept frequencies (exact, word-bounded, case-insensitive unless noted) ===")
    for label, c in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {label:<32} {c:>6}")
    print("\n=== Top 30 content words overall ===")
    for w, c in top30:
        print(f"  {w:<24} {c:>6}")

    # 3) figure
    plt.rcParams.update({"font.size": 10.5, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.alpha": 0.25, "figure.dpi": 120,
                         "legend.frameon": False, "savefig.bbox": "tight"})
    items = sorted(counts.items(), key=lambda kv: kv[1])
    fig, ax = plt.subplots(figsize=(7.6, 6.4))
    labels = [k for k, _ in items]
    vals = [v for _, v in items]
    bars = ax.barh(range(len(items)), vals, color="C0")
    ax.set_yticks(range(len(items)))
    ax.set_yticklabels(labels)
    for i, v in enumerate(vals):
        ax.text(v + max(vals) * 0.008, i, str(v), va="center", fontsize=8.5, color="0.25")
    ax.set_xlabel("Occurrences in the prospectus text")
    ax.set_title("Term frequencies in the SpaceX IPO prospectus (June 2026)")
    figs = ROOT / "paper" / "draft" / "output" / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    fig.savefig(figs / "fig_prospectus_term_frequency.pdf")
    fig.savefig(figs / "fig_prospectus_term_frequency.png")
    print("\nFigure written:", figs / "fig_prospectus_term_frequency.pdf")

    # 4) JSON for macros
    out = ROOT / "output" / "tables" / "prospectus_term_frequency.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"source": SRC.name, "chars": n_chars,
                               "concepts": counts, "top30": top30}, indent=2))
    print("Counts written:", out)


if __name__ == "__main__":
    main()
