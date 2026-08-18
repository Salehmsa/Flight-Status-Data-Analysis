# Report Build Guide

Five visible pages plus the hidden validation page. Build them in this order —
page 1 is the one a stakeholder sees first, and page 2 is the one that makes the
project memorable.

Every measure referenced here exists in the model and reconciles to the raw CSV.

---

## Before you place a single visual

**Theme.** View → Themes → Customize current theme. Set:

| Slot | Colour | Used for |
|---|---|---|
| Accent 1 | `#0F4C81` | neutral / totals |
| Positive | `#2E7D32` | on time |
| Warning | `#F9A825` | delayed |
| Negative | `#C62828` | cancelled |
| Info | `#5B8CFF` | diverted |

Fixing this once means every visual is consistent and you never pick a colour
again by hand.

**Canvas.** Format page → Canvas settings → 16:9, and set a page background of
`#F8FAFC` at 0% transparency. A pure-white canvas makes white cards invisible.

**Two things on every page:**

- A `Data Coverage Note` card, small, bottom-left, grey text. Never let a
  stakeholder discover the October gap on their own mid-meeting.
- The `Metric` field-parameter slicer if the page has a switchable visual.

---

## Page 1 — Executive Summary

*Answers: did the schedule hold, and are we above the industry benchmark?*

### Row 1 — five KPI cards

| Card | Measure | Format |
|---|---|---|
| Flights | `Total Flights` | 1,949,742 |
| On Time | `On Time % (Completed)` | 79.6% |
| Disrupted | `Disruption Rate %` | 21.7% |
| Cancelled | `Cancellation Rate %` | 1.47% |
| Avg Delay | `Avg Arrival Delay` | 5.8 min |

On the **On Time** card: Format → Callout value → Colour → *fx* → Format style
**Field value** → `KPI Status Colour`. It now turns green above the 80% target,
amber within 5 points, red below, and neutral grey when there is no data.

> Never rely on that colour alone. Roughly 8% of men have some colour vision
> deficiency. The number is right beside it, which is what actually carries the
> meaning.

### Row 2 — three visuals

**Donut — flight status split.** Legend `flights[Flight Status]`, Values
`Total Flights`. Set the four slice colours to match the theme. Detail labels:
*Category, percent of total*.

**Line — on-time trend.** X `'Date Table'[Month Name]`, Y
`On Time % (Completed)`. Add a constant line at `0.80` (Analytics pane → Constant
line → 0.8, dashed, grey, label "Target").

> **Filters pane → this visual → `Is Comparable Period` is 1.** Without it,
> October renders as a catastrophic collapse that never happened.

**Two cards side by side.** `Best Airline` and `Worst Airline`. These return
names, and both respect the 5,000-flight volume floor so a small carrier cannot
win on a thin margin.

### Row 3 — the median caveat

A card with `Median Arrival Delay` (−4 min) directly beside `Avg Arrival Delay`
(+5.8 min).

Put a text box under them: *"Most flights arrive early. The average is pulled
positive by a small tail of severe delays."* That single sentence is the
difference between a chart and an insight.

---

## Page 2 — Why Flights Are Late

*Answers: how much of this do we control? This is the page people remember.*

### The headline

One large card, `Controllable Delay %` → **72.9%**. Font size 60+.

Text box beneath: *"Of all attributed delay minutes, 72.9% originate inside the
airline's own operation — its own delays plus the knock-on effect of aircraft
arriving late from a previous leg. Delay here is a scheduling and turnaround
problem, not a weather problem."*

### The contrast — put these two side by side

| Visual | Measure | Reads |
|---|---|---|
| Card | `Controllable Delay %` | 72.9% |
| Card | `Weather Cancellation %` | 57.3% |

Text box between them: *"Weather causes 6.0% of delay minutes but 57.3% of
cancellations. Airlines absorb bad weather by delaying; when a delay can no
longer absorb it, they cancel. Two different levers."*

**This contrast is the single most interesting thing in the dataset, and it only
lands when the two numbers sit together.**

### Supporting visuals

**Bar — delay minutes by cause.** Build a small disconnected table, or simply
place the five measures in a clustered bar: `Late Aircraft Delay Min`,
`Airline Delay Min`, `Air System Delay Min`, `Weather Delay Min`,
`Security Delay Min`. Colour the first two (controllable) in one colour and the
last three in another. The visual then argues the 72.9% on its own.

**Column — delay severity.** X `flights[Delay Band]`, Y `Total Flights`.
Sort by severity, not alphabetically: create a sort column or set the sort in
the visual's ellipsis menu.

**Card — `Top Delay Cause`.** Dynamic. It re-ranks live as the user slices by
airport, month or carrier. Pair it with a slicer so people can play.

