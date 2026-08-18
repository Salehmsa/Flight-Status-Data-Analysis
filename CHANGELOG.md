# Changelog

## v1.0 — 2026-08-16

First published version. Supersedes an unpublished internal draft (v0) that was
withheld from release after a pre-publication technical review found six
blocking defects.

Everything below is recorded because the *class* of each defect is more useful
than the fix. All of them share one root cause: **a rule or a number was written
down in more than one place, and the copies drifted.**

---

### Blocking defects fixed

**One KPI, three published values.** The draft published `On Time %` as 79.6% in
the measure library, 78.26% in the Power Query documentation, and 78.99% in the
HTML dashboard. Two were correct with different denominators; one was wrong. All
three carried the same name.

*Fix:* two explicitly named measures, `On Time % (Completed)` and
`On Time % (Scheduled)`, each documenting its denominator and the question it
answers. There is deliberately no measure called `On Time %`.

---

**Dashboard classified flights with the wrong threshold.** The dashboard's
aggregates were produced by code carrying its own copy of the on-time rule,
which used `> 15` where the model uses `>= 15`. Result: 1,540,110 on-time
flights against the model's 1,525,904 — a discrepancy of exactly 14,206, the
number of flights that arrived exactly 15 minutes late.

*Fix:* deleted the second copy of the rule rather than correcting it.
`scripts/flight_rules.py` is now the single Python definition;
`scripts/build_dashboard.py` regenerates the dashboard from it, asserts against
published baselines, and writes nothing if an assertion fails. The dashboard
also carries a self-check banner that fires if its data was not produced by that
script.

---

**`Flight Status` classified flights with the wrong threshold.** The Power Query
step read `[ARRIVAL_DELAY] > 15` where the US DOT standard — and every document
in this project — is `>= 15`. The model therefore counted 1,540,110 on-time
flights against the correct 1,525,904.

*Fix:* `>= 15`, plus a null branch so a future extract cannot fail the refresh
silently. `Delay Band` had the same defect and the same fix.

This is the **root cause** of the dashboard discrepancy above. The dashboard was
not built from independent wrong code — it was faithfully reflecting a model
that was already wrong. One defect, three symptoms, 14,206 flights.

---

**`On Time Flights` did not implement the on-time standard at all.** It read
`CALCULATE([Total Flights], flights[DELAYED] = 0)`, filtering on a custom
`DELAYED` column with a zero-tolerance definition rather than the 15-minute
threshold. It counted 1,158,147 flights — **367,757 short** of correct, or 26×
the size of the dashboard defect, sitting in the measure the entire model's
punctuality story depends on.

*Fix:* rebound to `flights[Flight Status] = "On Time"`, so the rule lives in one
place and every dependent measure inherits it.

---

**`Completed Flights` returned more rows than the table contains.** It read
2,317,500 against a 1,949,742-row fact table — arithmetically impossible for a
row count, and it silently dragged `On Time % (Completed)` down to 65.8%.

*Fix:* `[Total Flights] - [Cancelled Flights] - [Diverted Flights]`.

---

**Absolute path leaked an employer name and a username.**
`C:\Users\IT\OneDrive - Naseej for Technology\...` appeared in four queries.

*Fix:* a single `SourceFolder` Power Query parameter.

---

**Data files exceeded GitHub limits.** `flights.csv` is ~290 MB against a 100 MB
hard block; the PBIX is a large undiffable binary.

*Fix:* `.gitignore` excludes both. `scripts/make_sample.py` produces a stratified
50,000-row sample (~8 MB) that preserves every carrier, month and cancellation
code — including code `D`, which has 2 rows in 1.9M and which proportional
sampling would have dropped.

---

**No README, licence or .gitignore.** All three added. MIT for the code, CC0 for
the data, stated separately.

---

### High-priority fixes

- **`Rolling 3M Avg On Time %` computed an unweighted mean of ~90 daily rates.**
  `AVERAGEX(DATESINPERIOD(...))` iterates individual dates, so a quiet Tuesday
  with 4,000 flights counted the same as a Friday with 7,000. Rewritten with
  `CALCULATE` so the ratio is recomputed over the whole window.

- **`Worst Airline` could name a carrier with no data.** `BLANK` sorts below
  every real value in an ascending `TOPN`, so any airline excluded by a slicer
  was reported as the worst performer. Guarded with `NOT ISBLANK`.

- **Rankings had no volume floor.** Hawaiian's 3,368 flights ranked against
  Delta's 352,114. Added `[Min Flights For Ranking]`, default 5,000.

- **Two measures named "total delay" that can never reconcile.**
  `Total Delay Minutes` covered all positive delays; `Total Attributed Delay Min`
  covers only flights ≥15 min. Renamed to `Total Positive Delay Minutes`.

- **Cancellation baselines off by one** in each direction (16,371/8,085 instead
  of 16,372/8,084) — a symptom of figures being retyped rather than computed.
  Baselines now live once, in `flight_rules.BASELINES`.

- **`Flights MoM %` guarded only the prior period**, publishing a real-looking
  −100% for October. Both sides guarded; `[Is Comparable Period]` added.

- **Incremental refresh was listed as a checklist item.** It is not achievable
  on a CSV source: `RangeStart`/`RangeEnd` cannot fold, so they cost a full file
  read and buy nothing. Now documented as a deliberate non-implementation with
  three concrete upgrade paths.

- **Seven unconsumed high-cardinality columns** dropped: `TAIL_NUMBER`,
  `FLIGHT_NUMBER` and five of the six `time` columns.

