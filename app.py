import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from src.f1_utils import (
    CURRENT_YEAR,
    TEAM_COLORS,
    get_event_schedule,
    load_session,
    get_driver_laps,
    compare_drivers_fastest,
    tyre_strategy,
    get_telemetry,
)
import src.openf1_client as openf1

# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="F1 Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Theme / CSS ───────────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
    /* Metric card value size */
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-size: 1.4rem;
        font-weight: 700;
    }
    /* Tighten sidebar spacing */
    section[data-testid="stSidebar"] .block-container { padding-top: 1rem; }
    /* Tab label weight */
    button[data-baseweb="tab"] { font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Constants ─────────────────────────────────────────────────────────────────

SESSION_TYPES = ["R", "Q", "FP1", "FP2", "FP3", "S", "SQ"]
SESSION_LABELS = {
    "R": "Race",
    "Q": "Qualifying",
    "FP1": "Practice 1",
    "FP2": "Practice 2",
    "FP3": "Practice 3",
    "S": "Sprint",
    "SQ": "Sprint Qualifying",
}
YEARS = list(range(CURRENT_YEAR, 2017, -1))

# ── Session state init ────────────────────────────────────────────────────────

for key, default in {
    "session": None,
    "session_meta": {},
    "drivers_available": [],
    "schedule": None,
    "openf1_sessions": None,
    "use_openf1": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("F1 Dashboard")
    st.divider()

    year = st.selectbox("Season", YEARS, index=0)

    # Decide data source: OpenF1 for current year, FastF1 for historical
    use_openf1 = year == CURRENT_YEAR
    st.caption(f"Source: {'OpenF1 (live)' if use_openf1 else 'FastF1 (historical)'}")

    # ── Event list ────────────────────────────────────────────────────────────

    @st.cache_data(show_spinner=False, ttl=3600)
    def fetch_schedule_ff1(yr: int) -> pd.DataFrame:
        return get_event_schedule(yr)

    @st.cache_data(show_spinner=False, ttl=300)
    def fetch_meetings_of1(yr: int) -> pd.DataFrame:
        return openf1.get_meetings(yr)

    with st.spinner("Loading calendar..."):
        if use_openf1:
            meetings_df = fetch_meetings_of1(year)
            if meetings_df.empty:
                st.warning("No OpenF1 meetings found for this year.")
                st.stop()
            event_options = meetings_df["meeting_name"].tolist()
            meeting_keys = meetings_df["meeting_key"].tolist()
        else:
            schedule_df = fetch_schedule_ff1(year)
            if schedule_df.empty:
                st.warning("No events found for this season.")
                st.stop()
            event_options = schedule_df["EventName"].tolist()

    selected_event_name = st.selectbox("Grand Prix", event_options)

    # ── Session type ──────────────────────────────────────────────────────────

    if use_openf1:
        meeting_key = meeting_keys[event_options.index(selected_event_name)]

        @st.cache_data(show_spinner=False, ttl=300)
        def fetch_of1_sessions(mk: int) -> pd.DataFrame:
            return openf1.get_sessions(mk)

        of1_sessions = fetch_of1_sessions(meeting_key)
        if of1_sessions.empty:
            st.info("No sessions available yet for this event.")
            st.stop()
        session_name_opts = of1_sessions["session_name"].tolist()
        session_keys_map = dict(zip(of1_sessions["session_name"], of1_sessions["session_key"]))
        selected_session_name = st.selectbox("Session", session_name_opts)
        openf1_session_key = session_keys_map[selected_session_name]
        fastf1_session_type = openf1.SESSION_TYPE_MAP.get(selected_session_name, "R")
    else:
        selected_session_type = st.selectbox(
            "Session",
            SESSION_TYPES,
            format_func=lambda x: SESSION_LABELS[x],
        )

    st.divider()
    load_btn = st.button("Load Session", type="primary", use_container_width=True)


# ── Session loader ────────────────────────────────────────────────────────────

def _session_changed(year, event, stype) -> bool:
    meta = st.session_state.session_meta
    return meta.get("year") != year or meta.get("event") != event or meta.get("stype") != stype


if load_btn:
    if use_openf1:
        event_key = selected_event_name
        stype_key = selected_session_name
    else:
        event_key = selected_event_name
        stype_key = selected_session_type

    if _session_changed(year, event_key, stype_key):
        st.session_state.session = None
        st.session_state.drivers_available = []

        with st.spinner(f"Loading {event_key} — {stype_key if not use_openf1 else stype_key}..."):
            try:
                if use_openf1:
                    drivers_df = openf1.get_drivers(openf1_session_key)
                    st.session_state.session = {
                        "type": "openf1",
                        "session_key": openf1_session_key,
                        "drivers_df": drivers_df,
                    }
                    st.session_state.drivers_available = (
                        drivers_df[["name_acronym", "full_name", "team_name"]]
                        .drop_duplicates("name_acronym")
                        .sort_values("name_acronym")["name_acronym"]
                        .tolist()
                    )
                else:
                    ff1_session = load_session(year, selected_event_name, selected_session_type)
                    st.session_state.session = {"type": "fastf1", "data": ff1_session}
                    st.session_state.drivers_available = sorted(
                        ff1_session.laps["Driver"].dropna().unique().tolist()
                    )
                st.session_state.session_meta = {
                    "year": year,
                    "event": event_key,
                    "stype": stype_key,
                    "label": f"{year} {event_key} — {SESSION_LABELS.get(stype_key, stype_key)}",
                }
            except Exception as exc:
                st.error(f"Failed to load session: {exc}")


# ── Main area ─────────────────────────────────────────────────────────────────

if st.session_state.session is None:
    st.info("Select a Grand Prix and session in the sidebar, then click **Load Session**.")
    st.stop()

meta = st.session_state.session_meta
st.header(meta.get("label", "Session"))

# Driver selector (rendered after session loads)
available = st.session_state.drivers_available
selected_drivers = st.multiselect(
    "Drivers",
    available,
    default=available[:5] if len(available) >= 5 else available,
)

if not selected_drivers:
    st.warning("Select at least one driver.")
    st.stop()

session_obj = st.session_state.session

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_class, tab_sectors, tab_speed, tab_tyres = st.tabs(
    ["Classification", "Sector Times", "Speed Trace", "Tyre Strategy"]
)

# ── Helper: format lap time ───────────────────────────────────────────────────

def fmt_laptime(seconds: float | None) -> str:
    if seconds is None or pd.isna(seconds):
        return "—"
    m, s = divmod(seconds, 60)
    return f"{int(m)}:{s:06.3f}"


# ── Tab 1: Classification ─────────────────────────────────────────────────────

with tab_class:
    if session_obj["type"] == "fastf1":
        ff1 = session_obj["data"]

        @st.cache_data(show_spinner=False)
        def build_classification(_session, drivers):
            return compare_drivers_fastest(_session, drivers)

        with st.spinner("Building classification..."):
            df = build_classification(ff1, tuple(selected_drivers))

        if df.empty:
            st.info("No lap data for selected drivers.")
        else:
            # Metric cards — top 3
            cols = st.columns(min(3, len(df)))
            for i, col in enumerate(cols):
                row = df.iloc[i]
                gap_str = "LEADER" if i == 0 else f"+{row['Gap']:.3f}s"
                col.metric(
                    label=f"P{i+1}  {row['Driver']}",
                    value=fmt_laptime(row["LapTimeSeconds"]),
                    delta=gap_str,
                    delta_color="off",
                )

            st.divider()

            # Classification table
            display_df = df[["Driver", "Team", "LapTimeSeconds", "Gap", "Sector1", "Sector2", "Sector3", "Compound"]].copy()
            display_df["LapTime"] = display_df["LapTimeSeconds"].apply(fmt_laptime)
            display_df["Gap"] = display_df["Gap"].apply(
                lambda x: "—" if pd.isna(x) or x == 0 else f"+{x:.3f}s"
            )
            display_df["Sector1"] = display_df["Sector1"].apply(
                lambda x: f"{x.total_seconds():.3f}" if pd.notna(x) else "—"
            )
            display_df["Sector2"] = display_df["Sector2"].apply(
                lambda x: f"{x.total_seconds():.3f}" if pd.notna(x) else "—"
            )
            display_df["Sector3"] = display_df["Sector3"].apply(
                lambda x: f"{x.total_seconds():.3f}" if pd.notna(x) else "—"
            )
            st.dataframe(
                display_df[["Driver", "Team", "LapTime", "Gap", "Sector1", "Sector2", "Sector3", "Compound"]],
                use_container_width=True,
                hide_index=True,
            )

    else:
        # OpenF1 path
        sk = session_obj["session_key"]

        @st.cache_data(show_spinner=False, ttl=60)
        def build_of1_classification(session_key, drivers):
            all_laps = []
            for drv_abbr in drivers:
                drivers_df = session_obj["drivers_df"]
                row = drivers_df[drivers_df["name_acronym"] == drv_abbr]
                if row.empty:
                    continue
                drv_num = row.iloc[0]["driver_number"]
                laps = openf1.get_laps(session_key, drv_num)
                if laps.empty:
                    continue
                laps["driver_acronym"] = drv_abbr
                laps["team_name"] = row.iloc[0].get("team_name", "")
                all_laps.append(laps)
            if not all_laps:
                return pd.DataFrame()
            df = pd.concat(all_laps, ignore_index=True)
            df = df.dropna(subset=["lap_duration"])
            best = df.loc[df.groupby("driver_acronym")["lap_duration"].idxmin()]
            return best.sort_values("lap_duration").reset_index(drop=True)

        with st.spinner("Fetching lap times..."):
            df = build_of1_classification(sk, tuple(selected_drivers))

        if df.empty:
            st.info("No lap data available yet.")
        else:
            leader_time = df["lap_duration"].iloc[0]
            cols = st.columns(min(3, len(df)))
            for i, col in enumerate(cols):
                row = df.iloc[i]
                gap_str = "LEADER" if i == 0 else f"+{row['lap_duration'] - leader_time:.3f}s"
                col.metric(
                    label=f"P{i+1}  {row['driver_acronym']}",
                    value=fmt_laptime(row["lap_duration"]),
                    delta=gap_str,
                    delta_color="off",
                )
            st.divider()
            st.dataframe(
                df[["driver_acronym", "team_name", "lap_duration"]].rename(
                    columns={"driver_acronym": "Driver", "team_name": "Team", "lap_duration": "Best Lap (s)"}
                ),
                use_container_width=True,
                hide_index=True,
            )


# ── Tab 2: Sector Times ───────────────────────────────────────────────────────

with tab_sectors:
    if session_obj["type"] != "fastf1":
        st.info("Sector breakdown is available for historical sessions (FastF1) only.")
    else:
        ff1 = session_obj["data"]

        @st.cache_data(show_spinner=False)
        def build_sector_data(_session, drivers):
            return compare_drivers_fastest(_session, drivers)

        df = build_sector_data(ff1, tuple(selected_drivers))
        if df.empty:
            st.info("No sector data available.")
        else:
            fig = go.Figure()
            sectors = [("Sector 1", "Sector1"), ("Sector 2", "Sector2"), ("Sector 3", "Sector3")]
            for label, col in sectors:
                vals = [
                    row[col].total_seconds() if pd.notna(row[col]) else 0
                    for _, row in df.iterrows()
                ]
                fig.add_trace(go.Bar(name=label, x=df["Driver"].tolist(), y=vals))

            fig.update_layout(
                barmode="stack",
                title="Sector Times (fastest lap)",
                xaxis_title="Driver",
                yaxis_title="Time (s)",
                legend_title="Sector",
                height=420,
                margin=dict(l=20, r=20, t=40, b=20),
            )
            st.plotly_chart(fig, use_container_width=True)


# ── Tab 3: Speed Trace ────────────────────────────────────────────────────────

with tab_speed:
    if session_obj["type"] != "fastf1":
        st.info("Speed trace is available for historical sessions (FastF1) only.")
    else:
        ff1 = session_obj["data"]
        drivers_for_trace = selected_drivers[:6]  # cap at 6 for readability

        @st.cache_data(show_spinner=False)
        def build_telemetry(_session, drivers):
            traces = {}
            for drv in drivers:
                try:
                    traces[drv] = get_telemetry(_session, drv)
                except Exception:
                    pass
            return traces

        with st.spinner("Loading telemetry..."):
            traces = build_telemetry(ff1, tuple(drivers_for_trace))

        if not traces:
            st.info("No telemetry data available.")
        else:
            fig = go.Figure()
            color_cycle = px.colors.qualitative.Plotly
            for i, (drv, tel) in enumerate(traces.items()):
                team = ff1.laps.pick_drivers(drv)["Team"].iloc[0] if not ff1.laps.pick_drivers(drv).empty else None
                color = TEAM_COLORS.get(team, color_cycle[i % len(color_cycle)])
                fig.add_trace(
                    go.Scatter(
                        x=tel["Distance"],
                        y=tel["Speed"],
                        mode="lines",
                        name=drv,
                        line=dict(color=color, width=1.5),
                    )
                )
            fig.update_layout(
                title="Speed Trace — Fastest Lap",
                xaxis_title="Distance (m)",
                yaxis_title="Speed (km/h)",
                height=440,
                hovermode="x unified",
                margin=dict(l=20, r=20, t=40, b=20),
            )
            st.plotly_chart(fig, use_container_width=True)


# ── Tab 4: Tyre Strategy ──────────────────────────────────────────────────────

with tab_tyres:
    COMPOUND_COLORS = {
        "SOFT": "#E8002D",
        "MEDIUM": "#FFF200",
        "HARD": "#FFFFFF",
        "INTERMEDIATE": "#39B54A",
        "WET": "#0067FF",
        "UNKNOWN": "#999999",
    }

    if session_obj["type"] == "fastf1":
        ff1 = session_obj["data"]

        @st.cache_data(show_spinner=False)
        def build_strategy(_session, drivers):
            return tyre_strategy(_session, drivers)

        df = build_strategy(ff1, tuple(selected_drivers))

        if df.empty:
            st.info("No tyre stint data available.")
        else:
            fig = go.Figure()
            drivers_ordered = df["Driver"].unique().tolist()
            for drv in drivers_ordered:
                stints = df[df["Driver"] == drv]
                for _, stint in stints.iterrows():
                    compound = str(stint["Compound"]).upper()
                    color = COMPOUND_COLORS.get(compound, COMPOUND_COLORS["UNKNOWN"])
                    fig.add_trace(
                        go.Bar(
                            x=[stint["Laps"]],
                            y=[drv],
                            orientation="h",
                            base=stint["StartLap"] - 1,
                            marker_color=color,
                            marker_line_color="#333",
                            marker_line_width=0.8,
                            name=compound,
                            showlegend=False,
                            hovertemplate=(
                                f"<b>{drv}</b><br>"
                                f"Compound: {compound}<br>"
                                f"Laps {stint['StartLap']}–{stint['EndLap']}<br>"
                                f"Stint length: {stint['Laps']} laps<extra></extra>"
                            ),
                        )
                    )

            # Compound legend entries
            seen = set()
            for _, row in df.iterrows():
                compound = str(row["Compound"]).upper()
                if compound not in seen:
                    seen.add(compound)
                    color = COMPOUND_COLORS.get(compound, COMPOUND_COLORS["UNKNOWN"])
                    fig.add_trace(
                        go.Bar(
                            x=[0], y=[""],
                            orientation="h",
                            marker_color=color,
                            marker_line_color="#333",
                            name=compound,
                        )
                    )

            fig.update_layout(
                barmode="stack",
                title="Tyre Strategy",
                xaxis_title="Lap",
                yaxis_title="Driver",
                height=max(300, 60 + 40 * len(drivers_ordered)),
                margin=dict(l=20, r=20, t=40, b=20),
                legend_title="Compound",
            )
            st.plotly_chart(fig, use_container_width=True)

    else:
        sk = session_obj["session_key"]

        @st.cache_data(show_spinner=False, ttl=60)
        def build_of1_stints(session_key):
            return openf1.get_stints(session_key)

        with st.spinner("Fetching stint data..."):
            stints_df = build_of1_stints(sk)

        if stints_df.empty:
            st.info("No stint data available yet.")
        else:
            drivers_df = session_obj["drivers_df"]
            drv_map = dict(zip(drivers_df["driver_number"].astype(str), drivers_df["name_acronym"]))
            stints_df["driver_acronym"] = stints_df["driver_number"].astype(str).map(drv_map)
            stints_df = stints_df[stints_df["driver_acronym"].isin(selected_drivers)]

            if stints_df.empty:
                st.info("No stint data for selected drivers.")
            else:
                fig = go.Figure()
                for drv in selected_drivers:
                    drv_stints = stints_df[stints_df["driver_acronym"] == drv]
                    for _, stint in drv_stints.iterrows():
                        compound = str(stint.get("compound", "UNKNOWN")).upper()
                        color = COMPOUND_COLORS.get(compound, COMPOUND_COLORS["UNKNOWN"])
                        start = stint.get("lap_start", 0) or 0
                        end = stint.get("lap_end", start) or start
                        laps = max(1, end - start + 1)
                        fig.add_trace(
                            go.Bar(
                                x=[laps],
                                y=[drv],
                                orientation="h",
                                base=start - 1,
                                marker_color=color,
                                marker_line_color="#333",
                                marker_line_width=0.8,
                                name=compound,
                                showlegend=False,
                                hovertemplate=(
                                    f"<b>{drv}</b><br>"
                                    f"Compound: {compound}<br>"
                                    f"Laps {start}–{end}<extra></extra>"
                                ),
                            )
                        )
                fig.update_layout(
                    barmode="stack",
                    title="Tyre Strategy",
                    xaxis_title="Lap",
                    height=max(300, 60 + 40 * len(selected_drivers)),
                    margin=dict(l=20, r=20, t=40, b=20),
                )
                st.plotly_chart(fig, use_container_width=True)
