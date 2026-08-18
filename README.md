# Flight Operations Intelligence — US Domestic Aviation 2015

End-to-end Power BI analytics project over 1,949,742 US domestic flights across
the ten busiest origin hubs. Covers the full pipeline: raw CSV ingestion, Power
Query cleaning, star-schema modelling, a 58-measure DAX library, an executive
report, and a reproducible validation harness.

**Headline finding:** 72.9% of all attributed delay minutes originate inside the
airline's own operation — its own delays plus the knock-on effect of aircraft
arriving late from a previous leg. Weather accounts for only 6.0% of delay
minutes. Delay is an operational and scheduling problem in this dataset, not a
weather problem.

---

## Contents

| Path | What it is |
|---|---|
| `src/powerquery/m-scripts.pq` | All five Power Query / M queries, parameterised |
| `src/dax/measures.dax` | 58 DAX measures in 9 display folders |
| `src/dax/deploy_measures.csx` | Tabular Editor script — creates all 58 in one run |
| `scripts/flight_rules.py` | **Single Python definition of every business rule and baseline** |
| `scripts/validate_dataset.py` | Recomputes every published figure and asserts it |
| `scripts/build_dashboard.py` | Regenerates the HTML dashboard; refuses to write on a failed assertion |
| `scripts/make_sample.py` | Builds a committable stratified sample |
| `docs/data-dictionary.md` | Every column: type, nullability, meaning, gotchas |
| `docs/kpi-definitions.md` | Business definition and denominator for every KPI |
| `docs/data-lineage.md` | Provenance, filtering, known gaps and their causes |
| `docs/model-design.md` | Schema decisions, storage, security posture, upgrade path |
| `docs/rebuild-guide.md` | Rebuild everything from a clean clone in ~40 minutes |
| `CHANGELOG.md` | What changed in v1.0 and why |
| `reports/` | The HTML dashboard — regenerate with `build_dashboard.py` |
| `data/reference/` | The three small dimension CSVs (committed) |
| `data/raw/` | **Not committed.** flights.csv lives here — see below |

### One rule, one place

Every business rule — the on-time threshold, the delay bands, both on-time
denominators, the published baselines — is defined exactly once per runtime:
in `Flights[Flight Status]` for the model, and in `scripts/flight_rules.py` for
everything in Python. The three other scripts import from it and none of them
reimplements a rule.

This is deliberate. The one defect in this project's history that reached a
published artefact was caused by a classification rule that existed in two
places and drifted apart. See [`CHANGELOG.md`](CHANGELOG.md).

---

## Getting the data

`flights.csv` is approximately **290 MB**. GitHub warns above 50 MB and hard-
blocks pushes above 100 MB, so it is deliberately **not** in this repository and
is listed in `.gitignore`.

