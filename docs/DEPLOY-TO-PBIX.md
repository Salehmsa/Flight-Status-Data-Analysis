# Deploying to the live PBIX

Built from an inspection of the actual `#Measures` table on 2026-08-16, not from
any document. **31 measures already exist and most are correct** — this is a
targeted patch, not a 58-measure paste.

Work through the phases in order. Phase 1 must come first: it unblocks
everything else.

---

## What is already there — 31 measures

| Folder | Present | Verdict |
|---|---|---|
| Base Measures | Cancelled / Delayed / Diverted / **On-Time-Flights** / Total Flights | rename one |
| Delay Attribution | 5 cause sums, Total Attributed, Controllable Delay % | complete |
| Delay Magnitude | Avg Delay (Delayed Only), Avg Delay Recovery, **Delay Attribution**, Median Arrival Delay, Recovery Rate %, **Total Delay Minutes** | 3 gaps, 1 rename, 1 stray |
| Ranking | Airline Rank by On Time, Airport Rank by On Time, Best Airline, Worst Airline, **+ Airline Rank, Airline_Rank, Test Airline, Test OTP** | 4 to review |
| Rate KPIs | Cancellation %, **Completed Flights**, Delay Rate %, Disruption %, Diverted %, **On Time %** | 1 rename, 1 misfiled |
| Time Intelligence | Flights MoM %, Flights PM, **On Time % MoM**, On Time % PM, Rolling 3M On Time % | 1 rename, 2 formula fixes |

**Entirely missing: the Cancellation Analysis folder.** Six measures, including
the 57.3% weather-cancellation figure that carries half the project's story.

---

## Phase 1 — Renames (3). Do these first.

Renaming a measure in Power BI **automatically updates every other measure that
references it**. Doing this first means nothing downstream has to be edited
twice.

Right-click the measure → Rename.

| Current | Rename to | Why |
|---|---|---|
| `On-Time-Flights` | `On Time Flights` | Hyphens are inconsistent with all 30 other measures, and every published DAX snippet for this project uses the spaced form. This is the single most important rename: measures you paste later will reference `[On Time Flights]` and fail against the hyphenated name. |
| `On Time %` | `On Time % (Completed)` | The name that carried three different values across this project. Once renamed, `On Time % (Scheduled)` can be added beside it without ambiguity. |
| `Total Delay Minutes` | `Total Positive Delay Minutes` | It counts every positive delay minute including 1–14 min flights, so it can never reconcile with `Total Attributed Delay Min` (22,302,095). Two measures called "total delay" that do not tie is the fastest way to lose a stakeholder's trust. |
| `On Time % MoM` | `On Time % MoM (pp)` | The result is a difference in percentage POINTS. Labelling a 3.0pp move as "+3%" is a classic reporting error. |

### Then verify one formula

Click `On Time % (Completed)` and check the formula bar reads:

```dax
On Time % (Completed) = DIVIDE( [On Time Flights], [Completed Flights] )
```

If the denominator is `[Total Flights]`, change it to `[Completed Flights]` —
that measure is the operational KPI and must exclude cancelled and diverted
flights, which carry no punctuality outcome at all.

---

## Phase 2 — The missing Cancellation Analysis folder (6)

`Home → New measure`, paste, Enter. Then set **Display folder** to
`Cancellation Analysis` in the Properties pane.

```dax
Weather Cancellations = CALCULATE( [Cancelled Flights], cancellation_codes[CANCELLATION_REASON] = "B" )
```
```dax
Carrier Cancellations = CALCULATE( [Cancelled Flights], cancellation_codes[CANCELLATION_REASON] = "A" )
```
```dax
Air System Cancellations = CALCULATE( [Cancelled Flights], cancellation_codes[CANCELLATION_REASON] = "C" )
```
```dax
Security Cancellations = CALCULATE( [Cancelled Flights], cancellation_codes[CANCELLATION_REASON] = "D" )
```
```dax
Weather Cancellation % = DIVIDE( [Weather Cancellations], [Cancelled Flights] )
```
```dax
Cancellations per 1000 Flights = DIVIDE( [Cancelled Flights], [Total Flights] ) * 1000
```

