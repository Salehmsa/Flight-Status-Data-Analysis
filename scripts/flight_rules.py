"""
flight_rules.py — the single Python definition of every business rule.

WHY THIS MODULE EXISTS
----------------------
The v1 project classified flights in two places: once in Power Query and once
inside the dashboard's generation code. The two copies diverged — the dashboard
used `> 15` where Power Query used `>= 15` — and the project shipped two
different on-time counts, 14,206 apart, without anyone noticing.

A classification rule written twice will diverge. This module is the one Python
definition; `build_dashboard.py`, `validate_dataset.py` and `make_sample.py` all
import from here and none of them reimplement it. Power Query holds the
equivalent definition for the model, in `Flights[Flight Status]`, and the two
are asserted against the same published baselines.

If you change a rule, change it here, then run validate_dataset.py.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# =============================================================================
# THE RULES
# =============================================================================

#: US DOT counts a flight as on time only if it arrives LESS THAN this many
#: minutes late. The comparison is therefore `>= DELAY_THRESHOLD_MIN` for
#: "delayed", NOT `> 15`.
#:
#: This single character is load-bearing: 14,206 flights arrived at exactly 15
#: minutes. `> 15` moves all of them into On Time.
DELAY_THRESHOLD_MIN = 15

#: The five reason columns, in the order they are reported.
CAUSE_COLUMNS = {
    "Air System":    "AIR_SYSTEM_DELAY",
    "Security":      "SECURITY_DELAY",
    "Airline":       "AIRLINE_DELAY",
    "Late Aircraft": "LATE_AIRCRAFT_DELAY",
    "Weather":       "WEATHER_DELAY",
}

#: Airline delay is the carrier's own fault directly; late-aircraft delay is
#: that same fault propagating from a previous leg. Both are inside the
#: airline's control. Air system, weather and security are not.
CONTROLLABLE_CAUSES = ("Airline", "Late Aircraft")

CANCELLATION_REASONS = {
    "A": "Airline/Carrier",
    "B": "Weather",
    "C": "National Air System",
    "D": "Security",
    "N": "Not Cancelled",
}

#: ISO convention, matching the source DAY_OF_WEEK column: 1 = Monday.
#: Power BI's default WEEKDAY() starts at Sunday = 1; mixing the two shifts
#: every day-of-week chart by one position.
DAY_NAMES = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu",
             5: "Fri", 6: "Sat", 7: "Sun"}


# =============================================================================
# DERIVED COLUMNS — mirrors src/powerquery/m-scripts.pq Query 4
# =============================================================================

def flight_status(df: pd.DataFrame) -> pd.Series:
    """Classify every flight. Mirrors Flights[Flight Status] exactly.

    Order matters: cancelled and diverted are checked first because those rows
    carry a NULL ARRIVAL_DELAY and have no punctuality outcome at all.
    """
    return pd.Series(
        np.select(
            [
                df["CANCELLED"] == 1,
                df["DIVERTED"] == 1,
                df["ARRIVAL_DELAY"].isna(),
                df["ARRIVAL_DELAY"] >= DELAY_THRESHOLD_MIN,
            ],
            ["Cancelled", "Diverted", "Unknown", "Delayed"],
            default="On Time",
        ),
        index=df.index,
    )


def delay_band(df: pd.DataFrame) -> pd.Series:
    """Severity band. Boundaries match the labels exactly — a flight at 15 min
    is Minor, not On Time, which is the same `>=` decision as flight_status."""
    d = df["ARRIVAL_DELAY"]
    return pd.Series(
        np.select(
            [d.isna(), d < 15, d <= 45, d <= 120],
            ["N/A", "On Time (<15)", "Minor (15-45)", "Major (46-120)"],
            default="Severe (>120)",
        ),
        index=df.index,
    )


def distance_band(df: pd.DataFrame) -> pd.Series:
    """Haul length. Note the boundary: exactly 1500 miles is Long Haul."""
    d = df["DISTANCE"]
    return pd.Series(
        np.select([d < 500, d < 1500], ["Short Haul", "Medium Haul"],
                  default="Long Haul"),
        index=df.index,
    )


def delay_recovery(df: pd.DataFrame) -> pd.Series:
    """Minutes made up in the air. Positive = recovered.

    NULL when either input is NULL, which is why this cannot be derived by
    subtracting two column means: those means cover different row populations.
    """
    return df["DEPARTURE_DELAY"] - df["ARRIVAL_DELAY"]


def departure_hour(df: pd.DataFrame) -> pd.Series:
    """Scheduled departure hour, 0-23, from the HHMM integer.

    Yields 22 distinct values, not 24 — hours 03 and 04 hold zero flights
    across all ten hubs. That is real, not missing data.
    """
    return (df["SCHEDULED_DEPARTURE"] // 100) % 24


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Attach every derived column in one pass. Returns a new frame."""
    out = df.copy()
    out["Flight Status"] = flight_status(out)
    out["Delay Band"] = delay_band(out)
    out["Distance Band"] = distance_band(out)
    out["Delay Recovery"] = delay_recovery(out)
    out["Departure Hour"] = departure_hour(out)
    return out


