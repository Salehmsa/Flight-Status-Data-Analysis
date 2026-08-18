# KPI Definitions

Every published KPI: its formula, its **denominator**, the business question it
answers, and the mistake it is designed to prevent.

The denominator column exists because this project previously published three
different values for a metric called "On Time %". Any KPI whose denominator is
not written down will eventually be computed two ways.

---

## Primary KPIs

### On Time % (Completed) — 79.6%

```
DIVIDE( [On Time Flights], [Completed Flights] )
      = 1,525,904 / 1,916,166
```

**Denominator:** flights that actually operated (total − cancelled − diverted).
**Answers:** of the flights we operated, how many landed on time?
**Use for:** operational performance, month-over-month trending, airport
comparison, the report headline.
**Why the denominator excludes cancelled and diverted:** those rows carry a null
`ARRIVAL_DELAY`. They have no punctuality outcome at all, so including them in a
punctuality denominator measures nothing and depresses the rate arbitrarily.

### On Time % (Scheduled) — 78.3%

```
DIVIDE( [On Time Flights], [Total Flights] )
      = 1,525,904 / 1,949,742
```

**Denominator:** every flight in the published schedule.
**Answers:** of the flights a passenger could have booked, how many arrived on
time?
**Use for:** carrier league tables and any customer-facing claim.
**Why it exists:** without it, an airline can improve its on-time score by
cancelling its weakest flights. American Eagle cancels 4.84% of its schedule
against Delta's 0.35% — on the Completed basis, that difference is invisible.

> **Rule:** never publish a measure named simply "On Time %". Both rates are
> correct; only one answers a given question.

---

## Rate KPIs

| KPI | Formula | Denominator | Value |
|---|---|---|---|
| Delay Rate % | `Delayed ÷ Completed` | Completed | 20.4% |
| Cancellation Rate % | `Cancelled ÷ Total` | **Total** | 1.47% |
| Diverted Rate % | `Diverted ÷ Total` | **Total** | 0.26% |
| Disruption Rate % | `(Delayed + Cancelled + Diverted) ÷ Total` | **Total** | 21.7% |
| Cancellations per 1,000 | `(Cancelled ÷ Total) × 1000` | Total | 14.7 |

**The denominators differ on purpose.** Delay is a property of a flight that
operated, so it is measured against flights that operated. A cancellation is a
broken promise, so it is measured against everything that was promised. Mixing
the two is the most common error in aviation reporting.

**Invariant to assert on the validation page:**
`On Time % (Completed) + Delay Rate % = 100.0%` exactly.

---

## Delay magnitude

| KPI | Formula | Value | Caution |
|---|---|---|---|
| Avg Arrival Delay | `AVERAGE(ARRIVAL_DELAY)` | +5.8 min | Strongly right-skewed. **Never show without the median.** |
| Median Arrival Delay | `MEDIAN(ARRIVAL_DELAY)` | −4 min | Most flights arrive *early*. Expensive over 1.9M rows — keep it on a card, never in a matrix. |
| Avg Delay (Delayed Only) | `AVERAGE` filtered to Delayed | — | The honest answer to "when we're late, how late?" |
| Total Positive Delay Minutes | `SUM(ARRIVAL_DELAY)` where `> 0` | — | **Not comparable to Total Attributed Delay Min.** |
| Total Attributed Delay Min | Sum of the five reason columns | 22,302,095 | Covers only flights ≥15 min late. |

**Why two "total delay" figures exist and why they are named differently:**
*Total Positive Delay Minutes* counts every minute of positive arrival delay,
including flights 1–14 minutes late that carry no reason attribution. *Total
Attributed Delay Min* covers only the 390,262 flights at ≥15 minutes. They will
never reconcile. Two measures called "total delay" that do not tie is the fastest
way to lose a stakeholder's trust — hence the explicit names.

**Why `> 0` and not a plain SUM:** a plain sum lets early arrivals net off real
delays. An aircraft landing 20 minutes early does not refund a different
aircraft's 20-minute delay. Delay minutes are a cost, and costs do not cancel.

---

## Delay attribution — the headline

### Controllable Delay % — 72.9%

```
DIVIDE( [Airline Delay Min] + [Late Aircraft Delay Min],
        [Total Attributed Delay Min] )
      = 16,251,915 / 22,302,095
```

**Answers:** what share of delay minutes originate inside the airline's own
operation?

Airline delay is the carrier's own fault directly. Late-aircraft delay is the
knock-on effect of an aircraft arriving late from a previous leg — which is the
carrier's own delay, propagating. Air system, weather and security are external.

