# Model Design

The schema, the decisions behind it, the security posture, and the upgrade path.

---

## Schema

Star, four dimensions, one fact. Every relationship single-direction, dimension
filtering fact.

```
                          ┌────────────────────┐
                          │    Date Table      │
                          │   365 rows · M     │
                          │  Marked as Date    │
                          └─────────┬──────────┘
                                    │ 1:*
                                    │ [Date] → [Flight Date]
                                    │
  ┌──────────────┐  1:*    ┌────────▼──────────┐  *:1   ┌─────────────────────┐
  │  Airlines    ├────────►│     Flights       │◄───────┤ Cancellation Codes  │
  │  14 rows     │         │  1,949,742 rows   │        │  5 rows             │
  └──────────────┘         │                   │        └─────────────────────┘
                           │  Flight Status    │
  ┌──────────────┐  1:*    │  Delay Band       │
  │  Airports    ├────────►│  Distance Band    │
  │  10 rows     │         │  Delay Recovery   │
  └──────────────┘         │  Departure Hour   │
                           └───────────────────┘
                                    ▲
                          DESTINATION_AIRPORT
                          (273 values, no relationship)
```

| From | To | Cardinality | Cross-filter |
|---|---|---|---|
| `'Date Table'[Date]` | `Flights[Flight Date]` | 1:* | Single |
| `Airlines[Airline Code]` | `Flights[AIRLINE]` | 1:* | Single |
| `Airports[Airport Code]` | `Flights[ORIGIN_AIRPORT]` | 1:* | Single |
| `'Cancellation Codes'[Cancellation Code]` | `Flights[CANCELLATION_REASON]` | 1:* | Single |

**No bi-directional filtering anywhere.** With one large fact and four small
dimensions there is no scenario in this model that requires it, and it
introduces filter ambiguity the moment a fifth table is added. If you later need
a many-to-many, add it deliberately with `CROSSFILTER` in a measure rather than
flipping a relationship globally.

---

## Design decisions

### Why the `_Measures` table exists

An empty table hosting all 50 measures. Measures parked on the fact table clutter
the field list and imply — wrongly — that a measure belongs to a table. Grouping
them into one table with eight display folders makes the model navigable to
someone who did not build it.

### Why `Date Table` is built in M, not DAX

A DAX calculated table cannot participate in incremental refresh and is invisible
to Power Query's lineage view. It also cannot be exported to this repository as
reviewable source. The M version derives its range from `MIN`/`MAX` of
`Flights[Flight Date]`, so it cannot silently truncate the model the day someone
adds 2016 data.

### Why the calendar covers October when the facts do not

Time intelligence requires a gap-free date table. `DATEADD` and `DATESINPERIOD`
navigate the date dimension, not the fact table — a hole in the calendar breaks
them for every period, not just the missing one. The facts have a hole;
the calendar must not.

### Why `Cancellation Codes` has a fifth member

98.5% of fact rows are not cancelled. Without an `"N"` member they resolve to a
`(Blank)` row in every slicer and legend. Adding the member is the correct fix.
Hiding the blank in each visual is not — it treats the symptom once per visual
and forever.

### Why there are two on-time measures and no measure called "On Time %"

Both denominators are legitimate and they answer different questions. v1 had one
name and three values across three artefacts. See `docs/kpi-definitions.md`.

### Why rankings have a volume floor

Hawaiian flies 3,368 flights; Delta flies 352,114. `[Min Flights For Ranking]`
defaults to 5,000. It is a judgement call, exposed as a parameter so the business
can move it rather than file a change request.

---

## Cardinality and storage

VertiPaq compresses by column, so cardinality — not row count — drives size.

| Column | Distinct | In model | Rationale |
|---|---:|:---:|---|
| `AIRLINE` | 14 | Yes | Dimension key |
| `ORIGIN_AIRPORT` | 10 | Yes | Dimension key |
| `DESTINATION_AIRPORT` | 273 | Yes | No dimension; used as a text attribute |
| `Flight Date` | 334 | Yes | Dimension key |
| `Departure Hour` | 22 | Yes | Cheap, high analytical value |
| `Flight Status` | 4 | Yes | Drives every status measure |
| `Delay Band` / `Distance Band` | 5 / 3 | Yes | Cheap |
| `ARRIVAL_DELAY` / `DEPARTURE_DELAY` | ~1,700 | Yes | Core facts |
| The five reason columns | ~1,000 each | Yes | 79.98% null — compresses very well |
| `TAIL_NUMBER` | ~4,900 | **No** | No visual consumes it |
| `FLIGHT_NUMBER` | ~6,900 | **No** | No visual consumes it |
| 5 of 6 `time` columns | ~1,440 each | **No** | Only `SCHEDULED_DEPARTURE` is used |

Dropping those seven columns is the largest single saving available.

> **Measure it, do not estimate it.** DAX Studio → *View Metrics*, before and
> after, and record both figures in the README. An optimisation claim without a
> measurement is an opinion.

