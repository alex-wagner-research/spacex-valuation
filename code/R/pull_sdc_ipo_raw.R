# pull_sdc_ipo_raw.R
# -----------------------------------------------------------------------------
# Broad, ONE-TIME raw export of U.S. common-stock IPOs (2000+) from SDC New Issues on WRDS, with
# EVERY candidate proceeds/identifier/filter field, written to data/raw/sdc_ipo_pull_raw.csv. The
# final objective universe (largest by proceeds) is then built LOCALLY from this file by
# build_ipo_universe_from_raw.py -- no further WRDS round-trips, and we can inspect names directly.
#
# To be safe, the known mega-IPOs are force-included by name (so no filter can silently drop Visa,
# GM, Facebook, Rivian, ...), and the deal-size ordering uses the GREATEST of several proceeds
# fields so a deal is never cut just because one field is null. Read-only.
#
# Run:  Rscript code/R/pull_sdc_ipo_raw.R     (prompts for WRDS credentials)
# -----------------------------------------------------------------------------
for (p in c("RPostgres","DBI","getPass")) if (!requireNamespace(p, quietly=TRUE)) install.packages(p, repos="https://cloud.r-project.org")
library(DBI); library(RPostgres); library(getPass)

SCHEMA <- "sdc"; TABLE <- "wrds_ni_details"
OUT    <- file.path("data", "raw", "sdc_ipo_pull_raw.csv")
LIMIT  <- 6000
dir.create(dirname(OUT), recursive = TRUE, showWarnings = FALSE)

wrds <- dbConnect(RPostgres::Postgres(), host="wrds-pgdata.wharton.upenn.edu", port=9737,
                  dbname="wrds", sslmode="require",
                  user=getPass("WRDS username: "), password=getPass("WRDS password: "))
cat("Connected to WRDS.\n")

# clean-and-cast a text column to numeric (SDC numbers arrive as text)
num <- function(c) sprintf("NULLIF(regexp_replace(%s::text, '[^0-9.]', '', 'g'), '')::numeric", c)

cols <- c("ninames","cusip9","cusip","firstradedate","ipodate","offerpric","ipo","listipo",
          "nation","security","sicp","sicdesc","exchange","year",
          "rank1_overallot_totdolamtpr","proceedsoversold","principalamount","totdolamt",
          "totdolamtfiled","totgrossmil","gross","primaryshares","seconshares","shares")

# date cutoff on the SAS serial (>=14610 ~ 2000-01-01); keep it loose, refine in Python
date_ok  <- sprintf("%s >= 14610", num("firstradedate"))
us       <- "(UPPER(nation) LIKE 'UNITED STATES%' OR UPPER(nation) IN ('US','USA','U.S.'))"
common   <- "(UPPER(security) LIKE '%COM%' OR UPPER(security) LIKE '%ORD%')"
priced   <- sprintf("%s >= 5", num("offerpric"))
broad    <- sprintf("(%s AND %s AND %s AND %s)", date_ok, us, common, priced)

# force-include known mega-IPOs by name regardless of the broad filters, for inspection
names_like <- c("VISA","GENERAL MOTORS","FACEBOOK","META PLATFORM","RIVIAN","SNAP INC","SNAP ",
                "MASTERCARD","AIRBNB","COUPANG","SNOWFLAKE","DOORDASH","UBER","KENVUE","CORE WEAVE","COREWEAVE")
named <- paste(sprintf("UPPER(ninames) LIKE '%%%s%%'", names_like), collapse=" OR ")

order_by <- sprintf("GREATEST(COALESCE(%s,0), COALESCE(%s,0), COALESCE(%s,0), COALESCE(%s,0))",
                    num("rank1_overallot_totdolamtpr"), num("proceedsoversold"),
                    num("principalamount"), num("totdolamt"))

q <- sprintf("SELECT %s FROM %s.%s WHERE %s OR (%s) ORDER BY %s DESC LIMIT %d",
             paste(cols, collapse=", "), SCHEMA, TABLE, broad, named, order_by, LIMIT)
cat("\nQuery:\n", q, "\n\n", sep="")

d <- dbGetQuery(wrds, q)
write.csv(d, OUT, row.names = FALSE)
cat(sprintf("Wrote %d rows x %d cols to %s\n", nrow(d), ncol(d), OUT))
cat("Now build the universe locally with build_ipo_universe_from_raw.py.\n")
dbDisconnect(wrds)