**Card — `Avg Attributed Delay per Delayed Flight`** → 57.1 min. Gives the
percentages a per-flight scale a person can hold.

---

## Page 3 — Network and Hubs

*Answers: where is our weakest link, and when does the day break?*

**Map.** Location `airports[AIRPORT]` (with Latitude/Longitude data categories
already set), Bubble size `Total Flights`, Colour saturation
`On Time % (Completed)`. Ten bubbles, sized by traffic, coloured by performance.

**Bar — hub ranking.** Y `airports[AIRPORT]`, X `On Time % (Completed)`, sorted
descending. Add `Airport Rank by On Time` as a tooltip.

**Column — on-time by hour.** X `flights[Departure Hour]`, Y
`On Time % (Completed)`.

> **Set the X axis to Continuous, not Categorical.** Hours 03 and 04 have zero
> flights — 22 distinct values, not 24. A categorical axis silently omits them
> and makes the overnight trough look continuous. This is a real trap and it is
> invisible once it happens.

The shape you will see: ~91% at 05:00 falling to ~72% by 20:00. Delay
accumulates through the day because aircraft carry it forward. That is the
late-aircraft effect from page 2, visible.

**Matrix — top routes.** Rows `flights[ORIGIN_AIRPORT]` and
`flights[DESTINATION_AIRPORT]`, Values `Total Flights`, `On Time % (Completed)`,
`Avg Arrival Delay`. Top 10 by flights.

> Destination shows as a raw IATA code — the origin-only dimension decision.
> Documented in `model-design.md`, fixed in v1.1.

---

## Page 4 — Carrier League Table

*Answers: which airline is actually most reliable to a passenger?*

**Bar — the league.** Y `airlines[AIRLINE]`, X **`On Time % (Scheduled)`**.

> Use the **Scheduled** basis here, not Completed. On the Completed basis an
> airline improves its score by cancelling its weakest flights. American Eagle
> cancels 4.84% of its schedule against Delta's 0.35%, and that difference is
> invisible unless you charge cancellations against the carrier.

**Scatter — volume vs reliability.** X `Total Flights`, Y
`On Time % (Scheduled)`, Size `Cancellation Rate %`, Legend `airlines[AIRLINE]`.
Small high-performers separate visually from large ones, which is exactly the
context the volume floor exists to protect.

**Table — carrier detail.** `airlines[AIRLINE]`, `Airline Rank by On Time`,
`Total Flights`, `On Time % (Scheduled)`, `On Time % (Completed)`,
`Cancellation Rate %`, `Avg Arrival Delay`.

Showing both on-time bases in one table, side by side, is the clearest possible
statement that they are different questions. Add both to the tooltip
descriptions so hovering explains the difference.

---

## Page 5 — Time Patterns

*Answers: when should we staff up?*

- **Line** — `On Time % (Completed)` by `'Date Table'[Month Name]`, with
  `Rolling 3M On Time %` as a second, lighter line. Filter
  `Is Comparable Period = 1`.
- **Column** — by `'Date Table'[Day Name]`. Already sorted by `ISO Weekday`.
  Saturday is the best day, Monday the worst.
- **Column** — by `'Date Table'[Season]`.
- **Card** — `On Time % MoM (pp)`. The name carries "(pp)" because it is a
  difference in percentage *points*. Labelling a 3.0pp move as "+3%" is wrong.

---

## Hidden page — Validation

Already built. Right-click the tab → **Hide page**.

Never delete it. It caught two defects in ten seconds that had cost hours to
find by hand.

---

## Accessibility — five minutes, do not skip

For each page:

1. **Alt text** on every visual: Format → General → Alt text. Describe the
   finding, not the chart type. *"On-time rate by hour, falling from 91% at 5am
   to 72% at 8pm"* — not *"column chart"*.
2. **Tab order**: Selection pane → Tab order. The default is creation order,
   which is almost never reading order.
3. **Contrast**: check any custom colour against a WCAG AA checker rather than
   by eye.
4. Never encode meaning in colour alone.

---

## Before you publish the report

- [ ] Every time-series visual filtered on `Is Comparable Period = 1`
- [ ] `Departure Hour` axis set to Continuous
- [ ] `Data Coverage Note` on every page
- [ ] Validation page hidden, not deleted
- [ ] `Controllable Delay %` and `Weather Cancellation %` on the same page
- [ ] Carrier league uses `On Time % (Scheduled)`
- [ ] Alt text on every visual
- [ ] File → Options → Current file → Report settings → **disable** "Persistent
      filters" if you want everyone to open on the same view
- [ ] View → Performance Analyzer → record. Any visual over 2 seconds gets
      documented or fixed. `Median Arrival Delay` is the usual suspect — keep it
      on a card, never in a matrix.