### Measures to watch

| Measure | Cost | Rule |
|---|---|---|
| `Median Arrival Delay` | Highest | Card only. Never in a matrix by airline × month × airport |
| `Top Delay Cause` | Moderate | Evaluates 5 measures per row. Card only |
| `Best` / `Worst Airline` | Moderate | Fine at 14 rows; revisit if the dimension grows |
| `Rolling 3M On Time %` | Moderate | `CALCULATE`, not `AVERAGEX` — see kpi-definitions.md |

---

## Security posture

### Row-level security: none, deliberately

The source is public-domain US government data with no confidentiality
classification. RLS would add maintenance cost and protect nothing.

**This is documented precisely because "no RLS" and "we forgot RLS" look
identical from the outside.** A reviewer who finds this section knows the
decision was made.

**When that changes:** if this model is ever repointed at commercial carrier
data, RLS on `Airlines[Airline Code]` becomes mandatory. The design would be:

```dax
-- Table: Airlines · Role: Carrier User
[Airline Code] = LOOKUPVALUE(
    UserAirlineMap[Airline Code],
    UserAirlineMap[UPN], USERPRINCIPALNAME() )
```

With single-direction relationships already in place, filtering `Airlines`
propagates to `Flights` automatically. No model change would be needed — which
is one more reason not to enable bi-directional filtering today.

### Object-level security: not applicable

No column in the model is sensitive.

### What is actually sensitive here

Not the data — the **paths**. v1 hardcoded an absolute path containing an
employer name and a Windows username into four queries. That is the only real
disclosure this project ever had, and it is why `SourceFolder` is a parameter.

Run `gitleaks detect` or `git secrets --scan` before every push. This project
needs no credentials, which is exactly why a stray one must never slip through.

---

## Report design guidance

### Accessibility

- Do not encode status by colour alone. The green/amber/red from
  `[KPI Status Colour]` must be paired with a number or an icon — roughly 8% of
  men have some form of colour vision deficiency.
- Contrast: the dark theme uses `#E9EEF7` on `#0F1826`, which passes WCAG AA for
  body text. Verify any new colour against a contrast checker rather than by eye.
- Set alt text on every visual (Format → General → Alt text).
- Set tab order explicitly on every page (Selection pane → Tab order). The
  default follows creation order, which is rarely the reading order — and in an
  Arabic RTL report it is almost never right.

### Page structure

| Page | Answers | Anchor measures |
|---|---|---|
| Executive summary | Did the schedule hold? | `Disruption Rate %`, `On Time % (Completed)`, `KPI Status Colour` |
| Delay attribution | What do we control? | `Controllable Delay %`, `Top Delay Cause` |
| Network & hubs | Where is the weak link? | `Airport Rank by On Time`, hub map |
| Carrier league | Who is reliable to a passenger? | `On Time % (Scheduled)`, `Cancellation Rate %` |
| Time patterns | When does it break? | `On Time %` by hour, by day, `Rolling 3M` |
| Validation *(hidden)* | Do the numbers still tie? | the four `Check *` measures |

Put `[Data Coverage Note]` on every page. Never let a stakeholder discover the
October gap on their own in the middle of a meeting.

Put `[Controllable Delay %]` and `[Weather Cancellation %]` on the **same** page.
Weather causes 6.0% of delay minutes and 57.3% of cancellations — that contrast
is the most interesting thing in this dataset and it only lands side by side.

---

## Upgrade path

### v1.1 — destination as a role-playing dimension

Highest-value change available. `DESTINATION_AIRPORT` currently renders as a raw
code because `airports.csv` covers only the ten hubs.

1. Download the full 322-row `airports.csv` from the Kaggle source
2. Replace `data/reference/airports.csv`
3. Add a second relationship, **inactive**:
   `Airports[Airport Code] → Flights[DESTINATION_AIRPORT]`
4. Expose destination measures via `USERELATIONSHIP`:

```dax
On Time % (Destination) =
CALCULATE(
    [On Time % (Completed)],
    USERELATIONSHIP( Airports[Airport Code], Flights[DESTINATION_AIRPORT] ) )
```

True origin–destination analysis is where the operational value in this dataset
actually lives.

### v1.1 — US federal holiday flag

Thanksgiving, Christmas and July 4th drive a large share of the delay variance.
A holiday flag turns "December is bad" into "the eight days around Christmas are
bad" — a staffing decision rather than a seasonal shrug.

### v1.2 — Parquet source

Partition `flights.csv` into monthly Parquet files and point a Folder query at
them. Still no folding, but refresh I/O drops by roughly 11/12 and the source
stops being a 290 MB file nobody can commit.

### Not recommended

- **SQL / Fabric backing.** Correct engineering for a live pipeline,
  over-engineering for a static 2015 archive.
- **Bi-directional relationships.** Nothing in this model needs them.
- **A calculated column for on-time %.** Ratios belong in measures; a calculated
  column would freeze the denominator at row grain and break every aggregation.
