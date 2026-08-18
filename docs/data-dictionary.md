# Data Dictionary

Every column in the model: source, type, nullability, meaning, and the traps.
Nullability and cardinality figures are from the 1,949,742-row fact table.

---

## `Flights` — fact table, 1,949,742 rows

### Keys and dimensions

| Column | Type | Null | Distinct | Notes |
|---|---|---|---|---|
| `Flight Date` | date | 0 | 334 | Derived from `YEAR`+`MONTH`+`DAY`. Relates to `'Date Table'[Date]`. 334 not 365 — October is absent. |
| `AIRLINE` | text | 0 | 14 | IATA carrier **code**. Relates to `airlines[IATA_CODE]`. |
| `ORIGIN_AIRPORT` | text | 0 | 10 | IATA code. Relates to `airports[IATA_CODE]`. |
| `DESTINATION_AIRPORT` | text | 0 | 273 | **No relationship.** Only 10 of 273 exist in `airports.csv`. Renders as a raw code in the report. |
| `CANCELLATION_REASON` | text | 0 | 5 | Nulls replaced with `"N"` in Power Query so the relationship is total. Relates to `cancellation_codes[CANCELLATION_REASON]`. |

### Measured facts

| Column | Type | Null | Notes |
|---|---|---|---|
| `DEPARTURE_DELAY` | int | ~28,570 | Minutes. Negative = departed early. Null on cancelled flights. |
| `ARRIVAL_DELAY` | int | 33,576 | Minutes. Negative = arrived early. **Null on all cancelled and diverted flights** — 28,570 + 5,006. This is why `[Completed Flights]` exists. |
| `DISTANCE` | int | 0 | Statute miles. Range 31–4,983. |
| `TAXI_OUT` / `TAXI_IN` | int | small | Minutes on the ground. |
| `SCHEDULED_TIME` / `ELAPSED_TIME` / `AIR_TIME` | int | varies | Minutes. |
| `DIVERTED` | int | 0 | 0/1 flag. Sums to 5,006. |
| `CANCELLED` | int | 0 | 0/1 flag. Sums to 28,570. |

### Delay attribution — the five reason columns

| Column | Type | Null | Total minutes | Share |
|---|---|---|---:|---:|
| `AIR_SYSTEM_DELAY` | int | 79.98% | 4,696,308 | 21.1% |
| `SECURITY_DELAY` | int | 79.98% | 25,717 | 0.1% |
| `AIRLINE_DELAY` | int | 79.98% | 7,542,717 | 33.8% |
| `LATE_AIRCRAFT_DELAY` | int | 79.98% | 8,709,198 | 39.1% |
| `WEATHER_DELAY` | int | 79.98% | 1,328,155 | 6.0% |

**The single most important rule in this project:** these NULLs are *structural*,
not missing. They are populated only when `ARRIVAL_DELAY >= 15` — exactly 390,262
rows. **Do not replace them with 0.** Doing so makes every `AVERAGE()`-based
attribution measure divide by 1,949,742 instead of 390,262 and understates each
cause by roughly a factor of five.

On the 390,262 populated rows the five columns sum exactly to `ARRIVAL_DELAY`.
`scripts/validate_dataset.py` asserts this row-by-row rather than taking it on
trust.

### Derived columns (created in Power Query)

| Column | Type | Rule |
|---|---|---|
| `Flight Status` | text | `Cancelled` → `Diverted` → `ARRIVAL_DELAY >= 15` = `Delayed` → else `On Time`. **The `>=` is load-bearing: 14,206 flights arrived at exactly 15 minutes.** |
| `Delay Band` | text | `N/A` (null) / `On Time (<15)` / `Minor (15–45)` / `Major (46–120)` / `Severe (>120)` |
| `Delay Recovery` | int | `DEPARTURE_DELAY − ARRIVAL_DELAY`. Positive = minutes made up in the air. Null if either input is null. |
| `Distance Band` | text | `Short (<500)` / `Medium (500–1499)` / `Long (>=1500)`. Note the boundary: exactly 1500 is Long Haul. |
| `Departure Hour` | int | `Time.Hour(SCHEDULED_DEPARTURE)`, 0–23. **22 distinct values, not 24** — hours 03 and 04 have zero flights. |

### Columns dropped from the model

