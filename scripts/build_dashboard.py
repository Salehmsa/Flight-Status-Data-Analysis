#!/usr/bin/env python3
"""
build_dashboard.py — regenerate the HTML dashboard from source data.

WHY THIS SCRIPT REPLACED A HAND-BUILT DATA BLOB
-----------------------------------------------
The v1 dashboard carried a hand-generated aggregate blob built by code that had
its own copy of the on-time rule. That copy used `> 15` where the model used
`>= 15`, so the dashboard published 1,540,110 on-time flights against the
model's 1,525,904 — a 14,206-flight discrepancy, invisible to a reader, in the
project's most-viewed artefact.

The fix is not "correct the threshold". The fix is to delete the second copy of
the rule. This script imports every rule from flight_rules.py, recomputes every
aggregate, asserts the result against the published baselines, and only then
writes the blob into the HTML. If an assertion fails, nothing is written.

USAGE
-----
    pip install pandas
    python scripts/build_dashboard.py \
        --data data/raw \
        --template reports/Flight_Operations_Dashboard.html \
        --out reports/Flight_Operations_Dashboard.html

    # dry run — recompute and assert, write nothing
    python scripts/build_dashboard.py --data data/raw --check-only

EXIT CODES
    0  dashboard written (or check passed)
    1  a baseline assertion failed — nothing written
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flight_rules as fr  # noqa: E402

TOP_N_ROUTES = 15

USECOLS = [
    "YEAR", "MONTH", "DAY", "DAY_OF_WEEK", "AIRLINE",
    "ORIGIN_AIRPORT", "DESTINATION_AIRPORT",
    "SCHEDULED_DEPARTURE", "DEPARTURE_DELAY", "ARRIVAL_DELAY", "DISTANCE",
    "DIVERTED", "CANCELLED", "CANCELLATION_REASON",
    *fr.CAUSE_COLUMNS.values(),
]


# =============================================================================
# BUILD
# =============================================================================

def build_data(data_dir: Path) -> tuple[dict, list[str]]:
    """Recompute every aggregate. Returns (DATA, failures)."""
    df = fr.load_flights(data_dir / "flights.csv", usecols=USECOLS)
    df = fr.enrich(df)

    airlines = pd.read_csv(data_dir / "airlines.csv").set_index("IATA_CODE")
    airports = pd.read_csv(data_dir / "airports.csv").set_index("IATA_CODE")

    status = df["Flight Status"]
    total = len(df)
    n_on_time = int((status == "On Time").sum())
    n_delayed = int((status == "Delayed").sum())
    n_cancelled = int((status == "Cancelled").sum())
    n_diverted = int((status == "Diverted").sum())
    n_unknown = int((status == "Unknown").sum())
    n_completed = total - n_cancelled - n_diverted

    # ---- KPI block --------------------------------------------------------
    # Two on-time rates, both present, both named. The dashboard headline uses
    # the completed basis; the donut uses scheduled-basis shares so that its
    # four segments sum to 100 without lying about any of them.
    kpis = {
        "total_flights":     total,
        "completed_flights": n_completed,
        "on_time_flights":   n_on_time,

        "on_time_pct":           round(100 * n_on_time / n_completed, 2),
        "on_time_pct_scheduled": round(100 * n_on_time / total, 2),
        "delayed_pct":           round(100 * n_delayed / n_completed, 2),
        "cancelled_pct":         round(100 * n_cancelled / total, 2),
        "diverted_pct":          round(100 * n_diverted / total, 2),
        "disruption_pct":        round(100 * (n_delayed + n_cancelled + n_diverted) / total, 2),

        # Scheduled-basis shares — these four sum to 100 and drive the donut.
        "share_on_time":   round(100 * n_on_time / total, 2),
        "share_delayed":   round(100 * n_delayed / total, 2),
        "share_cancelled": round(100 * n_cancelled / total, 2),
        "share_diverted":  round(100 * n_diverted / total, 2),

        "avg_dep_delay":    round(float(df["DEPARTURE_DELAY"].mean()), 2),
        "avg_arr_delay":    round(float(df["ARRIVAL_DELAY"].mean()), 2),
        "median_arr_delay": float(df["ARRIVAL_DELAY"].median()),
        "avg_recovery":     round(float(df["Delay Recovery"].mean()), 2),
    }

    def group_block(by, extra=None):
        rows = []
        for key, g in df.groupby(by, observed=True, sort=False):
            # Cast the group key out of numpy — json.dumps cannot serialise
            # numpy.int64, and the failure surfaces far from its cause.
            k = int(key) if hasattr(key, "item") and not isinstance(key, str) else key
            row = {by: k}
            row.update(fr.summarise(g))
            if extra:
                extra(row, key, g)
            rows.append(row)
        return rows

    # ---- monthly ----------------------------------------------------------
    monthly = sorted(group_block("MONTH"), key=lambda r: r["MONTH"])

    # ---- airline ----------------------------------------------------------
    def add_airline_name(row, code, _g):
        row["name"] = airlines.loc[code, "AIRLINE"] if code in airlines.index else code

    airline = sorted(group_block("AIRLINE", add_airline_name),
                     key=lambda r: -r["total"])

    # ---- origin -----------------------------------------------------------
    def add_airport(row, code, _g):
        if code in airports.index:
            a = airports.loc[code]
            row.update(city=a["CITY"], name=a["AIRPORT"],
                       lat=float(a["LATITUDE"]), lon=float(a["LONGITUDE"]))
        else:
            row.update(city=code, name=code, lat=None, lon=None)

    origin = sorted(group_block("ORIGIN_AIRPORT", add_airport),
                    key=lambda r: -r["total"])

    # ---- day of week ------------------------------------------------------
    # DOW is 0-indexed Monday-first to match the dashboard's lookup table;
    # the source DAY_OF_WEEK is ISO 1-indexed Monday-first.
    dow = []
    for iso, g in sorted(df.groupby("DAY_OF_WEEK", observed=True)):
        row = {"DOW": int(iso) - 1, "day_name": fr.DAY_NAMES[int(iso)]}
        row.update(fr.summarise(g))
        dow.append(row)

    # ---- departure hour ---------------------------------------------------
    # Yields 22 entries, not 24. Hours 03 and 04 have no scheduled departures
    # from these ten hubs. A categorical X-axis will silently omit them and make
    # the overnight trough look continuous — the template uses a continuous axis.
    hour = []
    for h, g in sorted(df.groupby("Departure Hour", observed=True)):
        row = {"Departure Hour": int(h)}
        row.update(fr.summarise(g))
        hour.append(row)

    # ---- distance band ----------------------------------------------------
    distance = []
    for band, g in df.groupby("Distance Band", observed=True):
        row = {"Distance Band": band, "avg_distance": round(float(g["DISTANCE"].mean()))}
        row.update(fr.summarise(g))
        distance.append(row)
    distance.sort(key=lambda r: -r["total"])

    # ---- delay band -------------------------------------------------------
    band_order = ["On Time (<15)", "Minor (15-45)", "Major (46-120)",
                  "Severe (>120)", "N/A"]
    counts = df["Delay Band"].value_counts()
    delayband = [{"band": b, "count": int(counts.get(b, 0))} for b in band_order]

    # ---- cancellation reasons ---------------------------------------------
    cancelled_rows = df[status == "Cancelled"]
    vc = cancelled_rows["CANCELLATION_REASON"].value_counts()
    cancel_reason = [
        {"code": c, "count": int(vc.get(c, 0)), "desc": fr.CANCELLATION_REASONS[c]}
        for c in ("B", "A", "C", "D")
    ]

    # ---- delay causes -----------------------------------------------------
    causes = {name: float(df[col].sum()) for name, col in fr.CAUSE_COLUMNS.items()}
    attributed = sum(causes.values())
    causes_pct = {k: round(100 * v / attributed, 1) for k, v in causes.items()}

    # ---- top routes -------------------------------------------------------
    # Destination resolves to a raw IATA code whenever it is not one of the ten
    # hubs in airports.csv — a visible consequence of the origin-only dimension
    # decision. Documented in docs/model-design.md; fixed in v1.1 by loading the
    # full 322-row airport reference.
    routes = []
    for (o, d), g in df.groupby(["ORIGIN_AIRPORT", "DESTINATION_AIRPORT"], observed=True):
        routes.append({
            "ORIGIN_AIRPORT": o, "DESTINATION_AIRPORT": d,
            "total": len(g),
            "on_time": int((g["Flight Status"] == "On Time").sum()),
            "avg_arr_delay": round(float(g["ARRIVAL_DELAY"].mean()), 2),
            "on_time_pct": round(fr.on_time_pct_completed(g), 2),
            "origin_city": airports.loc[o, "CITY"] if o in airports.index else o,
            "dest_city":   airports.loc[d, "CITY"] if d in airports.index else d,
        })
    routes = sorted(routes, key=lambda r: -r["total"])[:TOP_N_ROUTES]

    airport_coords = {
        code: {"lat": float(a["LATITUDE"]), "lon": float(a["LONGITUDE"]),
               "city": a["CITY"]}
        for code, a in airports.iterrows()
    }

    # ---- assertions -------------------------------------------------------
    B, R = fr.BASELINES, fr.RATE_BASELINES
    checks = [
        ("total_flights",      total,       B["total_flights"],      0),
        ("on_time_flights",    n_on_time,   B["on_time_flights"],    0),
        ("delayed_flights",    n_delayed,   B["delayed_flights"],    0),
        ("cancelled_flights",  n_cancelled, B["cancelled_flights"],  0),
        ("diverted_flights",   n_diverted,  B["diverted_flights"],   0),
        ("completed_flights",  n_completed, B["completed_flights"],  0),
        ("unknown_status",     n_unknown,   B["unknown_status"],     0),
        ("total_attributed_min", attributed, B["total_attributed_min"], 0),
        ("months_with_data",   len(monthly), B["months_with_data"],  0),
        ("distinct_departure_hours", len(hour), B["distinct_departure_hours"], 0),
        ("distinct_airlines",  len(airline), B["distinct_airlines"],  0),
        ("distinct_origin_airports", len(origin), B["distinct_origin_airports"], 0),
        ("on_time_pct_completed", kpis["on_time_pct"], R["on_time_pct_completed"], 0.05),
        ("on_time_pct_scheduled", kpis["on_time_pct_scheduled"], R["on_time_pct_scheduled"], 0.05),
        ("cancellation_rate_pct", kpis["cancelled_pct"], R["cancellation_rate_pct"], 0.01),
        ("disruption_rate_pct",   kpis["disruption_pct"], R["disruption_rate_pct"], 0.05),
    ]
    for code in ("A", "B", "C", "D"):
        checks.append((f"cancel_code_{code}", int(vc.get(code, 0)),
                       B[f"cancel_code_{code}"], 0))

    # Invariants — these must hold regardless of what the data says.
    checks.append(("status_partition",
                   total - (n_on_time + n_delayed + n_cancelled + n_diverted + n_unknown), 0, 0))
    checks.append(("rate_sum",
                   kpis["on_time_pct"] + kpis["delayed_pct"] - 100, 0, 0.01))
    checks.append(("donut_sum",
                   sum(kpis[k] for k in ("share_on_time", "share_delayed",
                                         "share_cancelled", "share_diverted")) - 100, 0, 0.05))

    failures = []
    print("\nBaseline assertions")
    for name, actual, expected, tol in checks:
        ok = abs(float(actual) - float(expected)) <= tol
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:<28} {actual:>14,.4g} vs {expected:>14,.4g}")
        if not ok:
            failures.append(name)

    data = {
        "_meta": {
            "generated":       datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "generator":       "scripts/build_dashboard.py",
            "delay_threshold": fr.DELAY_THRESHOLD_MIN,
            "rule":            f"Delayed when ARRIVAL_DELAY >= {fr.DELAY_THRESHOLD_MIN} (US DOT)",
            # No semicolons in any string here: the template injector matches
            # `const DATA = {...};` non-greedily and a stray `};` inside the
            # blob would truncate the replacement.
            "otp_basis":       "on_time_pct fields use the COMPLETED denominator, share_* fields use SCHEDULED",
            "baselines_ok":    not failures,
        },
        "kpis": kpis, "monthly": monthly, "airline": airline, "origin": origin,
        "dow": dow, "hour": hour, "distance": distance, "delayband": delayband,
        "cancel_reason": cancel_reason, "causes": causes, "causes_pct": causes_pct,
        "routes": routes, "airport_coords": airport_coords,
    }
    return data, failures


# =============================================================================
# TEMPLATE PATCHING
# =============================================================================

#: Applied after the DATA blob is injected. Every patch is idempotent — running
#: the script twice produces the same file. `old` is matched literally.
PATCHES: list[tuple[str, str, str]] = [
    (
        "donut denominators",
        "    {value:k.on_time_pct, color:'var(--teal)', ar:'في الموعد', en:'On Time'},\n"
        "    {value:k.delayed_pct, color:'var(--amber)', ar:'متأخرة', en:'Delayed'},\n"
        "    {value:k.cancelled_pct, color:'var(--red)', ar:'ملغاة', en:'Cancelled'},\n"
        "    {value:k.diverted_pct, color:'var(--blue)', ar:'محوّلة', en:'Diverted'},",
        # A donut divides a whole into parts, so every part must share one
        # denominator. on_time_pct and delayed_pct are on the COMPLETED basis
        # and do not sum to 100 alongside the cancelled/diverted shares. The
        # share_* fields are all on the SCHEDULED basis, and they do.
        "    {value:k.share_on_time, color:'var(--teal)', ar:'في الموعد', en:'On Time'},\n"
        "    {value:k.share_delayed, color:'var(--amber)', ar:'متأخرة', en:'Delayed'},\n"
        "    {value:k.share_cancelled, color:'var(--red)', ar:'ملغاة', en:'Cancelled'},\n"
        "    {value:k.share_diverted, color:'var(--blue)', ar:'محوّلة', en:'Diverted'},",
    ),
    (
        "KPI labels state their denominator",
        "? ['إجمالي الرحلات','الالتزام بالمواعيد','متأخرة','ملغاة','محوّلة','متوسط تأخير الوصول']\n"
        "    : ['TOTAL FLIGHTS','ON-TIME PERFORMANCE','DELAYED','CANCELLED','DIVERTED','AVG ARRIVAL DELAY'];",
        "? ['إجمالي الرحلات','الالتزام بالمواعيد (المكتملة)','متأخرة (المكتملة)','ملغاة (المجدولة)','محوّلة (المجدولة)','متوسط تأخير الوصول']\n"
        "    : ['TOTAL FLIGHTS','ON-TIME % (COMPLETED)','DELAYED % (COMPLETED)','CANCELLED % (SCHEDULED)','DIVERTED % (SCHEDULED)','AVG ARRIVAL DELAY'];",
    ),
]

#: Injected just before </body>. Renders a loud banner if the DATA blob was not
#: produced by this script, or was produced by a run whose assertions failed.
#: The point is that a stale dashboard announces itself rather than looking fine.
INTEGRITY_GUARD = """
<script id="integrityGuard">
/* Data integrity guard — see scripts/build_dashboard.py.
   A dashboard whose numbers have drifted from the model should say so on its
   own face, not wait to be caught in a meeting. */
