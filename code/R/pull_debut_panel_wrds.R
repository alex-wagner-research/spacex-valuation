# pull_debut_panel_wrds.R
# -----------------------------------------------------------------------------
# Build the Figure-7 ("debut panel") comparison set on an OBJECTIVE, EX-ANTE rule,
# and pull every series from authoritative WRDS sources (CRSP + OptionMetrics).
#
# THE RULE (replaces the old curated list). SpaceX is the largest IPO on record, so the
# natural peer set is defined by SIZE, which is fixed at the offer and does not depend on how
# the stock then traded:
#
#     "The largest U.S. common-stock IPOs by gross proceeds, 2000-present, that subsequently
#      had listed options."
#
# Size (proceeds = offer price x shares offered) is ex ante; first-day return, continuation, and
# implied volatility play no part in selection. Include ALL deals that qualify; drop a deal only
# for genuine data unavailability (e.g. options not yet in the OptionMetrics vintage), and report
# the drop. The 2000 start keeps the whole set inside OptionMetrics coverage (IvyDB begins 1996).
#
# THE UNIVERSE FILE. This script does NOT pick the deals; it reads them from
#   data/raw/ipo_universe.csv   with columns:  label, cusip, ipo_date, offer_price, proceeds_musd
# Build that file from a single objective source you can cite -- e.g. SDC Platinum New Issues
# (U.S., common stock, operating company, ordered by principal amount, with the usual IPO-sample
# exclusions: no SPACs, REITs, closed-end funds, unit offers, ADRs/foreign issuers), or Capital IQ
# offerings, or Jay Ritter's IPO database. Take the top N by proceeds; do not edit the list by hand.
# (cusip = 8-character CUSIP, the CRSP/OptionMetrics key.)
#
# WHAT THIS RECOVERS. Drawing prices from CRSP (not Yahoo) recovers delisted names such as Twitter,
# whose post-IPO closes Yahoo no longer serves. Mapping options by CUSIP (not the reused ticker)
# fixes Visa's implied volatility. A 2025 name (e.g. Circle) appears once it enters your
# OptionMetrics vintage; until then it is reported as "options data not yet available."
#
# OUTPUT: data/clean/ipo_debut_panel.csv  -- one row per deal:
#   label, cusip, permno, secid, ipo_date, first_close, day3_close, day5_close, first_day_ret_pct,
#   cont2_pct, cont3_pct, cont5_pct, first_opt_date, atm_iv30_pct
# Continuation is the return from the first close to the 2nd / 3rd / 5th daily close; Figure 7's
# panel (b) uses the 5-session (first-trading-week) window, with 2 and 3 sessions for robustness.
# Then rerun 12_fig_debut_panel.py (which will read this single file) to redraw Figure 7.
#
# SCHEMA NOTE: if a table/column name errors, your WRDS vintage differs; the diagnostic block at
# the bottom lists available columns. Standard libraries used: crsp (dsf, dsenames/stocknames),
# optionm (securd, vsurfd{yyyy}, opprcd{yyyy}).
# -----------------------------------------------------------------------------

for (p in c("RPostgres", "DBI", "getPass")) {
  if (!requireNamespace(p, quietly = TRUE)) install.packages(p, repos = "https://cloud.r-project.org")
}
library(DBI); library(RPostgres); library(getPass)

OPTIONM <- "optionm"                        # change to "optionm_all" if your WRDS uses that
UNIV    <- file.path("data", "raw", "ipo_universe.csv")
OUT     <- file.path("data", "clean", "ipo_debut_panel.csv")
dir.create(dirname(OUT), recursive = TRUE, showWarnings = FALSE)

if (!file.exists(UNIV))
  stop(sprintf("Provide %s first (label, cusip, ipo_date, offer_price, proceeds_musd). See header.", UNIV))
ipos <- read.csv(UNIV, stringsAsFactors = FALSE, colClasses = c(cusip = "character"))
ipos <- ipos[order(-ipos$proceeds_musd), ]   # largest first; objective order

wrds <- dbConnect(RPostgres::Postgres(),
                  host = "wrds-pgdata.wharton.upenn.edu", port = 9737,
                  dbname = "wrds", sslmode = "require",
                  user = getPass("WRDS username: "), password = getPass("WRDS password: "))
cat(sprintf("Connected. Universe: %d deals (objective: largest U.S. IPOs by proceeds).\n", nrow(ipos)))

