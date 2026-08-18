<div align="center">

# Flight Operations Intelligence · 2015

**1.9 million US domestic flights, analysed end to end.**
Power Query → star schema → 58 DAX measures → executive report → automated validation.

[![Live Dashboard](https://img.shields.io/badge/▶_Live_Dashboard-0F4C81?style=for-the-badge)](https://salehmsa.github.io/Flight-Status-Data-Analysis/)
[![Power BI](https://img.shields.io/badge/Power_BI-F2C811?style=for-the-badge&logo=powerbi&logoColor=black)](src/dax/measures.dax)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](scripts/)
[![License](https://img.shields.io/badge/License-MIT-2E7D32?style=for-the-badge)](LICENSE)

</div>

---

## The finding

> ### 72.9% of all delay minutes are the airline's own doing.
> Weather explains just **6.0%**.

Delay in this dataset is a **scheduling and turnaround problem**, not a weather
problem — the airline's own delays plus the knock-on effect of aircraft arriving
late from a previous leg.

The mirror image makes it sharper: weather causes 6.0% of delay *minutes* but
**57.3%** of *cancellations*. Airlines absorb bad weather by delaying; when a
delay can no longer absorb it, they cancel. Two levers, two very different
stories.

| | |
|---|---|
| Flights analysed | **1,949,742** |
| On-time (operated basis) | **79.6%** |
| On-time (scheduled basis) | **78.3%** |
| Schedule disrupted | **21.7%** |
| Median arrival delay | **−4 min** |

*Most flights arrive early. The +5.8 min average is dragged positive by a small
tail of severe delays — which is why both numbers are always shown together.*

---

## What makes this different

Most portfolio projects show a dashboard. This one ships the **harness that
proves the dashboard is right**.

```bash
python scripts/validate_dataset.py --data data/raw
# RESULT: all 45 assertions PASSED
```

Every published figure is recomputed from the raw CSV and asserted on every run.
Exit code `1` fails the build. Inside Power BI, four `Check` measures must read
exactly `0` after every refresh.

**This was not decoration.** The harness caught three live defects that every
document in the project had missed:

| Defect | Scale |
|---|---|
| `Flight Status` classified with `> 15` instead of `>= 15` | 14,206 flights |
| `On Time Flights` filtered a column with a different standard entirely | 367,757 flights |
| `Completed Flights` returned more rows than the fact table holds | 401,334 rows |

All three produced numbers that looked perfectly reasonable on a card. Full
account in [`CHANGELOG.md`](CHANGELOG.md).

### One rule, one place

Every business rule — the on-time threshold, the delay bands, both denominators,
the published baselines — is defined **once per runtime**: in
`flights[Flight Status]` for the model, and in
[`scripts/flight_rules.py`](scripts/flight_rules.py) for everything in Python.
Nothing reimplements a rule.

That constraint exists because the original defect was a classification rule
written in two places that quietly drifted apart.

---

## Two on-time rates, two names

There is deliberately **no measure called "On Time %"** in this model.

| KPI | Denominator | Value | Answers |
|---|---|---|---|
| `On Time % (Completed)` | flights operated | **79.6%** | How did our operation perform? |
| `On Time % (Scheduled)` | flights promised | **78.3%** | What did the passenger experience? |

Use **Scheduled** for carrier league tables. Without it, an airline improves its
score by cancelling its weakest flights — American Eagle cancels 4.84% of its
schedule against Delta's 0.35%, and on the Completed basis that gap is invisible.

---

## Quick start

```bash
git clone https://github.com/Salehmsa/Flight-Status-Data-Analysis.git
cd Flight-Status-Data-Analysis
pip install -r requirements.txt
```

`flights.csv` is ~290 MB and is **not** committed. Download
[2015 Flight Delays and Cancellations](https://www.kaggle.com/datasets/usdot/flight-delays)
(CC0), filter to the ten hubs in `data/reference/airports.csv`, and place it at
`data/raw/flights.csv`. Then:

```bash
python scripts/validate_dataset.py --data data/raw   # 45 assertions
python scripts/build_dashboard.py  --data data/raw   # regenerate the dashboard
```

A **50,086-row stratified sample** is committed so you can explore without the
download. Fidelity: all 14 airlines, all 10 airports, all 11 months and all 4
cancellation codes survive; on-time rate 79.63% → 79.63%.

Rebuilding the Power BI model from scratch:
**[`docs/rebuild-guide.md`](docs/rebuild-guide.md)** (~40 min).

---

## Repository

```
├── src/
│   ├── powerquery/m-scripts.pq      5 queries, parameterised
│   └── dax/measures.dax             58 measures, 9 folders
├── scripts/
│   ├── flight_rules.py              ◄ single definition of every rule
│   ├── validate_dataset.py          45 assertions, CI-ready
│   ├── build_dashboard.py           regenerates the dashboard, refuses to
│   │                                  write on a failed assertion
│   └── make_sample.py               stratified committable sample
├── docs/                            dictionary · KPIs · lineage · model
│                                      design · rebuild · report build
└── data/
    ├── reference/                   3 dimension CSVs
    └── sample/                      50k stratified rows
```

**Model:** star schema, one 1.9M-row fact, four dimensions, all relationships
single-direction. Full rationale in
[`docs/model-design.md`](docs/model-design.md).

---

## Known limitations

Stated plainly — a limitation you disclose is a design decision; one you hide is
a defect.

**October 2015 is absent, and it is our fault.** October encodes airports as
five-digit DOT identifiers rather than IATA codes:

```
2015,9,1,2,NK,298,N624NK,LAS,IAH,...        ← September: IATA
2015,10,1,4,AA,1230,N3DBAA,14747,11298,...  ← October:  numeric
```

Filtering to ten IATA codes dropped the whole month silently. October is fully
present upstream. Recovery is deferred to v2.0 because it changes the row count
to ~2.1M and invalidates every baseline here.

**No destination dimension** — `DESTINATION_AIRPORT` has 273 values against a
10-airport reference, so routes render as raw codes. Fix planned for v1.1.

**No query folding, so no incremental refresh.** A CSV source cannot fold;
`RangeStart`/`RangeEnd` would cost a full file read and buy nothing. Deliberate
non-implementation, with three upgrade paths documented.

**Hours 03 and 04 have zero flights** — real, not missing. Which means a
categorical X axis silently omits them. Use a continuous axis.

---

## Privacy

No personal data of any kind: no passengers, crew, contacts or payments.
`TAIL_NUMBER` is an aircraft registration from a public FAA registry, and it is
dropped from the model regardless. Source is public-domain US government data.
No RLS — documented as a decision in
[`docs/model-design.md`](docs/model-design.md), not an omission.

## Stack

Power BI Desktop · Power Query (M) · DAX · VertiPaq · Python 3.10+ · pandas

## License

Code **MIT** ([`LICENSE`](LICENSE)) · Data **CC0**, US DOT Bureau of
Transportation Statistics

---

<div align="center">

**[Saleh Mahbub](https://github.com/Salehmsa)** · Data & BI

*Sources: [Kaggle / US DOT](https://www.kaggle.com/datasets/usdot/flight-delays) ·
[Airport code encoding](https://www.kaggle.com/code/smiller933/fixing-airport-codes)*

</div>