(function(){
  var EXPECTED = { total: 1949742, on_time_completed: 79.63, cancelled: 1.47 };
  var m = (typeof DATA !== 'undefined') ? DATA._meta : null;
  var k = (typeof DATA !== 'undefined') ? DATA.kpis : null;
  var problems = [];

  if (!m)                    problems.push('DATA was not produced by build_dashboard.py — the on-time rule cannot be verified.');
  else if (!m.baselines_ok)  problems.push('The last build failed its baseline assertions.');
  else if (m.delay_threshold !== 15) problems.push('Delay threshold is ' + m.delay_threshold + ', expected 15 (US DOT).');

  if (k) {
    if (k.total_flights !== EXPECTED.total)
      problems.push('Total flights ' + k.total_flights.toLocaleString() + ', expected ' + EXPECTED.total.toLocaleString() + '.');
    if (Math.abs(k.on_time_pct - EXPECTED.on_time_completed) > 0.05)
      problems.push('On-time % (completed) is ' + k.on_time_pct + '%, expected ' + EXPECTED.on_time_completed + '%.');
  }

  if (!problems.length) return;

  var bar = document.createElement('div');
  bar.setAttribute('dir','rtl');
  bar.style.cssText = 'position:sticky;top:0;z-index:9999;background:#8E1B1B;color:#fff;'
    + 'padding:14px 22px;font-family:"IBM Plex Sans Arabic",sans-serif;font-size:13.5px;line-height:1.7;'
    + 'border-bottom:3px solid #F0455C;';
  bar.innerHTML = '<strong>⚠ هذه اللوحة غير مُتحقَّق منها — لا تُنشر.</strong><br>'
    + problems.map(function(p){ return '· ' + p; }).join('<br>')
    + '<br><span style="opacity:.85">أعد التوليد: '
    + '<code style="background:rgba(255,255,255,.15);padding:1px 6px;border-radius:3px;direction:ltr;display:inline-block">'
    + 'python scripts/build_dashboard.py --data data/raw</code></span>';
  document.body.insertBefore(bar, document.body.firstChild);
})();
</script>
"""


def patch_template(html: str, data: dict) -> str:
    blob = json.dumps(data, ensure_ascii=False, separators=(", ", ": "))

    new_html, n = re.subn(r"const DATA = \{.*?\};",
                          lambda _: "const DATA = " + blob + ";",
                          html, count=1, flags=re.S)
    if n != 1:
        raise SystemExit("ERROR: could not locate `const DATA = {...};` in the template.")

    for label, old, new in PATCHES:
        if new in new_html:
            print(f"  [skip] {label} — already applied")
        elif old in new_html:
            new_html = new_html.replace(old, new, 1)
            print(f"  [ok]   {label}")
        else:
            print(f"  [WARN] {label} — anchor not found, patch NOT applied")

    if 'id="integrityGuard"' not in new_html:
        new_html = new_html.replace("</body>", INTEGRITY_GUARD + "\n</body>", 1)
        print("  [ok]   integrity guard injected")
    else:
        print("  [skip] integrity guard — already present")

    return new_html


# =============================================================================

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=Path("data/raw"))
    # docs/index.html is what GitHub Pages serves. The script patches the file
    # in place, so there is exactly ONE copy of the dashboard in the repo —
    # the live site and the committed artefact are the same bytes and cannot
    # drift apart.
    ap.add_argument("--template", type=Path, default=Path("docs/index.html"))
    ap.add_argument("--out", type=Path, default=None,
                    help="defaults to overwriting --template")
    ap.add_argument("--check-only", action="store_true",
                    help="recompute and assert, write nothing")
    args = ap.parse_args()

    if not (args.data / "flights.csv").exists():
        print(f"ERROR: {args.data / 'flights.csv'} not found.")
        print("       flights.csv is ~290 MB and is not committed. See README.")
        return 1

    print(f"Reading {args.data / 'flights.csv'} ...")
    data, failures = build_data(args.data)

    print()
    if failures:
        print(f"BUILD ABORTED — {len(failures)} assertion(s) failed:")
        for f in failures:
            print(f"  - {f}")
        print("\nNothing was written. Investigate before publishing anything.")
        return 1

    print("All assertions passed.")
    if args.check_only:
        return 0

    if not args.template.exists():
        print(f"ERROR: template not found at {args.template}")
        return 1

    print("\nPatching template")
    html = patch_template(args.template.read_text(encoding="utf-8"), data)

    out = args.out or args.template
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"\nWrote {out}  ({out.stat().st_size / 1024:.0f} KB)")
    print(f"On-time % (completed): {data['kpis']['on_time_pct']}%   "
          f"(scheduled): {data['kpis']['on_time_pct_scheduled']}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
