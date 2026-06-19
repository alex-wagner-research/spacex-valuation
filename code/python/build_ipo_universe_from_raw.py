r"""
build_ipo_universe_from_raw.py -- build the objective Figure-7 IPO universe LOCALLY from the broad
SDC raw export (data/raw/sdc_ipo_pull_raw.csv, written by code/R/pull_sdc_ipo_raw.R). No WRDS needed.

THE RULE: the largest U.S. common-stock IPOs by gross proceeds, 2000-present. Selection uses only
ex-ante fields (issuer nation, security type, offer price, proceeds), never post-listing trading.

Filters (Ritter-style, matched to SDC's actual encodings as seen in the raw pull):
  * ipo flag = 'Yes'                  -- isolates the equity IPO tranche (debt rows carry ipo = NA)
  * nation  = United States           -- U.S. issuer (excludes foreign issuers listing in the U.S.,
                                         e.g. Coupang [South Korea], Alibaba [China] -- same as ADRs)
  * security is common/ordinary       -- "Common Shares", "Ordinary Shares", "Class A Shares", etc.;
                                         excludes Units, ADR/ADS, depositary shares, notes/bonds
  * offer price >= $5
  * SIC not in 6726 (closed-end fund) / 6798 (REIT) / 6770 (blank-check / SPAC)
  * issue year >= 2000

Proceeds = total gross proceeds incl. overallotment, all markets ($mil)
  = rank1_overallot_totdolamtpr, falling back to proceedsoversold then principalamount (all $mil).
Date = firstradedate (SAS serial, days since 1960-01-01); if missing, ipodate (ISO or SAS).
One deal per issuer (de-dup on the 6-digit issuer CUSIP, keeping the largest-proceeds row).

OUTPUT: data/raw/ipo_universe.csv  (label, cusip, ipo_date, offer_price, proceeds_musd) -- top N.
Then run code/R/pull_debut_panel_wrds.R to attach CRSP prices + OptionMetrics IV by CUSIP.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "sdc_ipo_pull_raw.csv"
OUT = ROOT / "data" / "raw" / "ipo_universe.csv"
TOP_N = 30
SAS_EPOCH = pd.Timestamp("1960-01-01")


def num(s):
    s = re.sub(r"[^0-9.]", "", str(s))
    try:
        return float(s) if s not in ("", ".") else np.nan
    except ValueError:
        return np.nan


def to_date(fts, ipod):
    """firstradedate is a SAS serial; ipodate may be ISO text or a SAS serial. Prefer firstradedate."""
    s = num(fts)
    if not np.isnan(s) and 10000 <= s <= 40000:
        return SAS_EPOCH + pd.Timedelta(days=int(s))
    x = str(ipod).strip()
    dt = pd.to_datetime(x, errors="coerce", format="%Y-%m-%d")
    if pd.notna(dt):
        return dt
    s2 = num(x)
    if not np.isnan(s2) and 10000 <= s2 <= 40000:
        return SAS_EPOCH + pd.Timedelta(days=int(s2))
    return pd.NaT


def main():
    d = pd.read_csv(RAW, dtype=str, keep_default_na=False)
    d["proceeds"] = (d["rank1_overallot_totdolamtpr"].map(num)
                     .fillna(d["proceedsoversold"].map(num))
                     .fillna(d["principalamount"].map(num)))
    d["offer"] = d["offerpric"].map(num)
    d["ipo_date"] = [to_date(f, i) for f, i in zip(d["firstradedate"], d["ipodate"])]
    d["yr"] = d["ipo_date"].dt.year

    sec = d["security"].str.upper()
    is_equity = ~sec.str.contains(
        r"UNIT|ADR|ADS|DEP\b|DEPOSITARY|INCOME DEP|NOTE|BOND|DEBENT|PFD|PREFERRED", regex=True, na=False)
    us = (d["nation"].str.upper().str.startswith("UNITED STATES")
          | d["nation"].str.upper().isin(["US", "USA", "U.S."]))
    # listed on a U.S. exchange (drops e.g. KKR PEI on Euronext Amsterdam). A blank/NA exchange is
    # given the benefit of the doubt -- it's missing data, not a foreign listing (e.g. Anthem 2001) --
    # since nation and CUSIP already establish a U.S. issuer; only an explicitly foreign exchange is cut.
    exch = d["exchange"].str.upper().str.strip()
    us_exch = (exch.str.contains(r"YORK|NASDAQ|AMERICAN|AMEX|NYSE", regex=True, na=False)
               | exch.isin(["", "NA", "N/A", "NONE"]))
    # a real 8-9 char U.S. CUSIP (drops foreign issuers with a missing/letter-prefixed CINS, e.g.
    # GlobalFoundries cusip9 = NA / cusip = G39387) -- also the CRSP/OptionMetrics match key
    cusip_clean = d["cusip9"].str.replace(r"\s", "", regex=True).str.upper()
    cusip_ok = cusip_clean.str.match(r"^[0-9][0-9A-Z]{7,8}$").fillna(False)
    sicp = d["sicp"].str.extract(r"(\d{3,4})")[0]
    ok_sic = ~sicp.isin(["6726", "6798", "6770"])

    keep = ((d["ipo"].str.upper() == "YES") & us & us_exch & cusip_ok & is_equity & ok_sic
            & (d["offer"] >= 5) & (d["yr"] >= 2000) & (d["proceeds"] > 0) & d["ipo_date"].notna())
    u = d[keep].copy()

    u["cusip8"] = u["cusip9"].str.replace(r"\s", "", regex=True).str.upper().str[:8]
    u["cusip6"] = u["cusip8"].str[:6]
    u = u.sort_values("proceeds", ascending=False).drop_duplicates("cusip6")   # one deal per issuer
    top = u.head(TOP_N)

    out = pd.DataFrame({
        "label": top["ninames"].str.strip(),
        "cusip": top["cusip8"],
        "ipo_date": top["ipo_date"].dt.strftime("%Y-%m-%d"),
        "offer_price": top["offer"].round(2),
        "proceeds_musd": top["proceeds"].round(1),
    })
    out.to_csv(OUT, index=False)
    print(f"Matched {len(u)} unique U.S. common-stock IPOs (2000+); wrote top {len(out)} to {OUT}\n")
    with pd.option_context("display.width", 200, "display.max_rows", None):
        print(out.to_string(index=False))


if __name__ == "__main__":
    main()
