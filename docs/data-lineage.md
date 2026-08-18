# Data Lineage

Where the data came from, what was done to it, what is missing, and why.

---

## Provenance chain

```
US DOT · Bureau of Transportation Statistics
  On-Time Performance, calendar year 2015
        │
        ▼
Kaggle · usdot/flight-delays  (CC0 / public domain)
  flights.csv    5,819,079 rows · all US domestic flights
  airlines.csv          14 rows
  airports.csv         322 rows
        │
        │  FILTER: ORIGIN_AIRPORT ∈ {ATL, ORD, DFW, DEN, LAX,
        │                            SFO, PHX, IAH, LAS, MSP}
        ▼
data/raw/flights.csv          1,949,742 rows  (~290 MB)
data/reference/airports.csv          10 rows  (the ten hubs only)
        │
        │  scripts/make_sample.py  — stratified, seed 42
        ▼
data/sample/flights_sample.csv   ~50,000 rows  (~8 MB, committed)
```

**Evidence for the filtering step:** the delivered `flights.csv` carries an
unnamed leading index column whose values run `1 .. 5,819,074`. That range is
the row count of the *full* upstream file, not of this subset — proof that this
file is a filtered slice rather than an independent extract. The index column is
dropped in Power Query (`RemovedIndex`) and by `flight_rules.load_flights()`.

---

## Transformations applied

Every step is in `src/powerquery/m-scripts.pq`, Query 4, in this order.

| # | Step | Effect |
|---|---|---|
| 1 | Drop ghost index column | Removed before header promotion — promoting first would leave a column with an empty name that cannot be referenced |
| 2 | Set data types | 31 columns; numerics arrive as `"2.0"` and are parsed to `Int64` |
| 3 | Build `Flight Date` | From `YEAR` + `MONTH` + `DAY` |
| 4 | HHMM → `time` | Six columns; `2400` mapped to `00:00` (2400 is not a valid time) |
| 5 | `Departure Hour` | Derived from `SCHEDULED_DEPARTURE`, null-guarded |
| 6 | `CANCELLATION_REASON` null → `"N"` | Completes the dimension relationship |
| 7 | `Flight Status` | **The single classification rule.** `>= 15` per US DOT |
| 8 | `Delay Band` | Boundaries match labels exactly |
| 9 | `Delay Recovery` | `DEPARTURE_DELAY − ARRIVAL_DELAY`, null if either is null |
| 10 | `Distance Band` | Exactly 1500 miles falls into Long Haul |
| 11 | Drop `YEAR`/`MONTH`/`DAY`/`DAY_OF_WEEK` | Redundant once the date dimension exists |
| 12 | Drop 7 unconsumed columns | Largest VertiPaq saving in the model |

### What was deliberately NOT done

**The NULLs in the five delay-reason columns were not filled.** They are
structural — populated only when `ARRIVAL_DELAY >= 15`, on 390,262 of 1,949,742
rows (79.98% null). Zero-filling makes every `AVERAGE()`-based attribution
measure divide by 1.9M instead of 390k and understates each cause by roughly a
factor of five. This is the single most consequential decision in the pipeline.

**Fact-table columns were not renamed.** `src/dax/measures.dax` binds to the raw
physical names. Renaming them in Power Query breaks every measure silently at
refresh. Friendly labels belong in Model view display names.

---

## Known gaps

### October 2015 — zero rows

**Status: CONFIRMED against the full upstream file, 2026-08-16.**