**Business reading:** at 72.9%, delay in this dataset is a scheduling and
turnaround problem, not a weather problem. That reframes the entire remediation
conversation: buffer time and turnaround discipline, not meteorology.

---

## Cancellation analysis

### Weather Cancellation % — 57.3%

```
DIVIDE( [Weather Cancellations], [Cancelled Flights] ) = 16,372 / 28,570
```

**Put this next to Controllable Delay % on the same page.** Weather causes 6.0%
of delay *minutes* but 57.3% of *cancellations*. Airlines absorb bad weather by
delaying; when a delay can no longer absorb it, they cancel. Two levers, two
narratives, one slide.

---

## Time intelligence

| KPI | Formula | Note |
|---|---|---|
| Flights PM | `CALCULATE([Total Flights], DATEADD(Date, -1, MONTH))` | |
| Flights MoM % | Guarded ratio | Guard **both** sides for blank, not just the prior period |
| On Time % MoM (pp) | `Current − Prior` | Percentage **points**. Labelling a 3.0pp move as "+3%" is wrong. |
| Rolling 3M On Time % | `CALCULATE(otp, DATESINPERIOD(...))` | Must be `CALCULATE`, not `AVERAGEX` — see below |
| Is Comparable Period | `1` if both periods have data | Filter every MoM visual on this |

**The rolling-average trap.** `AVERAGEX(DATESINPERIOD(...), [On Time %])` iterates
~90 *individual days* and returns the unweighted mean of 90 daily rates — a quiet
Tuesday with 4,000 flights counts the same as a Friday with 7,000. That is not a
three-month on-time rate. Use `CALCULATE` so the ratio is recomputed over the
whole window and correctly volume-weighted.

**The October gap.** October 2015 has zero rows. Every MoM measure will show a
false −100% collapse. Apply `[Is Comparable Period] = 1` or
`'Date Table'[Has Flight Data]` to every time-series visual.

---

## Ranking

| KPI | Note |
|---|---|
| Airline / Airport Rank by On Time | `RANKX(ALLSELECTED(...))` — `ALLSELECTED`, not `ALL`, so ranks respect page slicers |
| Best Airline / Worst Airline | Returns a **name**, for a card visual |
| Min Flights For Ranking | Volume floor, default 5,000 |

**Two traps, both of which shipped in v1:**

1. **`ALL` vs `ALLSELECTED`.** With `ALL`, a user who filters to five airlines
   still sees ranks out of fourteen. To them, that is a bug.
2. **Blank sorts lowest in an ascending `TOPN`.** Any airline excluded by a
   slicer returns `BLANK` for On Time % and was therefore reported to the
   executive as the *worst performing airline*. Guard with
   `NOT ISBLANK([On Time %])`.

**Why the volume floor.** Hawaiian flies 3,368 flights; Delta flies 352,114.
Ranking them on the same axis without a floor produces statistically meaningless
winners and losers. 5,000 is a judgement call — document it, expose it as a
parameter, and let the business move it.

---

## Business questions this model answers

Use these to drive page design. Each maps to KPIs above.

**Executive**
1. What share of our schedule did not go to plan? → Disruption Rate %
2. Are we above or below the 80% on-time benchmark? → On Time % + KPI Status Colour
3. Is performance improving? → On Time % MoM (pp), Rolling 3M

**Operational**
4. How much delay do we control? → Controllable Delay % (72.9%)
5. Which cause dominates right now, under this filter? → Top Delay Cause
6. When we're late, how late? → Avg Delay (Delayed Only), Delay Band
7. Do we recover delay in the air? → Avg Delay Recovery, Recovery Rate %

**Network**
8. Which hub is our weakest link? → Airport Rank by On Time
9. Which hour of the day breaks? → On Time % by Departure Hour
10. Which routes underperform? → On Time % by origin–destination

**Commercial**
11. Which carrier is most reliable to a passenger? → On Time % (Scheduled)
12. Who cancels rather than delays? → Cancellation Rate % vs Delay Rate %

## Suggested targets and thresholds

| KPI | Target | Amber | Red |
|---|---|---|---|
| On Time % (Completed) | ≥ 80% | 75–80% | < 75% |
| Cancellation Rate % | ≤ 1.0% | 1.0–2.0% | > 2.0% |
| Controllable Delay % | ≤ 65% | 65–75% | > 75% |
| Disruption Rate % | ≤ 18% | 18–22% | > 22% |

80% on-time is the commonly cited US industry benchmark. The remaining three are
proposed starting points derived from this dataset's own distribution, not
external standards — agree them with the business before publishing, and record
the agreement here.
