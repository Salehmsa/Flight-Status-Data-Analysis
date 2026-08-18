#!/usr/bin/env python3
"""
validate_dataset.py — recompute every published figure and assert it.

WHY THIS FILE EXISTS
--------------------
v1 of this project published three different on-time rates for the same
dataset. That happened because the numbers were computed once, by hand, and
then copied into documentation, where they quietly went stale and drifted.

This script recomputes every figure from flights.csv and asserts it against the
baselines in flight_rules.py. Run it before every commit. If a number in the
README does not survive this script, the README is wrong.

Every rule it applies is imported from flight_rules.py — it does not carry its
own copy of the on-time threshold, which is precisely the mistake that produced
the original defect.

USAGE
    pip install pandas
    python scripts/validate_dataset.py --data data/raw
    python scripts/validate_dataset.py --data data/raw --json out/baselines.json

EXIT CODES
    0  every assertion passed
    1  at least one failed — wire this into CI
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flight_rules as fr  # noqa: E402

USECOLS = [
    "YEAR", "MONTH", "DAY", "DAY_OF_WEEK", "AIRLINE",
    "ORIGIN_AIRPORT", "DESTINATION_AIRPORT",
    "SCHEDULED_DEPARTURE", "DEPARTURE_DELAY", "ARRIVAL_DELAY", "DISTANCE",
    "DIVERTED", "CANCELLED", "CANCELLATION_REASON",
    *fr.CAUSE_COLUMNS.values(),
]

failures: list[str] = []
results: dict[str, object] = {}


def check(name: str, actual, expected, tol: float = 0.0) -> None:
    ok = abs(float(actual) - float(expected)) <= tol
    results[name] = {"actual": actual, "expected": expected, "pass": ok}
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:<32} "
          f"{actual:>14,.6g}  expected {expected:>14,.6g}")
    if not ok:
        failures.append(name)


def info(name: str, value, note: str = "") -> None:
    results[name] = value
    print(f"  [INFO] {name:<32} {value:>14,.6g}  {note}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=Path("data/raw"))
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args()

    path = args.data / "flights.csv"
    if not path.exists():
        print(f"ERROR: {path} not found.")
        print("       flights.csv is ~290 MB and is NOT committed to this repo.")
        print("       See README > Getting the data.")
        return 1

    print(f"\nReading {path} ...")
    df = fr.load_flights(path, usecols=USECOLS)
    df = fr.enrich(df)
    print(f"Loaded {len(df):,} rows\n")

    B, R = fr.BASELINES, fr.RATE_BASELINES
    status = df["Flight Status"]

    # -----------------------------------------------------------------------
    print("SECTION 1  Status classification")
    total = len(df)
    n_on_time   = int((status == "On Time").sum())
    n_delayed   = int((status == "Delayed").sum())
    n_cancelled = int((status == "Cancelled").sum())
    n_diverted  = int((status == "Diverted").sum())
    n_unknown   = int((status == "Unknown").sum())
    n_completed = total - n_cancelled - n_diverted

    check("total_flights",     total,       B["total_flights"])
    check("on_time_flights",   n_on_time,   B["on_time_flights"])
    check("delayed_flights",   n_delayed,   B["delayed_flights"])
    check("cancelled_flights", n_cancelled, B["cancelled_flights"])
    check("diverted_flights",  n_diverted,  B["diverted_flights"])
    check("completed_flights", n_completed, B["completed_flights"])

    # If this is non-zero, an operated flight has a NULL ARRIVAL_DELAY and every
    # punctuality denominator in the model needs revisiting before publication.
    check("unknown_status", n_unknown, B["unknown_status"])

    # The four statuses must partition the table exactly.
    check("status_partition_residual",
          total - (n_on_time + n_delayed + n_cancelled + n_diverted + n_unknown), 0)

    # Proof of the threshold, not an assertion about it: the count of flights at
    # exactly 15 minutes is the exact size of the error `> 15` would introduce.
    operated = ~status.isin(["Cancelled", "Diverted", "Unknown"])
    n_exactly15 = int((operated & (df["ARRIVAL_DELAY"] == 15)).sum())
    check("exactly_15_min_late", n_exactly15, B["exactly_15_min_late"])

    # -----------------------------------------------------------------------
    print("\nSECTION 2  Rate KPIs — both denominators, explicitly named")
    otp_completed = 100 * n_on_time / n_completed
    otp_scheduled = 100 * n_on_time / total
    delay_rate    = 100 * n_delayed / n_completed
    cancel_rate   = 100 * n_cancelled / total
    divert_rate   = 100 * n_diverted / total
    disruption    = 100 * (n_delayed + n_cancelled + n_diverted) / total

    check("on_time_pct_completed", otp_completed, R["on_time_pct_completed"], 0.01)
    check("on_time_pct_scheduled", otp_scheduled, R["on_time_pct_scheduled"], 0.01)
    check("delay_rate_pct",        delay_rate,    R["delay_rate_pct"],        0.01)
    check("cancellation_rate_pct", cancel_rate,   R["cancellation_rate_pct"], 0.01)
    check("diverted_rate_pct",     divert_rate,   R["diverted_rate_pct"],     0.01)
    check("disruption_rate_pct",   disruption,    R["disruption_rate_pct"],   0.01)
    check("rate_sum_residual",     otp_completed + delay_rate - 100, 0, 1e-9)

    # -----------------------------------------------------------------------
    print("\nSECTION 3  Delay attribution")
    sums = {name: float(df[col].sum()) for name, col in fr.CAUSE_COLUMNS.items()}
    check("air_system_delay_min",    sums["Air System"],    B["air_system_delay_min"])
    check("security_delay_min",      sums["Security"],      B["security_delay_min"])
    check("airline_delay_min",       sums["Airline"],       B["airline_delay_min"])
    check("late_aircraft_delay_min", sums["Late Aircraft"], B["late_aircraft_delay_min"])
    check("weather_delay_min",       sums["Weather"],       B["weather_delay_min"])

    attributed = sum(sums.values())
    check("total_attributed_min", attributed, B["total_attributed_min"])
    controllable = 100 * sum(sums[c] for c in fr.CONTROLLABLE_CAUSES) / attributed
    check("controllable_delay_pct", controllable, R["controllable_delay_pct"], 0.01)

    # The v1 docs claimed "the 5 reason columns sum exactly to ARRIVAL_DELAY
    # (verified 100%)" without showing the test. This is the test.
    attributed_rows = df["AIR_SYSTEM_DELAY"].notna()
    check("attribution_row_count", int(attributed_rows.sum()), n_delayed)

    row_sum = df.loc[attributed_rows, list(fr.CAUSE_COLUMNS.values())].sum(axis=1)
    check("attribution_row_mismatches",
          int((row_sum != df.loc[attributed_rows, "ARRIVAL_DELAY"]).sum()), 0)

    # NULLs must be preserved, not zero-filled.
    check("attribution_null_pct",
          100 * df["AIR_SYSTEM_DELAY"].isna().sum() / total, 79.98, 0.01)

    # -----------------------------------------------------------------------
    print("\nSECTION 4  Cancellation codes")
    vc = df.loc[status == "Cancelled", "CANCELLATION_REASON"].value_counts()
    for code in ("A", "B", "C", "D"):
        check(f"cancel_code_{code}", int(vc.get(code, 0)), B[f"cancel_code_{code}"])
    check("cancel_code_residual", n_cancelled - int(vc.sum()), 0)
    check("weather_cancel_pct", 100 * int(vc.get("B", 0)) / n_cancelled,
          R["weather_cancel_pct"], 0.01)

    # -----------------------------------------------------------------------
    print("\nSECTION 5  Coverage and cardinality")
    check("months_with_data", df["MONTH"].nunique(), B["months_with_data"])
    check("october_row_count", int((df["MONTH"] == 10).sum()), 0)
    check("distinct_departure_hours", df["Departure Hour"].nunique(),
          B["distinct_departure_hours"])
    check("distinct_origin_airports", df["ORIGIN_AIRPORT"].nunique(),
          B["distinct_origin_airports"])
    check("distinct_airlines", df["AIRLINE"].nunique(), B["distinct_airlines"])

    # Hours 03 and 04 hold zero flights. Real, not missing — but it means a
    # categorical X-axis will silently omit them.
    missing_hours = sorted(set(range(24)) - set(df["Departure Hour"].unique().tolist()))
    print(f"  [INFO] departure hours with zero flights: {missing_hours}")
    results["empty_departure_hours"] = missing_hours

    # ROOT-CAUSE PROBE FOR THE OCTOBER GAP.
    # The upstream Kaggle/DOT file encodes ORIGIN_AIRPORT as 5-digit numeric DOT
    # identifiers for part of the year instead of 3-letter IATA codes. If this
    # subset was built by filtering on ten IATA codes, October would have been
    # dropped silently rather than deliberately excluded.
    #
    # This subset contains only IATA codes, so the probe below will report zero.
    # RUN THE SAME PROBE AGAINST THE FULL UPSTREAM flights.csv to confirm the
    # cause, then record the result in docs/data-lineage.md. Until then the
    # explanation in the README is a hypothesis and is labelled as one.
    numeric = int(df["ORIGIN_AIRPORT"].astype(str).str.isdigit().sum())
    info("numeric_origin_codes", numeric, "run on the FULL upstream file to confirm")

    # -----------------------------------------------------------------------
    print("\nSECTION 6  Figures the v1 docs asserted without arithmetic")
    avg_arr = float(df["ARRIVAL_DELAY"].mean())
    avg_dep = float(df["DEPARTURE_DELAY"].mean())
    check("avg_arrival_delay",    avg_arr, 5.78, 0.05)
    check("avg_departure_delay",  avg_dep, 10.93, 0.05)
    check("median_arrival_delay", float(df["ARRIVAL_DELAY"].median()), -4.0, 0.01)

    # v1 derived "Avg Delay Recovery ~= 5.1" as 10.9 - 5.8. That subtraction is
    # invalid: the two means cover different row populations. Both are printed
    # so the size of the error is visible rather than argued about.
    rowwise = float(df["Delay Recovery"].mean())
    info("avg_delay_recovery_rowwise", rowwise, "correct")
    info("avg_delay_recovery_naive", avg_dep - avg_arr, "v1 method, invalid")

    # -----------------------------------------------------------------------
    print("\n" + "=" * 76)
    n_checks = sum(1 for v in results.values() if isinstance(v, dict))
    if failures:
        print(f"RESULT: {len(failures)} FAILED of {n_checks} assertions")
        for f in failures:
            print(f"  - {f}")
    else:
        print(f"RESULT: all {n_checks} assertions PASSED")
    print("=" * 76 + "\n")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(results, indent=2, default=str))
        print(f"Wrote {args.json}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