## ---- CRSP: permno from CUSIP, then the first three daily closes from the IPO date -----------
crsp_prices <- function(cusip8, ipo) {
  pm <- dbGetQuery(wrds, sprintf(
    "SELECT permno FROM crsp.stocknames WHERE ncusip = '%s' LIMIT 1", substr(cusip8, 1, 8)))$permno
  if (!length(pm)) return(NULL)
  px <- dbGetQuery(wrds, sprintf(
    "SELECT date, ABS(prc) AS prc FROM crsp.dsf
     WHERE permno = %d AND date >= '%s' ORDER BY date ASC LIMIT 6", pm[1], ipo))
  if (nrow(px) < 3) return(NULL)
  g <- function(k) if (nrow(px) >= k) px$prc[k] else NA    # kth daily close, NA if not yet traded
  list(permno = pm[1], c1 = px$prc[1], c2 = g(2), c3 = g(3), c5 = g(5))
}

## ---- OptionMetrics: secid from CUSIP, first option date, ATM 30-day implied vol -------------
om_iv <- function(cusip8) {
  s <- dbGetQuery(wrds, sprintf(
    "SELECT secid FROM %s.securd WHERE cusip = '%s' LIMIT 1", OPTIONM, cusip8))$secid
  if (!length(s)) return(list(secid = NA, d0 = NA, iv = NA))
  d0 <- NA
  for (y in 1996:2026) {
    d <- tryCatch(dbGetQuery(wrds, sprintf(
      "SELECT MIN(date) AS d FROM %s.opprcd%d WHERE secid = %d", OPTIONM, y, s[1]))$d,
      error = function(e) NA)
    if (length(d) && !is.na(d)) { d0 <- as.Date(d); break }
  }
  if (is.na(d0)) return(list(secid = s[1], d0 = NA, iv = NA))
  yr <- as.integer(format(d0, "%Y"))
  r <- tryCatch(dbGetQuery(wrds, sprintf(
    "SELECT AVG(impl_volatility) AS iv FROM %s.vsurfd%d
     WHERE secid = %d AND days = 30 AND abs(delta) = 50 AND date BETWEEN '%s' AND '%s'",
    OPTIONM, yr, s[1], d0, d0 + 12)), error = function(e) data.frame(iv = NA))
  list(secid = s[1], d0 = d0, iv = if (nrow(r)) 100 * r$iv[1] else NA)
}

## ---- loop ----------------------------------------------------------------------------------
rows <- list()
for (i in seq_len(nrow(ipos))) {
  lab <- ipos$label[i]; cu <- ipos$cusip[i]; ipo <- as.Date(ipos$ipo_date[i]); off <- ipos$offer_price[i]
  pr <- crsp_prices(cu, ipo)
  iv <- om_iv(cu)
  if (is.null(pr)) { cat(sprintf("  %-26s no CRSP prices; dropped\n", lab)); next }
  fdr   <- 100 * (pr$c1 / off - 1)
  pct   <- function(ck) if (!is.na(ck)) 100 * (ck / pr$c1 - 1) else NA   # continuation to kth close
  cont2 <- pct(pr$c2); cont3 <- pct(pr$c3); cont5 <- pct(pr$c5)
  rows[[length(rows) + 1]] <- data.frame(
    label = lab, cusip = cu, permno = pr$permno, secid = iv$secid, ipo_date = ipo,
    first_close = round(pr$c1, 4), day3_close = round(pr$c3, 4), day5_close = round(pr$c5, 4),
    first_day_ret_pct = round(fdr, 1), cont2_pct = round(cont2, 1), cont3_pct = round(cont3, 1),
    cont5_pct = round(cont5, 1), first_opt_date = iv$d0, atm_iv30_pct = round(iv$iv, 1),
    stringsAsFactors = FALSE)
  cat(sprintf("  %-26s ret %+5.1f%%  cont3 %+5.1f%%  cont5 %s  IV %s\n", lab, fdr, cont3,
              ifelse(is.na(cont5), "  n/a", sprintf("%+5.1f%%", cont5)),
              ifelse(is.na(iv$iv), "n/a (no options in vintage)", sprintf("%.0f%%", iv$iv))))
}
out <- do.call(rbind, rows)
write.csv(out, OUT, row.names = FALSE)
cat(sprintf("\nWrote %d deals to %s. Deals with IV n/a keep their return/continuation; the figure\n", nrow(out), OUT))
cat("drops only the implied-vol marker for those, and notes it.\n")
dbDisconnect(wrds)

## ---- DIAGNOSTIC (uncomment if a table/column errors) ---------------------------------------
# dbGetQuery(wrds, "SELECT column_name FROM information_schema.columns
#                   WHERE table_schema='crsp' AND table_name='stocknames'")
# dbGetQuery(wrds, "SELECT table_name FROM information_schema.tables WHERE table_schema='optionm'")
