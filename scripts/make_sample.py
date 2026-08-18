#!/usr/bin/env python3
"""
make_sample.py — build a small, committable, statistically faithful sample.

WHY
---
flights.csv is roughly 290 MB. GitHub warns above 50 MB and hard-blocks pushes
above 100 MB. Committing it is not an option, and committing it via Git LFS
burns quota for a file that is freely downloadable from the original source.

The answer is a sample small enough to commit and honest enough that someone can
clone the repo, open the model, and see a working report without downloading
anything.

STRATIFICATION
--------------
A naive random sample would under-represent Hawaiian (3,368 flights) and destroy
the cancellation mix — code D has 2 rows in the entire dataset. This script
stratifies on MONTH x AIRLINE x Flight Status so every carrier, month and status
survives at proportional weight, then force-keeps all rare cancellation codes.

Classification comes from flight_rules.py. It is not reimplemented here.

USAGE
    python scripts/make_sample.py --data data/raw --out data/sample --n 50000
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flight_rules as fr  # noqa: E402

SEED = 42  # fixed, so the sample is reproducible and its diff is reviewable


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=Path("data/raw"))
    ap.add_argument("--out", type=Path, default=Path("data/sample"))
    ap.add_argument("--n", type=int, default=50_000,
                    help="target sample size (default 50,000 ~ 8 MB)")
    args = ap.parse_args()

    src = args.data / "flights.csv"
    if not src.exists():
        print(f"ERROR: {src} not found. See README > Getting the data.")
        return 1

    print(f"Reading {src} ...")
    df = fr.load_flights(src)
    print(f"Loaded {len(df):,} rows")

    df["_status"] = fr.flight_status(df)
    frac = args.n / len(df)

    # Collect indices per stratum rather than using groupby.apply.
    # groupby.apply(lambda g: g.sample(...)) raises a FutureWarning in pandas 2.x
    # and the suggested fix, include_groups=False, would silently DROP the
    # grouping columns (MONTH, AIRLINE) from the sampled rows — which is exactly
    # the opposite of what a data sample needs. Working with indices sidesteps
    # the deprecation entirely and is easier to read.
    keep = []
    for _, g in df.groupby(["MONTH", "AIRLINE", "_status"], observed=True):
        n = min(len(g), max(1, round(len(g) * frac)))
        keep.append(g.sample(n=n, random_state=SEED).index)

    sample = df.loc[np.concatenate(keep)]

    # Force-keep the rarest cancellation code. D has 2 rows in 1.9M; proportional
    # sampling drops it and the cancellation-reason visual silently loses a
    # category — which looks like a chart bug, not a sampling artefact.
    rare = df[df["CANCELLATION_REASON"] == "D"]
    sample = pd.concat([sample, rare]).drop_duplicates()
    sample = sample.drop(columns=["_status"]).sort_index()

    args.out.mkdir(parents=True, exist_ok=True)
    dest = args.out / "flights_sample.csv"
    sample.to_csv(dest, index=False)
    size_mb = dest.stat().st_size / 1024 / 1024
    print(f"\nWrote {dest}  ({len(sample):,} rows, {size_mb:.1f} MB)")

    # Report fidelity so the README can quote it, rather than claiming
    # "representative" with nothing behind the word.
    print("\nFidelity (full -> sample):")
    for col in ("AIRLINE", "ORIGIN_AIRPORT", "MONTH", "CANCELLATION_REASON"):
        print(f"  {col:<22} {df[col].nunique():>4} -> {sample[col].nunique():>4} distinct")

    full = fr.enrich(df)
    samp = fr.enrich(sample)
    print(f"  {'On-time % (completed)':<22} "
          f"{fr.on_time_pct_completed(full):>6.2f} -> {fr.on_time_pct_completed(samp):>6.2f}")
    print(f"  {'On-time % (scheduled)':<22} "
          f"{fr.on_time_pct_scheduled(full):>6.2f} -> {fr.on_time_pct_scheduled(samp):>6.2f}")

    if size_mb > 45:
        print("\nWARNING: sample exceeds 45 MB. GitHub warns at 50 MB. Lower --n.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
