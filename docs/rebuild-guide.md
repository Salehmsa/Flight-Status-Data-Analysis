# Rebuild Guide

Reproduce the entire project from a clean clone. About 40 minutes, most of it
waiting for a 1.9M-row refresh.

**Prerequisites:** Power BI Desktop (2023.x or later), Python 3.10+, ~2 GB free
disk, a Kaggle account.

---

## 1 · Get the data (10 min, mostly download)

`flights.csv` is ~290 MB and is not committed — GitHub hard-blocks pushes above
100 MB.

1. Download [2015 Flight Delays and Cancellations](https://www.kaggle.com/datasets/usdot/flight-delays)
2. Filter `flights.csv` to the ten origin airports in
   `data/reference/airports.csv`:

```python
import pandas as pd
HUBS = ["ATL","ORD","DFW","DEN","LAX","SFO","PHX","IAH","LAS","MSP"]
df = pd.read_csv("flights.csv", low_memory=False)
df[df.ORIGIN_AIRPORT.isin(HUBS)].to_csv("data/raw/flights.csv", index=True)
```

3. Copy the three reference CSVs into the same folder:

```bash
cp data/reference/*.csv data/raw/
```

`data/raw/` should now hold `flights.csv`, `airlines.csv`, `airports.csv`,
`cancellation_codes.csv`.

---

## 2 · Validate before you build (2 min)

Do this **first**. Building a model on unverified data wastes the next thirty
minutes.

```bash
pip install pandas
python scripts/validate_dataset.py --data data/raw
```

Expect `RESULT: all N assertions PASSED` and exit code `0`. If it fails, stop —
the file you have is not the file this project describes, and nothing downstream
will tie.

---

## 3 · Build the model (25 min)

### 3.1 Parameter first

Power BI Desktop → **Transform data** → **Manage Parameters** → **New**

| Field | Value |
|---|---|
| Name | `SourceFolder` |
| Type | Text |
| Suggested values | Any value |
| Current Value | your absolute path to `data/raw`, **with trailing backslash** |

Everything resolves against this one value. This is why no absolute path appears
anywhere in the repository.

### 3.2 The five queries

For each: **Home → New Source → Blank Query → View → Advanced Editor**, paste the
block from `src/powerquery/m-scripts.pq`, **Done**, then rename the query.

| Order | Query name | Rows | Notes |
|---|---|---|---|
| 1 | `Airlines` | 14 | |
| 2 | `Airports` | 10 | |
| 3 | `Cancellation Codes` | 5 | Note the space in the name |
| 4 | `Flights` | 1,949,742 | The slow one |
| 5 | `Date Table` | 365 | Depends on `Flights` — create it last |

> Query names are a contract consumed by `src/dax/measures.dax`. They are not
> cosmetic. `Cancellation Codes` with a space is referenced in DAX as
> `'Cancellation Codes'`.

**Close & Apply.** The `Flights` refresh takes several minutes.

### 3.3 Data categories

Model view → `Airports`:

| Column | Data category |
|---|---|
| `Latitude` | Latitude |
| `Longitude` | Longitude |
| `State` | State or Province |

Skip this and map visuals geocode by name, which can plot a US airport on the
wrong continent.

### 3.4 Relationships

Model view. All **single** direction, dimension → fact.

| From | To |
|---|---|
| `'Date Table'[Date]` | `Flights[Flight Date]` |
| `Airlines[Airline Code]` | `Flights[AIRLINE]` |
| `Airports[Airport Code]` | `Flights[ORIGIN_AIRPORT]` |
| `'Cancellation Codes'[Cancellation Code]` | `Flights[CANCELLATION_REASON]` |

Do not enable bi-directional filtering on any of them.

### 3.5 Mark the date table

Select `Date Table` → **Table tools → Mark as date table** → column `[Date]`.

Required. Without it `DATEADD` and `DATESINPERIOD` return wrong results silently
rather than erroring.

### 3.6 Sort columns

| Table | Sort this | By this |
|---|---|---|
| `Date Table` | `Month Name` | `Month Number` |
| `Date Table` | `Day Name` | `ISO Weekday` |

`ISO Weekday` is 1 = Monday, matching the source `DAY_OF_WEEK`. Power BI's
default `WEEKDAY()` starts at Sunday = 1; mixing the two shifts every
day-of-week chart by one position.

---

## 4 · Add the measures (10 min)

1. **Home → Enter data** → table name `_Measures` → **Load**, then delete
   `Column1` (right-click → Delete)
2. For each measure in `src/dax/measures.dax`: **Home → New measure**, paste,
   Enter
3. Set the display folder from the Properties pane (folder names are the `##`
   headings in the file)
4. Apply the formats noted in the comments

---

## 5 · Verify (5 min)

Build a validation page — a single table visual, no grouping, these values:

| Measure | Expected |
|---|---|
| Total Flights | 1,949,742 |
| On Time Flights | 1,525,904 |
| Delayed Flights | 390,262 |
| Cancelled Flights | 28,570 |
| Diverted Flights | 5,006 |
| Completed Flights | 1,916,166 |
| On Time % (Completed) | 79.6% |
| On Time % (Scheduled) | 78.3% |
| Cancellation Rate % | 1.47% |
| Disruption Rate % | 21.7% |
| Total Attributed Delay Min | 22,302,095 |
| Controllable Delay % | 72.9% |
| Weather Cancellation % | 57.3% |
| **Check Status Sum** | **0** |
| **Check Rate Sum** | **0** |
| **Check Cancel Codes** | **0** |
| **Check Attribution** | **0** |

The four `Check` measures are the ones that matter — they must read exactly zero
after every refresh, forever. Keep this page hidden but never delete it.

### If a number is wrong

| Symptom | Cause |
|---|---|
| On Time exactly **14,206** too high, Delayed 14,206 too low | `Flight Status` built with `> 15` instead of `>= 15` |
| 78.3% where 79.6% expected (or reverse) | Cancelled/diverted rows in a punctuality denominator |
| Attribution averages ~80% too low | The five reason columns were zero-filled instead of left NULL |
| Every measure referencing a dimension errors | Query renamed, or a fact column renamed in Power Query |
| Day-of-week chart shifted by one | `WEEKDAY()` default used instead of ISO |

---

## 6 · Regenerate the dashboard (2 min)

```bash
python scripts/build_dashboard.py --data data/raw \
    --template reports/Flight_Operations_Dashboard.html
```

The script recomputes every aggregate from `scripts/flight_rules.py`, asserts it
against the published baselines, and **writes nothing if an assertion fails**.

Open the result. If a red banner appears at the top, the file is stale or the
build failed — the banner says which. A clean regeneration removes it.

Dry run without writing:

```bash
python scripts/build_dashboard.py --data data/raw --check-only
```

---

## 7 · Build the sample (1 min)

```bash
python scripts/make_sample.py --data data/raw --out data/sample --n 50000
```

Produces `data/sample/flights_sample.csv` (~8 MB, committed) so a visitor can
open the model without a 290 MB download. Stratified on
month × airline × status, seed 42, with rare cancellation codes force-kept.

---

## 8 · Publish

Full checklist in the technical review report. The short version:

```bash
git init
# confirm .gitignore is in place BEFORE the first add — a 290 MB file that
# reaches history stays in the pack forever
git status                      # flights.csv and *.pbix must NOT appear
gitleaks detect                 # or: git secrets --scan
git add . && git commit -m "Flight Operations Intelligence 2015 v1.0"
git tag v1.0
git push origin main --tags
```

Then attach the `.pbix` to the GitHub Release rather than committing it. A
binary with 1.9M imported rows cannot be diffed or merged, and every save adds a
full new copy to history.

If you want the model itself under version control, save as **PBIP/TMDL**
(`File → Save as → .pbip`) — plain text, diffable, reviewable in a pull request.
That is the current standard practice for Power BI on git.
