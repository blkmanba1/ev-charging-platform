# Tariff sources for SP2 — verified handover

**Status:** the source survey is done and the artefacts are downloaded. The remaining work
(building the tariff table and costing schedules) belongs to SP2.

**Why this exists:** SP1's datasets (City of Boulder, City of Palo Alto) contain **no tariff or
price column**, so SP2 cannot populate `tariff_cny_per_kwh` / `interval_cost_cny` without an
external tariff source. Integration-contract amendment **A1** records this as a blocker.

## Downloaded artefacts

`data/raw/tariff/` (git-ignored, like every dataset). Each row was re-downloaded and its byte count
compared against the survey's figure.

| File | Bytes | SHA-256 (first 16) | What it is |
|---|---|---|---|
| `urdb-bulk-usurdb.csv.gz` | 12,218,252 | `2552c0c7b1c07481` | OpenEI Utility Rate Database, full gzip CSV, 737 columns |
| `xcel-summary-of-electric-rates-2018-01-01.pdf` | 30,169 | `116a2b35a10e4450` | Xcel Colorado "Summary of Electric Rates", all-in ToU $/kWh (winter) |
| `xcel-summation-sheet-all-rates-2023-07-01.pdf` | 88,057 | `11389748cc49cc25` | Xcel Colorado "Electric Summation Sheet, All Rates", effective 1 July 2023 |

Retrieve them from these exact URLs (spaces are `%20`-encoded; no key or account is needed):

```
https://openei.org/apps/USURDB/download/usurdb.csv.gz
https://www.xcelenergy.com/staticfiles/xe-responsive/Company/Rates%20&%20Regulations/Summary-of-Electric-Rates-1-1-2018.pdf
https://www.xcelenergy.com/staticfiles/xe-responsive/Company/Rates%20&%20Regulations/Electric_Summation_Sheet_All_Rates_07.01.23.pdf
```

## Recommended recipe — Boulder, 2018–2023

Two sources, used for different things. Neither is sufficient alone.

1. **OpenEI URDB** (bulk CSV, no API key) for the **time-of-use period mapping**:
   `energyweekdayschedule` and `energyweekendschedule` are 12×24 arrays giving the period index per
   month, weekday/weekend, and hour. Boulder's utility is **`Public Service Co of Colorado`,
   EIA id `15466`** — the utility name contains no "Xcel", so a name filter misses it.
2. **Xcel's own rate-summary PDFs** for the **all-in delivered $/kWh**, because URDB's internal
   consistency does not survive close inspection (below).
3. For **2023**, URDB has no residential ToU version at all, so the
   2023-07-01 summation sheet is the only source for that year.

### Column-name trap in the bulk CSV

URDB energy prices are **not** top-level `rate0` / `adj0` columns in the bulk file (those names come
from the JSON API's flattened form). In the CSV they are:

```
energyratestructure/period0/tier0rate      the base energy price
energyratestructure/period0/tier0adj       the adjustment
energyratestructure/period0/tier0max       tier ceiling (empty = unlimited)
```

A first probe that looked for `rate0` found nothing; this is a probe error, not missing data.
Splitting the bulk CSV on commas is also unsafe — the rate-structure fields contain embedded JSON,
so naive line counting over-reports the row count (a parse gave 58,920 records; naive line splitting
gave 166,818).

### Quantified caveat

URDB's base rate matches Xcel's filed base charge exactly across all five ToU periods, but
**base + adjustment runs about $0.0007–0.0009/kWh low** against the official all-in totals
(2018 winter on-peak: official `0.13461` vs URDB `0.1337426`). The reason is unverified. **Take the
all-in price from the Xcel PDFs** and use URDB only for the period mapping.

### Cross-check that did pass

Xcel's filed ToU definitions independently reproduce URDB's schedule arrays:

| Season | Dates |
|---|---|
| Summer | 1 June – 30 September |
| Winter | 1 October – 31 May |

| Period (weekdays, excluding holidays) | Hours (MT) |
|---|---|
| On-peak | 14:00 – 18:00 |
| Shoulder | 09:00 – 14:00 and 18:00 – 21:00; plus weekends and holidays 09:00 – 21:00 |
| Off-peak | 21:00 – 09:00 |

## Palo Alto, 2011–2020 — needs a decision

Verified: **URDB's Palo Alto coverage is frozen** — 26 records, newest `startdate` 2013-09-10, all
last updated 2015-03-26, so it covers 2011–2013 only. And Palo Alto residential **E-1 was tiered,
not time-of-use**, in the FY2021 tariff (Tier 1 `$0.140873757`, Tier 2 `$0.196093679` /kWh, 11
kWh/day break); ToU then existed on non-residential schedules (E-4 TOU, E-7 TOU). Residential
E-1-TOU exists today, which is not evidence about 2011–2020.

Historical stamped tariff sheets are reachable without an account at the City's records portal
(`https://recordsportal.paloalto.gov/WebLink/ElectronicFile.aspx?docid=6666&dbid=0&repo=PaloAlto`,
10,411,283 bytes, effective 2020-07-01), but only that one packet has been checked.

**Decision (team, 2026-09-22): cost Palo Alto charging on the tiered residential E-1 schedule and
state explicitly that time-of-use optimisation does not apply to it.** Palo Alto therefore keeps its
role as the forecast-validation site, and the ToU / peak-shifting demonstration runs on Boulder,
where a genuine ToU tariff exists for the whole 2018–2023 window. SP5's economic comparison must
report the two sites separately rather than pooling them, because one is priced on tiers and the
other on time-of-use periods.

## Licensing

- **OpenEI URDB**: the OpenEI wiki states CC0, while the `data.openei.org` JSON-LD states CC BY 4.0.
  Both are permissive; **the discrepancy is worth disclosing** in the dissertation rather than
  quoting one as fact.
- **Xcel, Palo Alto, Colorado PUC documents**: no licence stated. Treat as public regulatory
  documents: cite the source, do not redistribute the files (they are not committed anyway).

## Not verified — do not cite without checking

All Xcel summary sheets except the two downloaded; the 2024+ Salesforce-hosted links; the current
Palo Alto E-1 / E-1-TOU PDFs (only their HTML period text was read); the exact E-4 TOU dollar
figures (the extracted text was malformed and needs re-reading from the page image); whether Palo
Alto packets exist for every year 2011–2019; any Wayback fallback (the CDX API returned 504 and the
availability API 429 during the survey).

Full survey with its own verification log: `data/raw/tariff-research.md` (git-ignored).