# =============================================================================
# KPIs — every denominator is explicit, because that is where v1 went wrong
# =============================================================================

def on_time_pct_completed(g: pd.DataFrame) -> float:
    """OPERATIONAL KPI. Denominator = flights that actually operated.

    Answers: "of the flights we operated, how many landed on time?"
    """
    completed = (g["Flight Status"] != "Cancelled") & (g["Flight Status"] != "Diverted")
    denom = int(completed.sum())
    if denom == 0:
        return float("nan")
    return 100.0 * int((g["Flight Status"] == "On Time").sum()) / denom


def on_time_pct_scheduled(g: pd.DataFrame) -> float:
    """CUSTOMER KPI. Denominator = every flight in the published schedule.

    Answers: "of the flights a passenger could book, how many arrived on time?"

    Always lower than the completed basis, because it charges cancellations and
    diversions against the carrier. Use this one for league tables: without it,
    an airline improves its score by cancelling its weakest flights.
    """
    if len(g) == 0:
        return float("nan")
    return 100.0 * int((g["Flight Status"] == "On Time").sum()) / len(g)


def summarise(g: pd.DataFrame) -> dict:
    """Standard aggregate block used by every grouping in the dashboard."""
    status = g["Flight Status"]
    n_cancelled = int((status == "Cancelled").sum())
    n_diverted = int((status == "Diverted").sum())
    return {
        "total":        len(g),
        "on_time":      int((status == "On Time").sum()),
        "delayed":      int((status == "Delayed").sum()),
        "cancelled":    n_cancelled,
        "diverted":     n_diverted,
        "completed":    len(g) - n_cancelled - n_diverted,
        "avg_arr_delay": round(float(g["ARRIVAL_DELAY"].mean()), 2),
        "avg_dep_delay": round(float(g["DEPARTURE_DELAY"].mean()), 2),
        "on_time_pct":  round(on_time_pct_completed(g), 2),
        "on_time_pct_scheduled": round(on_time_pct_scheduled(g), 2),
        "cancelled_pct": round(100.0 * n_cancelled / len(g), 2) if len(g) else 0.0,
    }


# =============================================================================
# PUBLISHED BASELINES — asserted everywhere, never retyped by hand
# =============================================================================

BASELINES = {
    "total_flights":           1_949_742,
    "on_time_flights":         1_525_904,
    "delayed_flights":           390_262,
    "cancelled_flights":          28_570,
    "diverted_flights":            5_006,
    "completed_flights":       1_916_166,
    "exactly_15_min_late":        14_206,
    "unknown_status":                  0,
    "cancel_code_A":               8_084,
    "cancel_code_B":              16_372,
    "cancel_code_C":               4_112,
    "cancel_code_D":                   2,
    "air_system_delay_min":    4_696_308,
    "security_delay_min":         25_717,
    "airline_delay_min":       7_542_717,
    "late_aircraft_delay_min": 8_709_198,
    "weather_delay_min":       1_328_155,
    "total_attributed_min":   22_302_095,
    "months_with_data":               11,
    "distinct_departure_hours":       22,
    "distinct_origin_airports":       10,
    "distinct_airlines":              14,
}

RATE_BASELINES = {
    "on_time_pct_completed":  79.63,
    "on_time_pct_scheduled":  78.26,
    "delay_rate_pct":         20.37,
    "cancellation_rate_pct":   1.47,
    "diverted_rate_pct":       0.26,
    "disruption_rate_pct":    21.74,
    "controllable_delay_pct": 72.87,
    "weather_cancel_pct":     57.30,
}


def load_flights(path, usecols=None) -> pd.DataFrame:
    """Read flights.csv and strip the ghost index column.

    The source CSV's first header cell is empty, so pandas names it
    'Unnamed: 0'. Its values run 1..5,819,074 — evidence that this file is a
    ten-airport subset of the full 5.8M-row source, not the source itself.
    """
    df = pd.read_csv(path, usecols=usecols, low_memory=False)
    return df.loc[:, ~df.columns.str.startswith("Unnamed")]