- **October gap attributed to "the source".** Reframed as a probable consequence
  of the project's own IATA-code filter, labelled explicitly as a hypothesis,
  with the confirming test in `validate_dataset.py` and `docs/data-lineage.md`.

### Medium-priority fixes

- `Airline Short Name` produced an inconsistent chart axis (`American` but
  `United Air Lines`) because three carriers spell it "Air Lines" as two words.
  Replaced chained `Text.Replace` with an explicit 14-row lookup.
- `Flight Status` would throw on a null `ARRIVAL_DELAY`. Added an `"Unknown"`
  branch, asserted to be empty.
- `Distance Band` label said `>1500` while the logic assigned exactly 1500 to
  that band.
- Date table was hardcoded to 2015 and `Has Flight Data` to `MONTH = 10`. Both
  now derived from the data.
- `RANKX(ALL(...))` ignored page slicers. Changed to `ALLSELECTED`.
- The 80% target and the coverage note were hardcoded. Both now driven by
  `[Target OTP]` and derived text respectively.
- `Table.InsertRows` with a hardcoded index replaced by `Table.Combine`.
- Relationship spec referenced `[Code]` where the query produces
  `[Cancellation Code]`.

### Low-priority fixes

- `Disruption Rate %` documented as 21.75%; the value is 21.74%, rendering as
  21.7% at the stated format.
- Removed a dead `Rank` column from the `DATATABLE` in `Top Delay Cause`.
- `Avg Delay Recovery` was derived by subtracting two means taken over different
  row populations — an invalid subtraction. `validate_dataset.py` now reports
  both the correct row-wise figure and the naive one, so the size of the error is
  visible rather than argued about.
- Validation checklist claimed `Departure Hour` ranges 0–23. It has 22 distinct
  values; hours 03 and 04 hold zero flights. Real, not a defect — but it means a
  categorical X-axis silently omits them.

---

### Decisions reviewed and left unchanged

Recorded so they are not "fixed" by someone later:

- **NULLs preserved in the five delay-reason columns.** They are structural
  (79.98% null, populated only at ≥15 min). Zero-filling would understate every
  cause by roughly 5×. This is the most consequential correct decision in the
  project.
- **`>= 15` threshold**, matching US DOT and confirmed by the data.
- **Cancelled and diverted excluded from punctuality denominators** — confirmed:
  the `N/A` band holds exactly 28,570 + 5,006 rows.
- **Different denominator for cancellation rate** — a cancellation is measured
  against what was promised, a delay against what operated.
- **`"N"` member added to the cancellation dimension** rather than hiding blanks
  in each visual.
- **Ghost index column dropped before header promotion** — the correct order.
- **`2400 → 00:00`** time handling.
- **ISO weekday**, matching the source `DAY_OF_WEEK`.
- **Gap-free calendar** despite the October hole in the facts.
- **Median shown beside the mean** — the −4 vs +5.8 gap is the story.

---

### Added in v1.0

- `scripts/flight_rules.py` — single Python definition of every rule and baseline
- `scripts/validate_dataset.py` — 45+ assertions, exit code 1 on failure
- `scripts/build_dashboard.py` — regenerates the dashboard, refuses to write on
  a failed assertion
- `scripts/make_sample.py` — stratified committable sample
- `docs/data-dictionary.md`, `docs/kpi-definitions.md`, `docs/data-lineage.md`,
  `docs/model-design.md`, `docs/rebuild-guide.md`
- Four `Check *` measures and a hidden validation page
- 26 measures beyond the original 32 (58 total, 9 display folders)
- `src/dax/deploy_measures.csx` — Tabular Editor script that creates all 58
  measures with formats and display folders in one run, instead of 58 manual
  pastes into the formula bar

---

---

### Withdrawn: a finding that was wrong

The review raised **P0-3, "four DAX measures reference columns that do not
exist"**, and rewrote the library to use `Airlines[Airline Name]`,
`Airports[Airport Name]` and `'Cancellation Codes'[Cancellation Code]`.

**The originals were correct.** The live model uses raw column names throughout
— `airlines[AIRLINE]`, `airports[AIRPORT]`,
`cancellation_codes[CANCELLATION_REASON]` — exactly as the original library
wrote them. The replacements were the ones that would have broken.

The cause: `PowerQuery_M_Scripts.txt` was read as a description of the model.
It was not. It documented renames that were never applied. The drift was real
but pointed the other way — the DAX matched reality and the documentation did
not.

Everything was rebound to the live model, and the M scripts were rewritten to
describe what actually exists. Full account in
[`docs/REVIEW-CORRECTION.md`](docs/REVIEW-CORRECTION.md).

**The lesson is the one this whole changelog is about:** a document describing a
model is not a model. Verify against the artefact, not against another document.

---

## Model state at v1.0

Every published figure now reconciles across all three surfaces — the raw CSV
(via `validate_dataset.py`), the Power BI model, and the HTML dashboard:

| | Model | Validated |
|---|---|---|
| On Time % (Completed) | 79.633% | 79.63% |
| On Time % (Scheduled) | 78.262% | 78.26% |
| Completed Flights | 1,916,166 | 1,916,166 |

This is the first point in the project's history at which that has been true.

## Open before v1.1

- [ ] Confirm the October root cause against the full upstream file
- [ ] Record measured model size from DAX Studio (currently unmeasured)
- [ ] Load the full 322-row airport reference; make `Airports` role-playing
- [ ] Add a US federal holiday flag to the date dimension
- [ ] Agree the amber/red thresholds in `kpi-definitions.md` with the business
