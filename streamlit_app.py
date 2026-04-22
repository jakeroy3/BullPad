# streamlit"""Category grid game: Streamlit UI."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from data_loader import DEFAULT_XLSX, build_merged_frame, load_dataset
from rules import DEFAULT_GRID, score_label, validate_pick


def _init_state():
    if "guesses" not in st.session_state:
        st.session_state.guesses = 0
    if "score" not in st.session_state:
        st.session_state.score = 0.0
    if "filled" not in st.session_state:
        st.session_state.filled = {}


def _load_data(xlsx: Path):
    if "merged" not in st.session_state or st.session_state.get("xlsx_path") != str(xlsx):
        stats, const, yoy = load_dataset(xlsx)
        merged = build_merged_frame(stats, const, yoy)
        st.session_state.xlsx_path = str(xlsx)
        st.session_state.stats = stats
        st.session_state.const = const
        st.session_state.yoy = yoy
        st.session_state.merged = merged


def main():
    st.set_page_config(page_title="BullPad", layout="wide")
    _init_state()

    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.2rem; max-width: 1200px; }
        html, body, [class*="css"]  { background-color: #121212 !important; color: #e8e8e8 !important; }
        section[data-testid="stSidebar"] { background-color: #1a1a1a !important; }
        .brand { font-size: 2rem; font-weight: 800; letter-spacing: 0.04em; }
        .sub { color:#9aa0a6; font-size:0.92rem; }
        .metric { text-align:right; }
        .metric b { font-size: 1.35rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("Dataset")
        path_in = st.text_input("Excel path", value=str(DEFAULT_XLSX))
        xlsx = Path(path_in.strip())
        if not xlsx.is_file():
            st.error("File not found.")
            return
        if st.button("Reset board"):
            st.session_state.guesses = 0
            st.session_state.score = 0.0
            st.session_state.filled = {}
            st.rerun()

    _load_data(xlsx)
    merged = st.session_state.merged
    stats = st.session_state.stats
    const = st.session_state.const

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        st.markdown(
            '<div><div class="brand">CATEGORY</div>'
            '<div class="sub">Bulldyke grid &mdash; one person + year per row</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="metric"><div class="sub">TOTAL SCORE</div><b>{st.session_state.score:,.1f}</b><br/>'
            f'<span class="sub">{score_label()}</span></div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="metric"><div class="sub">TOTAL GUESSES</div><b>{st.session_state.guesses}</b></div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    for idx, row in enumerate(DEFAULT_GRID):
        rid = row.row_id
        if idx:
            st.markdown("")
        a, b, c, d = st.columns([1.15, 0.85, 1.55, 1.05])
        with a:
            st.markdown(f"**{row.team_label}**")
        with b:
            st.markdown(f"**{row.year_lo}–{row.year_hi}**")
            st.caption("Season window")
        with c:
            st.markdown(f"**{row.stat_title}**")
            st.caption(row.stat_subtitle)
        with d:
            if rid in st.session_state.filled:
                fp = st.session_state.filled[rid]
                st.success(f"**{fp['person']} ({fp['year']})**  \n+{fp['pts']:,.1f} pts")
            else:
                name_key = f"inp_name_{rid}"
                year_key = f"inp_year_{rid}"
                st.text_input("Person", key=name_key, placeholder="Name", label_visibility="collapsed")
                st.text_input("Year", key=year_key, placeholder="Year", label_visibility="collapsed")
                if st.button("Add player", key=f"btn_{rid}", type="primary"):
                    st.session_state.guesses += 1
                    name = (st.session_state.get(name_key) or "").strip()
                    year = (st.session_state.get(year_key) or "").strip()
                    ok, msg, pts = validate_pick(name, year, row, merged, stats, const)
                    if ok:
                        pick_key = f"{name}:{year}"
                        used = {f"{v['person']}:{v['year']}" for v in st.session_state.filled.values()}
                        if pick_key in used:
                            st.warning(f"{name} ({year}) is already used on another row.")
                        else:
                            st.session_state.filled[rid] = {"person": name, "year": year, "pts": pts}
                            st.session_state.score += pts
                            st.rerun()
                    else:
                        st.warning(msg)
        st.divider()

    with st.expander("Roster from spreadsheet"):
        st.write(", ".join(sorted(merged["Person"].unique())))

    st.caption("Edit grid rows in `bulldyke_grid/rules.py` (`DEFAULT_GRID`).")


if __name__ == "__main__":
    main()
