"""Load and merge Bulldyke Dataset sheets."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


DEFAULT_XLSX = Path(r"C:\Users\JakeR\Downloads\Game\Bulldyke Dataset.xlsx")


def _norm_yes(x: object) -> str | None:
    if pd.isna(x):
        return None
    s = str(x).strip()
    if s.lower() in ("yes", "y", "true", "1"):
        return "Yes"
    if s.lower() in ("no", "n", "false", "0"):
        return "No"
    return s


def load_dataset(xlsx_path: str | Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    path = Path(xlsx_path) if xlsx_path else DEFAULT_XLSX
    stats = pd.read_excel(path, sheet_name="Stats")
    const = pd.read_excel(path, sheet_name="Constant Attributes")
    yoy = pd.read_excel(path, sheet_name="YoY Attributes")

    yes_cols = [
        c
        for c in const.columns
        if c != "Person"
        and const[c].dtype == object
        and const[c].dropna().isin(["Yes", "No", "Unknown"]).any()
    ]
    for c in yes_cols:
        if c in ("Has or Had Asian Kink",):
            continue
        const[c] = const[c].apply(lambda v: _norm_yes(v) if _norm_yes(v) is not None else v)

    for c in ["Made Fantasy Playoffs", "Made Fantasy Championship Game"]:
        if c in yoy.columns:
            yoy[c] = yoy[c].apply(lambda v: _norm_yes(v) if _norm_yes(v) is not None else v)

    numeric_stats = [
        "Fantasy Wins",
        "Reg Season Fantasy PF",
        "Reg Season Fantasy PA",
        "College Quotes",
        "Bulldyke Roomates",
    ]
    for c in numeric_stats:
        if c in stats.columns:
            stats[c] = pd.to_numeric(stats[c], errors="coerce").fillna(0)

    return stats, const, yoy


def build_merged_frame(
    stats: pd.DataFrame,
    const: pd.DataFrame,
    yoy: pd.DataFrame,
) -> pd.DataFrame:
    m = pd.merge(stats, yoy, on=["Year", "Person"], how="inner", suffixes=("", "_yoy"))
    dup = [c for c in m.columns if c.endswith("_yoy")]
    m = m.drop(columns=dup, errors="ignore")
    m = m.merge(const, on="Person", how="left")
    return m