| Column | Why |
|---|---|
| `YEAR` | Constant (2015). Lives in `'Date Table'`. |
| `MONTH`, `DAY`, `DAY_OF_WEEK` | Fully derivable from `Flight Date` via the date dimension. |
| `TAIL_NUMBER` | ~4,900 distinct text values; no visual consumes it. Pure dictionary cost. Restore it if you add fleet-utilisation analysis. |
| `FLIGHT_NUMBER` | ~6,900 distinct; no visual consumes it. |
| `DEPARTURE_TIME`, `ARRIVAL_TIME`, `WHEELS_OFF`, `WHEELS_ON`, `SCHEDULED_ARRIVAL` | Five of the six `time` columns are unused. `SCHEDULED_DEPARTURE` is retained because it feeds `Departure Hour`. |

Dropping these seven columns is the largest single VertiPaq saving available in
the model. Measure the before/after with DAX Studio → View Metrics rather than
estimating.

---

## `airlines` — dimension, 14 rows

| Column | Type | Notes |
|---|---|---|
| `IATA_CODE` | text | Two-letter carrier code. Primary key. Joins to `flights[AIRLINE]`. |
| `AIRLINE` | text | Full legal name, e.g. `"United Air Lines Inc."` |

**The trap:** `airlines[AIRLINE]` is the full name; `flights[AIRLINE]` is the
code. Same column name, two different things, in a related pair of tables.
Always qualify the table in DAX. For a chart axis you almost always want
`airlines[AIRLINE]`.

**No short-name column, deliberately.** If you ever add one, use an explicit
14-row lookup — not chained `Text.Replace` on the suffixes. Stripping `" Inc."`,
`" Co."` and `" Airlines"` in sequence produces an inconsistent axis, because
three carriers spell it "Air Lines" as two words and the suffix survives for
them: `American`, but `United Air Lines`, `Delta Air Lines`, `Southwest`.
For most purposes you do not need a column at all — set a display name on
`AIRLINE` in Model view and leave the data alone.

`EV` is labelled "Atlantic Southeast" in the source; in 2015 the code was
operated by ExpressJet post-merger. Either label is defensible — what matters is
that the choice is written down.

## `airports` — dimension, 10 rows

| Column | Type | Notes |
|---|---|---|
| `IATA_CODE` | text | Primary key. Joins to `flights[ORIGIN_AIRPORT]`. |
| `AIRPORT` | text | Full airport name. |
| `CITY`, `STATE`, `COUNTRY` | text | Set `STATE` → Data category: *State or Province*. |
| `LATITUDE`, `LONGITUDE` | decimal | **Set the data categories.** Without them, map visuals geocode by name and can plot a US airport on the wrong continent. |

## `cancellation_codes` — dimension, 5 rows

| Code | Reason | Cancelled flights |
|---|---|---:|
| A | Airline / Carrier | 8,084 |
| B | Weather | 16,372 |
| C | National Air System | 4,112 |
| D | Security | 2 |
| N | Not Cancelled | 1,921,172 |

Columns: `CANCELLATION_REASON` holds the **code** (A/B/C/D/N),
`CANCELLATION_DESCRIPTION` holds the text. The name says "reason" but carries
the code — a quirk of the source file, kept as-is. Set a display name of
"Cancellation Code" in Model view if it confuses report readers.

`N` does not exist in the source file; it is added in Power Query. Without it,
98.5% of fact rows resolve to a `(Blank)` member in every slicer and legend.
Adding the member is the correct fix — hiding the blank in the visual is not.

## `Date Table` — dimension, 365 rows

Continuous calendar for all of 2015, including October. A gap-free date table is
required for correct time intelligence even when the fact table has holes.

| Column | Notes |
|---|---|
| `Date` | Primary key. Mark as Date Table on this column. |
| `Month Number`, `Month Name`, `Month Short`, `Year Month`, `Quarter` | Sort `Month Name` by `Month Number`. |
| `Day`, `Day Name`, `Day Short`, `ISO Weekday` | **ISO: 1 = Monday.** The source `DAY_OF_WEEK` uses the same convention; Power BI's default `WEEKDAY()` starts at Sunday = 1. Mixing them shifts every day-of-week chart by one position. Sort `Day Name` by `ISO Weekday`. |
| `Week of Year`, `Is Weekend`, `Season` | |
| `Has Flight Data` | `Has Data` / `No Data`, derived from the fact table rather than hardcoded to month 10 — so it self-corrects if the extract is ever repaired. |

**Not yet present, recommended for v1.1:** a US federal holiday flag.
Thanksgiving, Christmas and July 4th drive a large share of the delay variance
here. A holiday flag turns "December is bad" into "the eight days around
Christmas are bad", which is a staffing decision rather than a seasonal shrug.