Expected: 16,372 · 8,084 · 4,112 · 2 · 57.3% · 14.7

**Put `Weather Cancellation %` on the same page as `Controllable Delay %`.**
Weather causes 6.0% of delay *minutes* but 57.3% of *cancellations*. Airlines
absorb bad weather by delaying; when a delay can no longer absorb it, they
cancel. That contrast only lands side by side.

---

## Phase 3 — Parameters and guards (5)

Folder `Parameters`:

```dax
Target OTP = 0.80
```
```dax
Min Flights For Ranking = 5000
```

Folder `Delay Magnitude` — three genuine gaps:

```dax
Avg Arrival Delay = AVERAGE( flights[ARRIVAL_DELAY] )
```
```dax
Avg Departure Delay = AVERAGE( flights[DEPARTURE_DELAY] )
```
```dax
Max Arrival Delay = MAX( flights[ARRIVAL_DELAY] )
```

Folder `Rate KPIs`:

```dax
On Time % (Scheduled) = DIVIDE( [On Time Flights], [Total Flights] )
```

Baseline 78.3%. This is the customer-facing KPI. Use it for carrier league
tables — without it, an airline improves its score by cancelling its weakest
flights. American Eagle cancels 4.84% of its schedule against Delta's 0.35%; on
the Completed basis that difference is invisible.

Folder `Time Intelligence`:

```dax
Is Comparable Period = IF( [Total Flights] > 0 && [Flights PM] > 0, 1, 0 )
```

Drop this into the Filters pane (`= 1`) on every time-series visual. October
2015 has zero rows, and without the guard every MoM measure publishes a
real-looking −100% collapse.

---

## Phase 4 — Four formula fixes

Click the measure, replace the formula bar contents.

### `Rolling 3M On Time %`

```dax
Rolling 3M On Time % =
CALCULATE( [On Time % (Completed)],
    DATESINPERIOD( 'Date Table'[Date], MAX( 'Date Table'[Date] ), -3, MONTH ) )
```

If the current version uses `AVERAGEX`, it is averaging ~90 **daily** rates
unweighted — a quiet Tuesday with 4,000 flights counting the same as a Friday
with 7,000. `DATESINPERIOD` returns individual dates, not months. `CALCULATE`
recomputes the ratio across the whole window, correctly volume-weighted.

### `Flights MoM %`

```dax
Flights MoM % =
VAR Curr = [Total Flights]
VAR Prev = [Flights PM]
RETURN IF( NOT ISBLANK( Prev ) && NOT ISBLANK( Curr ), DIVIDE( Curr - Prev, Prev ) )
```

Guard **both** sides. Guarding only the prior period still publishes −100.0% for
October, where Curr is blank and Prev is September's 172,409.

### `Worst Airline`

```dax
Worst Airline =
VAR Ranked =
    FILTER(
        ADDCOLUMNS( ALLSELECTED( airlines[AIRLINE] ),
            "@OTP", [On Time % (Completed)],
            "@Vol", [Total Flights] ),
        NOT ISBLANK( [@OTP] ) && [@Vol] >= [Min Flights For Ranking] )
RETURN MINX( TOPN( 1, Ranked, [@OTP], ASC ), airlines[AIRLINE] )
```

The `NOT ISBLANK` guard is load-bearing. BLANK sorts **below** every real value
in an ascending `TOPN`, so without it any airline excluded by a slicer is
reported to the executive as the worst performing airline. That defect survives
testing and fails in a board meeting.

### `Best Airline`

```dax
Best Airline =
VAR Ranked =
    FILTER(
        ADDCOLUMNS( ALLSELECTED( airlines[AIRLINE] ),
            "@OTP", [On Time % (Completed)],
            "@Vol", [Total Flights] ),
        NOT ISBLANK( [@OTP] ) && [@Vol] >= [Min Flights For Ranking] )
RETURN MAXX( TOPN( 1, Ranked, [@OTP], DESC ), airlines[AIRLINE] )
```

The volume floor matters: Hawaiian flies 3,368 flights against Delta's 352,114.
Ranking them on one axis without a floor produces statistically meaningless
winners in a board deck.