1. Download the source dataset: **[2015 Flight Delays and Cancellations](https://www.kaggle.com/datasets/usdot/flight-delays)**
   (US DOT Bureau of Transportation Statistics, licensed **CC0 / public domain**).
2. Filter `flights.csv` to the ten origin airports listed in
   `data/reference/airports.csv`.
3. Place the result at `data/raw/flights.csv`.
4. Verify it:

```bash
pip install pandas
python scripts/validate_dataset.py --data data/raw
```

The script exits `0` only when all 40+ assertions pass. If it exits `1`, the
numbers in this README do not describe the file you are holding — do not build
on it.

### The committed sample

`data/sample/flights_sample.csv` — **50,086 rows, 6.0 MB**, committed so the
model can be opened and explored without the 290 MB download. Built by
`scripts/make_sample.py`, stratified on month × airline × status with seed 42.

Measured fidelity against the full dataset:

| | Full | Sample |
|---|---:|---:|
| Airlines | 14 | **14** |
| Origin airports | 10 | **10** |
| Months | 11 | **11** |
| Cancellation codes | 4 | **4** |
| On-time % (completed) | 79.63% | **79.63%** |
| On-time % (scheduled) | 78.26% | **78.12%** |

Every category survives — including cancellation code `D`, which has 2 rows in
1.9M and which proportional sampling would have dropped.

The scheduled-basis rate drifts 0.14pp low, and the reason is worth stating
rather than hiding: the stratifier rounds every stratum up to at least one row,
which slightly over-represents small groups, and cancelled flights sit in many
small groups. The operational KPI is unaffected. **Use the sample to explore
structure, not to quote figures** — for numbers, run `validate_dataset.py`
against the full file.

---

## Scope and coverage

| Dimension | Value |
|---|---|
| Rows (fact) | 1,949,742 |
| Period | Jan–Dec 2015, **October absent** (see below) |
| Origin airports | 10 (ATL, ORD, DFW, DEN, LAX, SFO, PHX, IAH, LAS, MSP) |
| Destination airports | 273 (no dimension table — see *Known limitations*) |
| Airlines | 14 |
| Source | US DOT BTS On-Time Performance, via Kaggle |
| Personal data | **None.** No passenger, crew or contact data of any kind. |

### The October 2015 gap — confirmed cause

October contains **zero rows**, and the reason is now verified against the full
upstream file rather than assumed.

October 2015 encodes airport columns as **five-digit numeric DOT identifiers**
instead of three-letter IATA codes. Every other month uses IATA:

```
2015,9,1,2,NK,298,N624NK,LAS,IAH,...        ← September: IATA
2015,10,1,4,AA,1230,N3DBAA,14747,11298,...  ← October:  numeric
2015,11,1,7,NK,612,N602NK,LAS,MSP,...       ← November: IATA
```

This extract was built by filtering `ORIGIN_AIRPORT` to ten IATA codes, so no
October row could match and the whole month was dropped without warning.

**The gap is an artefact of our own filtering, not missing source data.**
October is fully present upstream. Recovery requires mapping DOT IDs to IATA
before filtering — deferred to v2.0 because it changes the row count to ~2.1M
and invalidates every baseline in this repository. See
[`docs/data-lineage.md`](docs/data-lineage.md).

**Consequence for the report:** every month-over-month measure will show a false
-100% collapse in October. The model ships an `[Is Comparable Period]` guard
measure and a `'Date Table'[Has Flight Data]` flag; apply one of them to every
time-series visual.

---

## The two on-time rates

This is the most important thing to understand before reading any number in this
project. There are **two** legitimate on-time rates and they differ by 1.3
percentage points:

| KPI | Formula | Value | Answers |
|---|---|---|---|
| `On Time % (Completed)` | on-time ÷ (total − cancelled − diverted) | **79.6%** | "Of flights we operated, how many landed on time?" |
| `On Time % (Scheduled)` | on-time ÷ total | **78.3%** | "Of flights a passenger could book, how many arrived on time?" |

Use **Completed** for operational performance. Use **Scheduled** when comparing
carriers — otherwise an airline can improve its score by cancelling its weakest
flights.

Both are defined in `src/dax/measures_CORRECTED.dax` under those exact names.
Never publish a measure called simply "On Time %".

### On-time threshold

A flight is **Delayed** when `ARRIVAL_DELAY >= 15` minutes, per the US DOT
standard (on time means arriving *less than* 15 minutes late).

The `>=` matters: **14,206 flights** arrived exactly 15 minutes late. Using
`> 15` moves all of them into On Time and inflates the on-time count by that
exact amount. `scripts/validate_dataset.py` asserts this figure directly.

---

## Verified baselines

Every figure below is asserted by `scripts/validate_dataset.py`.

| Metric | Value |
|---|---|
| Total flights | 1,949,742 |
| On time | 1,525,904 |
| Delayed (≥15 min) | 390,262 |
| Cancelled | 28,570 |
| Diverted | 5,006 |
| Completed | 1,916,166 |
| On Time % (Completed) | 79.6% |
| On Time % (Scheduled) | 78.3% |
| Cancellation rate | 1.47% |
| Disruption rate | 21.7% |
| Median arrival delay | −4 min |
| Mean arrival delay | +5.8 min |

The gap between the median (−4) and the mean (+5.8) is the story: most flights
arrive early, and a small tail of severe delays drags the average positive.
Never publish the mean without the median beside it.

### Delay attribution — 22,302,095 minutes

| Cause | Minutes | Share | Controllable by airline |
|---|---:|---:|:---:|
| Late aircraft | 8,709,198 | 39.1% | Yes |
| Airline | 7,542,717 | 33.8% | Yes |
| Air system | 4,696,308 | 21.1% | No |
| Weather | 1,328,155 | 6.0% | No |
| Security | 25,717 | 0.1% | No |
| **Controllable total** | **16,251,915** | **72.9%** | |

### Cancellations — 28,570

| Code | Reason | Count | Share |
|---|---|---:|---:|
| B | Weather | 16,372 | 57.3% |
| A | Airline / Carrier | 8,084 | 28.3% |
| C | National Air System | 4,112 | 14.4% |
| D | Security | 2 | 0.0% |

**The contrast worth putting on one page:** weather causes 6.0% of delay
*minutes* but 57.3% of *cancellations*. Airlines absorb bad weather by delaying;
when a delay can no longer absorb it, they cancel. Two different operational
levers, two different narratives.

---

## Data model

Star schema, four dimensions, one fact, all relationships single-direction
(dimension filters fact). No bi-directional filtering anywhere.

```
                     ┌──────────────┐
                     │  Date Table  │
                     │  (365 rows)  │
                     └──────┬───────┘
                            │ 1:*  [Date] → [Flight Date]
                            │
  ┌───────────┐      ┌──────▼───────────────┐      ┌─────────────────────┐
  │ airlines  │ 1:*  │                      │ *:1  │ cancellation_codes  │
  │ (14 rows) ├─────►│      flights         │◄─────┤ (5 rows)            │
  └───────────┘      │   1,949,742 rows     │      └─────────────────────┘
                     │                      │
  ┌───────────┐ 1:*  │                      │
  │ airports  ├─────►│                      │
  │ (10 rows) │      └──────────────────────┘
  └───────────┘
```

| From | To | Cardinality | Direction |
|---|---|---|---|
| `'Date Table'[Date]` | `flights[Flight Date]` | 1:* | Single |
| `airlines[IATA_CODE]` | `flights[AIRLINE]` | 1:* | Single |
| `airports[IATA_CODE]` | `flights[ORIGIN_AIRPORT]` | 1:* | Single |
| `cancellation_codes[CANCELLATION_REASON]` | `flights[CANCELLATION_REASON]` | 1:* | Single |

`flights[DESTINATION_AIRPORT]` has **no** relationship — see *Known limitations*.

### Naming policy

Raw physical column names from the source CSVs are kept everywhere, including
the dimensions. That is the convention, not an oversight. Friendly labels are
set as **display names** in Model view, which change what the reader sees
without rebinding any DAX.

One consequence worth knowing before you write a measure:

| Reference | Holds |
|---|---|
| `flights[AIRLINE]` | the two-letter IATA code — `"DL"` |
| `airlines[AIRLINE]` | the full carrier name — `"Delta Air Lines Inc."` |

Same column name, two different things, in a related pair of tables. Always
qualify the table.

---

## Known limitations

Stated plainly, because a limitation you disclose is a design decision and one
you hide is a defect.

1. **No destination dimension.** `DESTINATION_AIRPORT` holds 273 distinct values;
   `airports.csv` covers only the 10 origin hubs. Destination therefore appears
   as a raw IATA code in the report — the routes table renders
   "Los Angeles → JFK" rather than "Los Angeles → New York". Fix in v1.1 by
   loading the full 322-row airport reference and making `Airports` a
   role-playing dimension with an inactive destination relationship activated
   via `USERELATIONSHIP`.

2. **No query folding, and incremental refresh is not viable.** `Csv.Document`
   is a file connector with no query engine to push work down to. `RangeStart` /
   `RangeEnd` parameters would filter *after* a full file read, delivering
   partition complexity and no I/O saving. To enable incremental refresh, change
   the source — partitioned Parquet, SQL, or a Fabric Lakehouse — not the
   settings. For a static 2015 archive that will never receive new rows, this is
   an acceptable non-issue rather than a gap.

3. **Hours 03 and 04 contain zero flights.** This is real (no scheduled
   departures from these ten hubs in that window), not missing data. But a
   categorical X-axis will silently omit both and make the overnight trough look
   continuous. Use a continuous axis or a 24-row hour dimension.

4. **Single year, single country.** No year-over-year comparison is possible and
   no international benchmark applies.

5. **Rankings need a volume floor.** Hawaiian flies 3,368 flights against Delta's
   352,114. `[Min Flights For Ranking]` defaults to 5,000 for exactly this
   reason.

---

## Security and privacy

- **No PII.** The dataset contains no passenger, crew, contact or payment data.
  `TAIL_NUMBER` is an aircraft registration — an asset identifier on a public
  FAA registry, not personal data. It is dropped from the model regardless, as
  no visual consumes it.
- **No credentials.** No connection strings, keys or tokens anywhere in this
  repository. Verify with `git secrets --scan` or `gitleaks detect` before every
  push.
- **No filesystem or employer disclosure.** All source paths resolve through a
  single `SourceFolder` Power Query parameter. Earlier drafts hardcoded an
  absolute path containing an employer name and a Windows username — that class
  of leak is the reason the parameter exists.
- **Row-level security: none, by design.** The source is public-domain US
  government data with no confidentiality classification. RLS would add
  maintenance cost and no protection. If this model is ever repointed at
  commercial carrier data, RLS on `Airlines[Airline Code]` becomes mandatory —
  the design note is in `docs/model-design.md`.

---

## Reproducing the model

Full walkthrough in [`docs/rebuild-guide.md`](docs/rebuild-guide.md). Short form:

1. Open Power BI Desktop → **Transform data**
2. **Manage Parameters → New**: `SourceFolder` (Text) = your data folder path
3. Create five blank queries and paste each block from
   `src/powerquery/m-scripts.pq`
4. Name them exactly: `Airlines`, `Airports`, `Cancellation Codes`, `Flights`,
   `Date Table` — these names are a contract the DAX library depends on
5. **Close & Apply**, then build the four relationships in the table above
6. **Modeling → Mark as Date Table** → `'Date Table'[Date]`
7. Create an empty `_Measures` table and paste the measures from
   `src/dax/measures.dax`
8. Build the validation page described at the bottom of that file. The four
   `Check *` measures must all read exactly `0`

### Regenerating the dashboard

```bash
python scripts/build_dashboard.py --data data/raw
```

Recomputes every aggregate from `flight_rules.py`, asserts against the published
baselines, and **writes nothing if an assertion fails**. If the dashboard shows
a red banner at the top, its data is stale or unverified — the banner says
which, and a clean regeneration removes it.

---

## Tech stack

Power BI Desktop · Power Query (M) · DAX · VertiPaq · Python 3.10+ (pandas) ·
HTML/CSS/JS for the standalone report export

## License

- **Code** (M, DAX, Python, HTML) — MIT, see [`LICENSE`](LICENSE)
- **Data** — CC0 / public domain, US DOT Bureau of Transportation Statistics

Attribute the data to the US Department of Transportation, Bureau of
Transportation Statistics.

## Sources

- [2015 Flight Delays and Cancellations — Kaggle / US DOT](https://www.kaggle.com/datasets/usdot/flight-delays)
- [Fixing airport codes — Kaggle notebook documenting the mixed IATA/numeric encoding](https://www.kaggle.com/code/smiller933/fixing-airport-codes)
