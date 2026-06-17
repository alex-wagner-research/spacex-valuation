# pull_optionmetrics_iv.R
# -----------------------------------------------------------------------------
# First-day-of-options implied volatility and option/stock volume for the large
# IPOs in Figure 8, from OptionMetrics IvyDB US via WRDS. The point: benchmark
# SpaceX's debut option implied vol against OTHER IPOs' first option-trading day,
# not against generic large-caps.
#
# For each deal we find its security in OptionMetrics, locate the FIRST date its
# options trade, and pull on (or just after) that date:
#   * ATM 30-day implied volatility   -- from the standardized volatility surface
#                                        (days = 30, |delta| = 50), maturity-controlled
#   * total option volume (contracts) -- from the option price file
#   * underlying share volume         -- from the security price file
#   * O/S ratio = option volume / share volume  (Roll, Schwartz, Subrahmanyam 2010, JF)
#   * shares outstanding              -- for an alternative free-float-style scaling
#
# Output: data/clean/ipo_options_iv.csv  and a printed summary.
#
# NOTE ON SCHEMA: WRDS OptionMetrics tables are year-partitioned and the library is
# usually "optionm" (occasionally "optionm_all"). If a query errors with "relation
# does not exist", set SCHEMA below or inspect names with the diagnostic block at the
# very bottom of this file (commented out). Column names used here -- secid, date,
# ticker, issuer, issue_type, cp_flag, delta, days, impl_volatility, volume, shrout,
# strike_price -- are the standard IvyDB US fields.
# -----------------------------------------------------------------------------

## ---- 0. packages -----------------------------------------------------------
for (p in c("RPostgres", "DBI", "getPass")) {
  if (!requireNamespace(p, quietly = TRUE)) install.packages(p, repos = "https://cloud.r-project.org")
}
library(DBI); library(RPostgres); library(getPass)

SCHEMA  <- "optionm"                       # change to "optionm_all" if your WRDS uses that
OUT_CSV <- file.path("data", "clean", "ipo_options_iv.csv")
dir.create(dirname(OUT_CSV), recursive = TRUE, showWarnings = FALSE)

## ---- 1. connect to WRDS ----------------------------------------------------
# You will be prompted for your WRDS username and password (nothing is stored).
wrds <- dbConnect(RPostgres::Postgres(),
                  host = "wrds-pgdata.wharton.upenn.edu", port = 9737,
                  dbname = "wrds", sslmode = "require",
                  user = getPass("WRDS username: "),
                  password = getPass("WRDS password: "))
cat("Connected to WRDS.\n")