---

## Phase 5 — The validation page (4 + a page)

Folder `Validation`:

```dax
Check Status Sum = [Total Flights] - ( [On Time Flights] + [Delayed Flights] + [Cancelled Flights] + [Diverted Flights] )
```
```dax
Check Rate Sum = ROUND( [On Time % (Completed)] + [Delay Rate %] - 1, 6 )
```
```dax
Check Cancel Codes = [Cancelled Flights] - ( [Weather Cancellations] + [Carrier Cancellations] + [Air System Cancellations] + [Security Cancellations] )
```
```dax
Check Attribution = [Total Attributed Delay Min] - ( [Air System Delay Min] + [Security Delay Min] + [Airline Delay Min] + [Late Aircraft Delay Min] + [Weather Delay Min] )
```

New page → one Table visual → drag in every measure below. No grouping.

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
| Delay Rate % | 20.4% |
| Cancellation Rate % | 1.47% |
| Disruption Rate % | 21.7% |
| Total Attributed Delay Min | 22,302,095 |
| Controllable Delay % | 72.9% |
| Weather Cancellation % | 57.3% |
| **Check Status Sum** | **0** |
| **Check Rate Sum** | **0** |
| **Check Cancel Codes** | **0** |
| **Check Attribution** | **0** |

Every figure above was recomputed from the raw CSV by
`scripts/validate_dataset.py` and passed. They are measured, not asserted.

Hide the page (right-click the tab → Hide page). Never delete it.

### If a number is wrong

| Symptom | Cause |
|---|---|
| On Time exactly **14,206** too high | `Flight Status` built with `> 15` instead of `>= 15` |
| 78.3% where 79.6% expected, or reverse | Cancelled/diverted inside a punctuality denominator |
| Attribution averages ~80% low | The five reason columns were zero-filled instead of left NULL |
| A measure will not evaluate at all | A name has drifted. **Check the model first, not the document** — assuming a document described the model is what produced `REVIEW-CORRECTION.md` |

---

## Phase 6 — Housekeeping

### Delete after checking dependencies

Two of these are unambiguous. Two need a look first.

| Measure | Action |
|---|---|
| `Test Airline` | Delete. Test leftovers in a published model tell a reviewer nobody swept up. |
| `Test OTP` | Delete. |
| `Airline Rank` | **Check first.** You have three ranking measures — `Airline Rank`, `Airline_Rank`, `Airline Rank by On Time`. Keep one. |
| `Airline_Rank` | **Check first.** Same. |
| `Delay Attribution` | **Check first.** A measure with the same name as a display folder, filed under *Delay Magnitude*. Almost certainly a stray. |

Before deleting anything: **View → Dependencies** (or right-click → Show
dependencies) to confirm no visual uses it. A measure deleted while a visual
still references it leaves the visual permanently broken with no error until
someone opens that page.

### Fix the two broken measures on `flights`

The Data pane shows `% Canc…` and `% Delay…` on the `flights` table with error
icons. Either fix them or delete them. **A model that ships with visible warning
icons teaches its readers to ignore warning icons** — which is expensive the
first time one is real.

### Move measures into `#Measures`

`Completed Flights` sits under *Rate KPIs*; it is a base count and belongs in
*Base Measures*. Any measure still parked on the `flights` table should move to
`#Measures` too. A measure attached to a table implies it belongs to that table,
which is never true — measures operate over the whole model.

### Identify the `Metric` table

There is a table named `Metric` in the model with no documented purpose. Find
out what it is or remove it. An unexplained table in a portfolio repo is a
question you will be asked in an interview.

---

## Summary

| Phase | Work |
|---|---|
| 1 | 4 renames + verify 1 formula |
| 2 | 6 new measures (Cancellation Analysis) |
| 3 | 7 new measures (params, gaps, guards) |
| 4 | 4 formula replacements |
| 5 | 4 new measures + validation page |
| 6 | Delete 2, review 3, fix 2 broken, move 1, identify 1 table |

**17 new measures. 4 renames. 4 formula fixes.** Not 58.