October 2015 encodes `ORIGIN_AIRPORT` and `DESTINATION_AIRPORT` as **five-digit
numeric DOT identifiers** instead of three-letter IATA codes. Every other month
uses IATA. This is a
[documented quirk](https://www.kaggle.com/code/smiller933/fixing-airport-codes)
of the dataset, and it is present in this project's source file.

Direct evidence, read from the upstream `flights.csv`:

```
2015,9,1,2,NK,298,N624NK,LAS,IAH,...        ← September: IATA
2015,10,1,4,AA,1230,N3DBAA,14747,11298,...  ← October:  numeric DOT
2015,10,1,4,DL,1805,N696DL,14771,13487,...  ← October:  numeric DOT
2015,11,1,7,NK,612,N602NK,LAS,MSP,...       ← November: IATA
```

The numeric values are BTS airport IDs from the master coordinate table —
`14747` is Seattle, `11298` Dallas/Fort Worth, `14771` San Francisco.

**Therefore the gap is a filtering artefact of this project, not missing source
data.** The extract was built by filtering `ORIGIN_AIRPORT` to ten IATA codes.
No October row could match a three-letter code, so the entire month was dropped
without warning or error.

| Framing | Accurate? |
|---|---|
| "October is missing from the source" | **No.** October is present upstream, fully populated |
| "October was dropped by our filter" | **Yes.** Our decision, recoverable, now documented |

#### How to recover October — deferred to v2.0, deliberately

1. Download the BTS master coordinate table (DOT ID → IATA mapping), or derive it
   from the months that use IATA by joining on carrier, flight number and date
2. Map `ORIGIN_AIRPORT` and `DESTINATION_AIRPORT` before filtering
3. Re-extract, then re-run `validate_dataset.py`

**Do not do this before publishing v1.0.** Recovering October changes the row
count from 1,949,742 to roughly 2.1M, which invalidates *every* baseline in this
repository — all 45 assertions, the dashboard, the model, the README. That is a
major version, not a patch. Publish the documented limitation first.

**Downstream consequences, already handled:**

- `Flights MoM %` and `On Time % MoM (pp)` guard both periods for blank
- `[Is Comparable Period]` filters October out of time-series visuals
- `'Date Table'[Has Flight Data]` flags it, derived from the data rather than
  hardcoded to month 10
- The date dimension remains gap-free (365 days) — required for correct time
  intelligence even when the fact table has holes

### Hours 03 and 04 — zero flights

Not a gap. No flights are scheduled to depart from these ten hubs between 03:00
and 04:59. `Departure Hour` therefore has **22 distinct values, not 24**.

The reporting consequence is real: a categorical X-axis silently omits both
hours and makes the overnight trough look continuous. Use a continuous axis, or
build a 24-row hour dimension and left-join to it.

### Destination airports — 273 values, 10 covered

`airports.csv` as delivered covers only the ten origin hubs, so
`DESTINATION_AIRPORT` has no dimension and renders as a raw IATA code. Visible
in the routes table as "Los Angeles → JFK". See `docs/model-design.md` for the
v1.1 fix.

---

## Rule ownership — where each definition lives

A rule written twice will diverge. This is exactly how v1 came to publish two
different on-time counts. Each rule below has exactly one home per runtime:

| Rule | Power BI | Python |
|---|---|---|
| Flight classification | `Flights[Flight Status]` (M, Query 4 step 7) | `flight_rules.flight_status()` |
| Delay band | `Flights[Delay Band]` | `flight_rules.delay_band()` |
| Distance band | `Flights[Distance Band]` | `flight_rules.distance_band()` |
| On-time %, both bases | `measures.dax` folder 02 | `flight_rules.on_time_pct_*()` |
| Published baselines | comments in `measures.dax` | `flight_rules.BASELINES` |

`build_dashboard.py`, `validate_dataset.py` and `make_sample.py` all import from
`flight_rules.py`. **None of them reimplements a rule.** The two runtimes are
kept honest against each other by asserting both against the same baselines.

---

## Refresh and retention

- **Refresh cadence: none.** This is a static 2015 archive. It will never
  receive new rows.
- **Incremental refresh: not enabled, by design.** A CSV source cannot fold, so
  `RangeStart`/`RangeEnd` would cost a full file read and buy nothing. See the
  options table at the bottom of `m-scripts.pq`.
- **Retention:** `data/raw/` is reproducible from the Kaggle source at any time;
  it is not backed up and does not need to be. The sample and the three
  reference CSVs are in git, which is the backup.
- **Versioning:** tag `v1.0` at publication. OneDrive sync is not version
  control — it protects against disk loss, not against a bad edit.

## Sources

- [2015 Flight Delays and Cancellations — Kaggle / US DOT](https://www.kaggle.com/datasets/usdot/flight-delays)
- [Fixing airport codes — the mixed IATA/numeric encoding](https://www.kaggle.com/code/smiller933/fixing-airport-codes)
