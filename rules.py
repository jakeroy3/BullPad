"""Row rules and validation for the category grid."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import pandas as pd

Constraint = dict[str, Any]


@dataclass(frozen=True)
class TeamFilter:
    kind: Literal["grew_up", "lived_eoy", "constant_col"]
    value: Any


@dataclass(frozen=True)
class GridRow:
    row_id: str
    team_label: str
    stat_title: str
    stat_subtitle: str
    year_lo: int
    year_hi: int
    team: TeamFilter
    constraint: Constraint


DEFAULT_GRID: list[GridRow] = [
    GridRow(
        row_id="r1",
        team_label="Grew up: MA",
        stat_title="SEASON FANTASY WINS OVER 7",
        stat_subtitle="FOR CHOSEN YEAR",
        year_lo=2020,
        year_hi=2025,
        team=TeamFilter("grew_up", "MA"),
        constraint={"type": "season_stat", "column": "Fantasy Wins", "op": ">", "value": 7},
    ),
    GridRow(
        row_id="r2",
        team_label="Lived: Smithfield",
        stat_title="MADE FANTASY PLAYOFFS",
        stat_subtitle="SAME SEASON AS LOCATION",
        year_lo=2017,
        year_hi=2021,
        team=TeamFilter("lived_eoy", "Smithfield"),
        constraint={
            "type": "same_season_yoy",
            "column": "Made Fantasy Playoffs",
            "value": "Yes",
        },
    ),
    GridRow(
        row_id="r3",
        team_label="Attended '23 Nashville Trip",
        stat_title="FANTASY CHAMPION",
        stat_subtitle="ANYTIME (CONSTANT)",
        year_lo=2023,
        year_hi=2025,
        team=TeamFilter("constant_col", {"column": "On 2023 Nashville Trip?", "value": "Yes"}),
        constraint={"type": "constant_eq", "column": "Fantasy Championship?", "value": "Yes"},
    ),
    GridRow(
        row_id="r4",
        team_label="Major: Accounting",
        stat_title="SEASON COLLEGE QUOTES UNDER 40",
        stat_subtitle="FOR CHOSEN YEAR",
        year_lo=2018,
        year_hi=2022,
        team=TeamFilter("constant_col", {"column": "Primary Major", "value": "Accounting"}),
        constraint={"type": "season_stat", "column": "College Quotes", "op": "<", "value": 40},
    ),
    GridRow(
        row_id="r5",
        team_label="Grew up: CT",
        stat_title="MADE FANTASY PLAYOFFS",
        stat_subtitle="SAME SEASON (YoY)",
        year_lo=2025,
        year_hi=2025,
        team=TeamFilter("grew_up", "CT"),
        constraint={
            "type": "same_season_yoy",
            "column": "Made Fantasy Playoffs",
            "value": "Yes",
        },
    ),
]


def _team_ok_for_year(
    row: pd.Series,
    team: TeamFilter,
    const_row: pd.Series,
) -> bool:
    if team.kind == "grew_up":
        return str(const_row.get("Grew Up In", "")).strip() == team.value
    if team.kind == "lived_eoy":
        return str(row.get("Lived in (as of EOY)", "")).strip() == team.value
    if team.kind == "constant_col":
        # TeamFilter("constant_col", "Column Name") -> expects "Yes" by default
        # TeamFilter("constant_col", {"column": "...", "value": "..."}) -> explicit value
        if isinstance(team.value, str):
            col = team.value.strip()
            expected = "Yes"
        elif isinstance(team.value, dict):
            col = str(team.value.get("column", "")).strip()
            expected = team.value.get("value", "Yes")
        else:
            return False

        if not col:
            return False

        got = const_row.get(col)
        return _norm_yes_or_str(got) == _norm_yes_or_str(expected) or str(got).strip() == str(expected).strip()
    return False


def _norm_yes_or_str(v: object) -> str:
    if pd.isna(v):
        return ""
    s = str(v).strip()
    if s.lower() in ("yes", "y"):
        return "Yes"
    if s.lower() in ("no", "n"):
        return "No"
    return s


def _years_in_window(merged: pd.DataFrame, person: str, y_lo: int, y_hi: int) -> pd.DataFrame:
    return merged[(merged["Person"] == person) & (merged["Year"] >= y_lo) & (merged["Year"] <= y_hi)]


def _check_numeric_op(actual: float, op: str, expected: float) -> bool:
    if op == "<":
        return actual < expected
    if op == "<=":
        return actual <= expected
    if op == ">":
        return actual > expected
    if op == ">=":
        return actual >= expected
    raise ValueError(f"Unsupported operator: {op}")


def validate_pick(
    person: str,
    year: int | str,
    grid_row: GridRow,
    merged: pd.DataFrame,
    stats: pd.DataFrame,
    const: pd.DataFrame,
) -> tuple[bool, str, float]:
    person = person.strip()
    if not person:
        return False, "Enter a name.", 0.0

    people = set(merged["Person"].unique())
    if person not in people:
        close = [p for p in people if person.lower() in p.lower() or p.lower() in person.lower()]
        hint = f" Try: {', '.join(sorted(close))}." if close else f" Known: {', '.join(sorted(people))}."
        return False, f"Unknown person.{hint}", 0.0

    try:
        year_i = int(str(year).strip())
    except (TypeError, ValueError):
        return False, "Enter a valid year.", 0.0
    if not (grid_row.year_lo <= year_i <= grid_row.year_hi):
        return False, f"Year must be between {grid_row.year_lo} and {grid_row.year_hi}.", 0.0

    c_row = const[const["Person"] == person].iloc[0]
    season_rows = merged[(merged["Person"] == person) & (merged["Year"] == year_i)]
    if season_rows.empty:
        return False, f"No row found for {person} in {year_i}.", 0.0
    season_row = season_rows.iloc[0]

    team = grid_row.team
    if team.kind == "constant_col":
        if not _team_ok_for_year(season_row, team, c_row):
            return False, f"Must satisfy team rule: {grid_row.team_label}.", 0.0
    else:
        if not _team_ok_for_year(season_row, team, c_row):
            return False, f"Team/location rule failed: {grid_row.team_label}.", 0.0

    con = grid_row.constraint
    ctype = con["type"]

    if ctype == "constant_eq":
        col, val = con["column"], con["value"]
        got = c_row.get(col)
        if _norm_yes_or_str(got) == _norm_yes_or_str(val) or str(got).strip() == str(val).strip():
            pass
        else:
            return False, f"Constant '{col}' must be {val!r} (got {got!r}).", 0.0

    elif ctype == "season_stat":
        col, op, threshold = con["column"], con["op"], float(con["value"])
        actual = float(season_row[col])
        if not _check_numeric_op(actual, op, threshold):
            return False, f"{year_i} {col} is {actual}, need {op} {threshold}.", 0.0

    elif ctype == "same_season_yoy":
        col, val = con["column"], con["value"]
        got = season_row.get(col)
        if not (_norm_yes_or_str(got) == _norm_yes_or_str(val) or str(got).strip() == str(val).strip()):
            return False, f"In {year_i}, '{col}' must be {val!r} (got {got!r}).", 0.0

    else:
        return False, f"Unknown constraint {ctype}", 0.0

    score = float(season_row["Reg Season Fantasy PF"])
    return True, "Valid pick.", score


def score_label() -> str:
    return "REG SEASON FANTASY PF (CHOSEN YEAR)"
