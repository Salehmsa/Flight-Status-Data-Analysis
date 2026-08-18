# Review Correction — P0-3 was wrong

**Date:** 2026-08-16
**Status:** the measure library must be rebound before it is used against the
existing PBIX.

---

## What I got wrong

The technical review raised **P0-3: "four DAX measures reference columns that do
not exist"**, and I rewrote the library on that basis:

| Review said was broken | Review changed it to |
|---|---|
| `airlines[AIRLINE]` | `Airlines[Airline Name]` |
| `airports[AIRPORT]` | `Airports[Airport Name]` |
| `cancellation_codes[CANCELLATION_REASON]` | `'Cancellation Codes'[Cancellation Code]` |

**The originals were correct. My replacements are the ones that would break.**

Inspection of the live model in Power BI Desktop shows:

```
airlines             AIRLINE, IATA_CODE
airports             AIRPORT, CITY, COUNTRY, IATA_CODE, LATITUDE, LONGITUDE, STATE
cancellation_codes   CANCELLATION_REASON, CANCELLATION_DESCRIPTION
flights              raw CSV names + Delay Band, Delay Recovery, Departure Hour
Date Table           present
#Measures            present (not _Measures)
```

Lower-case table names, underscores, raw column headers. No renames anywhere.

## How the error happened

I reviewed the three text artefacts against each other and treated
`PowerQuery_M_Scripts.txt` as a description of the model that exists. It is not.
It documents renames — `IATA_CODE → Airline Code`, `AIRPORT → Airport Name`,
adding `Airline Short Name` and `Airport Label` — that **were never applied**.
The model was built from the raw CSVs.

So the drift was real, but it pointed the other way: **the DAX matched reality
and the M documentation did not.**

I flagged in the report that the PBIX could not be opened and that anything
concerning its contents was unverified. P0-3 depended entirely on the PBIX, and
I should have filed it as "verify" rather than as a blocking defect. Stating it
at P0 was more confidence than the evidence carried.

## What this does and does not change

**Unchanged — still verified, still correct:**

- Everything proven by `validate_dataset.py`, which passed against the raw data:
  the 14,206-flight threshold error, all four status counts, the 72.9%
  controllable-delay figure, the cancellation-code reconciliation.
- The dashboard defect and its fix. `build_dashboard.py` ran successfully and
  produced 79.63% / 78.26%.
- Every finding about the M scripts *as documentation*: the hardcoded path, the
  wrong threshold in the header comment, the inconsistent `Airline Short Name`
  logic, the Departure Hour claim, the incremental-refresh claim.
- The three-conflicting-on-time-rates finding, which was the most serious issue
  and is independent of column naming.

**Now known to be wrong:**

- P0-3 in the review report, and the "[P0-1/2/3/4] column name fixed" comments
  in `measures.dax` and `deploy_measures.csx`.

**Now known, newly:**

- Two measures on the `flights` table carry error icons in the Data pane
  (`% Canc…`, `% Delay…`). Those are genuinely broken and need diagnosis.
- Measures are split across two homes: `#Measures` and the `flights` table.
  Consolidating them into one table is worth doing.
- The PBIX is 44 MB, not the 60–120 MB the report estimated. Still above
  GitHub's 50 MB warning threshold is false — 44 MB is under it. It remains an
  undiffable binary and still should not be committed, but the size claim in the
  report was wrong.

## Decision taken: keep the raw names

**The model stays as it is. The documentation was corrected to match it.**

Rationale: renaming the dimension columns now would mean reapplying Power Query
steps against a 1.9M-row model, updating every measure, and repairing every
visual bound to the old names — high risk for a purely cosmetic gain. Friendly
labels are available with zero risk through Model view display names, which
change what the reader sees without rebinding any DAX. Separating the physical
name from the display name is standard practice.

### Applied

- `src/dax/measures.dax` — rebound to `flights`, `airlines[AIRLINE]`,
  `airports[AIRPORT]`, `cancellation_codes[CANCELLATION_REASON]`, hosted in
  `#Measures`. Every genuine improvement is retained: the two explicitly named
  on-time measures, `CALCULATE` instead of `AVERAGEX` for the rolling average,
  the `NOT ISBLANK` guard on `Worst Airline`, the ranking volume floor, both
  MoM guards, and the four `Check` measures.
- `src/powerquery/m-scripts.pq` — all three rename steps removed, `Airline
  Short Name` and `Airport Label` removed, relationships restated against the
  real column names, naming policy stated at the top.

### Still to do

## Remaining work

1. Capture the complete, exact column list for all five tables — best done from
   a `.pbip` save, where the model becomes plain-text TMDL.
2. Rebind `measures.dax` and `deploy_measures.csx` to those names.
3. Decide on the naming convention deliberately: either keep raw names
   everywhere and correct the M documentation to match, or apply the renames the
   M script describes and update the DAX. **Pick one and write it down.** The
   current state — documentation describing one model, implementation being
   another — is the underlying problem, and it is real regardless of which
   direction the fix goes.
4. Delete `Flight Status  S.pbix` — an accidental copy created during this
   session by a Save-as dialog that fired before the file-type dropdown applied.

## Lesson for the repo

`docs/data-lineage.md` claims each rule has exactly one home. That is now true
for the Python side and for the data. It was never true for the *model
documentation*, and this correction is the proof. A document describing a model
is not a model. Generate the documentation from the model, or verify it against
the model on a schedule — do not hand-maintain both.
