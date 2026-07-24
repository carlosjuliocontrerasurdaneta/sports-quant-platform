"""Atomic CSV persistence shared by the historical stores.

Temp file + ``os.replace`` (atomic on the same volume): readers only ever see
the old file or the complete new one. results_/starters_/starter_fip_ and the
feature dataset are rebuilt only via slow re-fetches (ESPN, 365 days), so a
crash mid-write must never leave them truncated (audit 2026-07-24, I-2).
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd


def atomic_write_csv(df: pd.DataFrame, out: Path) -> None:
    tmp = out.with_suffix(out.suffix + ".tmp")
    try:
        df.to_csv(tmp, index=False)
        os.replace(tmp, out)
    finally:
        tmp.unlink(missing_ok=True)  # no-op after a successful replace