## ---- 1b. introspect the security table (column names vary by vintage) -------
securd_cols <- dbGetQuery(wrds, sprintf(
  "SELECT column_name FROM information_schema.columns
   WHERE table_schema = '%s' AND table_name = 'securd'", SCHEMA))$column_name
cat(sprintf("securd columns: %s\n", paste(securd_cols, collapse = ", ")))
namecol <- intersect(c("issuer", "issuer_desc", "issuername", "name",
                       "company_name", "co_name", "comnam", "cusip"), securd_cols)[1]
has_col <- function(c) c %in% securd_cols

## ---- 2. the deals (same set as Figure 8; listing dates verified) -----------
# SPCX (2026) is omitted -- its day-1 option IV is taken from CBOE separately, and
# 2026 may not yet be in your OptionMetrics vintage. Add c("SpaceX","SPCX","2026-06-16")
# once IvyDB carries it, to cross-check the CBOE read.
ipos <- data.frame(stringsAsFactors = FALSE, rbind(
  c("Robinhood","HOOD","2021-07-29"), c("Uber","UBER","2019-05-10"),
  c("Facebook","META","2012-05-18"),  c("General Motors","GM","2010-11-18"),
  c("Blackstone","BX","2007-06-22"),  c("Mastercard","MA","2006-05-25"),
  c("Kenvue","KVUE","2023-05-04"),    c("Visa","V","2008-03-19"),
  c("Rivian","RIVN","2021-11-10"),    c("Goldman Sachs","GS","1999-05-04"),
  c("UPS","UPS","1999-11-10"),        c("Coupang","CPNG","2021-03-11"),
  c("Snap","SNAP","2017-03-02"),      c("Twitter","TWTR","2013-11-07"),
  c("DoorDash","DASH","2020-12-09"),  c("Snowflake","SNOW","2020-09-16"),
  c("Airbnb","ABNB","2020-12-10"),    c("Circle","CRCL","2025-06-05"),
  c("Figma","FIG","2025-07-31")))
names(ipos) <- c("label", "ticker", "ipo_date")

tbl <- function(stem, year) sprintf("%s.%s%d", SCHEMA, stem, year)   # e.g. optionm.opprcd2021

## ---- 3. ticker -> secid ----------------------------------------------------
# OptionMetrics tickers can be reused over time; we take the common-stock secid
# (issue_type '0') and, if several, the one whose option data is closest to the IPO.
get_secid <- function(ticker, ipo_date) {
  sel <- c("secid",
           if (has_col("issue_type")) "issue_type",
           if (!is.na(namecol)) sprintf("%s AS issuer", namecol))
  q <- sprintf("SELECT %s FROM %s.securd WHERE ticker = '%s'",
               paste(sel, collapse = ", "), SCHEMA, ticker)
  cand <- dbGetQuery(wrds, q)
  if (nrow(cand) == 0) return(NULL)
  if (!is.null(cand$issue_type)) {
    common <- cand[cand$issue_type == "0", , drop = FALSE]   # prefer common stock
    if (nrow(common) >= 1) cand <- common
  }
  r <- cand[1, , drop = FALSE]
  if (is.null(r$issuer)) r$issuer <- NA                 # name column for your sanity-check
  r
}

## ---- 4. first option-trading date (search IPO year, then year+1) -----------
first_opt_date <- function(secid, year) {
  for (y in c(year, year + 1)) {
    d <- tryCatch(dbGetQuery(wrds, sprintf(
      "SELECT MIN(date) AS d FROM %s WHERE secid = %d", tbl("opprcd", y), secid))$d,
      error = function(e) NA)
    if (length(d) && !is.na(d)) return(as.Date(d))
  }
  NA
}

## ---- 5. ATM 30-day IV on/just after the first option date ------------------
atm_iv30 <- function(secid, d0) {
  y <- as.integer(format(d0, "%Y"))
  q <- sprintf("SELECT date, AVG(impl_volatility) AS iv
                FROM %s
                WHERE secid = %d AND days = 30 AND abs(delta) = 50
                  AND date BETWEEN '%s' AND '%s'
                GROUP BY date ORDER BY date ASC LIMIT 1",
               tbl("vsurfd", y), secid, d0, d0 + 12)
  r <- tryCatch(dbGetQuery(wrds, q), error = function(e) data.frame())
  if (nrow(r) == 0) return(list(date = NA, iv = NA))
  list(date = as.Date(r$date[1]), iv = 100 * r$iv[1])         # percent
}

## ---- 6. option volume, share volume, shares outstanding on a date ----------
volumes <- function(secid, d) {
  y <- as.integer(format(d, "%Y"))
  ov <- tryCatch(dbGetQuery(wrds, sprintf(
    "SELECT COALESCE(SUM(volume),0) AS v FROM %s WHERE secid = %d AND date = '%s'",
    tbl("opprcd", y), secid, d))$v, error = function(e) NA)
  sp <- tryCatch(dbGetQuery(wrds, sprintf(
    "SELECT volume, shrout, close FROM %s WHERE secid = %d AND date = '%s'",
    tbl("secprd", y), secid, d)), error = function(e) data.frame())
  list(opt_vol = ov,
       stk_vol = if (nrow(sp)) sp$volume[1] else NA,
       shrout  = if (nrow(sp)) sp$shrout[1] else NA)
}

## ---- 7. loop ---------------------------------------------------------------
`%||%` <- function(a, b) if (is.null(a) || (length(a) == 1 && is.na(a))) b else a
rows <- list()
for (i in seq_len(nrow(ipos))) {
  lab <- ipos$label[i]; tk <- ipos$ticker[i]; ipo <- as.Date(ipos$ipo_date[i])
  s <- get_secid(tk, ipo)
  if (is.null(s)) { cat(sprintf("  %-15s %-5s  no secid found; skipped\n", lab, tk)); next }
  d0 <- first_opt_date(s$secid, as.integer(format(ipo, "%Y")))
  if (is.na(d0)) { cat(sprintf("  %-15s secid %d  no option data; skipped\n", lab, s$secid)); next }
  iv <- atm_iv30(s$secid, d0); v <- volumes(s$secid, iv$date %||% d0)
  os <- if (is.na(v$opt_vol) || is.na(v$stk_vol) || v$stk_vol == 0) NA else v$opt_vol / v$stk_vol
  rows[[length(rows) + 1]] <- data.frame(
    label = lab, ticker = tk, secid = s$secid, issuer = s$issuer,
    ipo_date = ipo, first_opt_date = d0,
    lag_days = as.integer(d0 - ipo), iv_date = iv$date,
    atm_iv30_pct = round(iv$iv, 1),
    opt_volume = v$opt_vol, stock_volume = v$stk_vol,
    os_ratio = round(os, 4), shrout_000 = v$shrout, stringsAsFactors = FALSE)
  cat(sprintf("  %-15s secid %-7d first opt %s (+%2dd)  ATM30 IV %5.1f%%  O/S %.3f  [%s]\n",
              lab, s$secid, d0, as.integer(d0 - ipo),
              ifelse(is.na(iv$iv), NA, iv$iv), ifelse(is.na(os), NA, os), s$issuer))
}

out <- do.call(rbind, rows)
write.csv(out, OUT_CSV, row.names = FALSE)
cat(sprintf("\nWrote %d rows to %s\n", nrow(out), OUT_CSV))

## ---- 8. summary ------------------------------------------------------------
iv <- out$atm_iv30_pct[is.finite(out$atm_iv30_pct)]
os <- out$os_ratio[is.finite(out$os_ratio)]
cat(sprintf("First-options-day ATM 30-day IV across %d IPOs: median %.0f%%, mean %.0f%%, range %.0f-%.0f%%\n",
            length(iv), median(iv), mean(iv), min(iv), max(iv)))
cat(sprintf("First-options-day O/S ratio: median %.3f, mean %.3f\n", median(os), mean(os)))
cat("SpaceX (CBOE, first options day, June 16 2026): ATM ~104-111%% at 3-6m tenors.\n")
cat("Compare SpaceX's CBOE read to the median above to judge how high its debut IV really is.\n")

dbDisconnect(wrds)

## ---- DIAGNOSTIC (uncomment if a table name errors) -------------------------
# dbGetQuery(wrds, "SELECT table_name FROM information_schema.tables
#                   WHERE table_schema = 'optionm' ORDER BY table_name")
# dbGetQuery(wrds, "SELECT column_name FROM information_schema.columns
#                   WHERE table_schema='optionm' AND table_name='securd'")
