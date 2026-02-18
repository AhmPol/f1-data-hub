import streamlit as st
import fastf1
import os
import importlib.util
from datetime import datetime
import pandas as pd

fastf1.Cache.enable_cache("fastf1_cache")

st.set_page_config(page_title="F1 Data Hub", layout="wide")
st.title("F1 Data Hub — Data Nerd Dashboard")

# -----------------------------
# Helpers
# -----------------------------
def load_modules(folder="module"):
    modules = {}
    for file in os.listdir(folder):
        if file.endswith(".py") and file != "__init__.py":
            name = file[:-3]
            path = os.path.join(folder, file)
            spec = importlib.util.spec_from_file_location(f"module.{name}", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            modules[name] = mod
    return modules

def nice_title(func_name: str) -> str:
    return func_name.replace("show_", "").replace("_", " ").title()

def detect_testing(row: pd.Series) -> bool:
    event_name = str(row.get("EventName", ""))
    event_format = str(row.get("EventFormat", ""))
    return ("Testing" in event_name) or ("Testing" in event_format)

def session_category(session_type: str, is_testing: bool) -> str:
    if is_testing:
        return "Testing"
    if session_type == "R":
        return "Race"
    if session_type == "Q":
        return "Qualifying"
    return "Practice"

def fmt_laptime(td) -> str:
    if td is None or pd.isna(td):
        return "N/A"
    total = td.total_seconds()
    m = int(total // 60)
    s = total - 60 * m
    return f"{m}:{s:06.3f}"

# Explanations ALWAYS ON
EXPLAINERS = {
    "show_driver_consistency": "Lower = more consistent. Std dev of quick-lap times.",
    "show_overall_laptimes": "Lap time vs lap number for selected drivers (faster = higher).",
    "show_all_laptimes": "Lap time distribution by driver (violin + box), sorted by median pace.",
    "show_lap_scatter": "Single-driver lap times colored by tyre compound (stints + pace).",
    "show_qualifying_results": "Driver fastest lap gap to pole (qualifying baseline).",
    "show_team_avg": "Team average fastest-lap gap to pole (car baseline).",
    "show_speed_comparison": "2 drivers: speed vs distance with corner markers (fastest laps).",
    "show_speed_diff_track": "2 drivers: speed delta painted on track map (where time is gained/lost).",
    "show_gear_visualizer": "Fastest lap track map colored by gear.",
    "show_stint_strategy": "Stint timeline by compound (strategy overview).",
    "show_tyre_degradation": "Lap time evolution within stints (tyre drop-off).",
    "show_race_results": "Positions over laps (race story / overtakes).",
    "show_sector_times": "Sector distributions (advanced; can look busy).",
    "show_telemetry_overlay": "Telemetry overlay (advanced; can be noisy/data-dependent).",
    "show_point_finishers": "Top 10 lap times over race (advanced; niche).",
}

# -----------------------------
# Grouping / Tabs
#   - Qualifying tab removed
#   - Team/Driver fastest (qualifying charts) moved under Overview
#   - Strategy tab includes stint + tyre and appears for all sessions
#   - Race positions only shown in Race sessions
#   - Compare gets its own tab
# -----------------------------
TAB_NAMES_BASE = ["Overview", "Lap Times", "Telemetry", "Strategy", "Race", "Advanced"]

FUNC_GROUP = {
    # Overview (includes qualifying-derived charts too)
    "show_driver_consistency": "Overview",
    "show_qualifying_results": "Overview",
    "show_team_avg": "Overview",

    # Lap Times
    "show_overall_laptimes": "Lap Times",
    "show_all_laptimes": "Lap Times",
    "show_lap_scatter": "Lap Times",

    # Telemetry
    "show_speed_comparison": "Telemetry",
    "show_speed_diff_track": "Telemetry",
    "show_gear_visualizer": "Telemetry",

    # Strategy (always shown)
    "show_stint_strategy": "Strategy",
    "show_tyre_degradation": "Strategy",

    # Race (race-only)
    "show_race_results": "Race",

    # Advanced (always shown)
    "show_sector_times": "Advanced",
    "show_telemetry_overlay": "Advanced",
    "show_point_finishers": "Advanced",
}

# Allowlist by session type
# - Strategy always included
# - Race positions only for Race
MODULE_ALLOWLIST = {
    "Race": {
        "show_driver_consistency",
        "show_qualifying_results", "show_team_avg",
        "show_overall_laptimes", "show_all_laptimes", "show_lap_scatter",
        "show_speed_comparison", "show_speed_diff_track", "show_gear_visualizer",
        "show_stint_strategy", "show_tyre_degradation",
        "show_race_results",
        "show_sector_times", "show_telemetry_overlay", "show_point_finishers",
    },
    "Qualifying": {
        "show_driver_consistency",
        "show_qualifying_results", "show_team_avg",
        "show_overall_laptimes", "show_all_laptimes", "show_lap_scatter",
        "show_speed_comparison", "show_speed_diff_track", "show_gear_visualizer",
        "show_stint_strategy", "show_tyre_degradation",
        "show_sector_times", "show_telemetry_overlay",
    },
    "Practice": {
        "show_driver_consistency",
        "show_overall_laptimes", "show_all_laptimes", "show_lap_scatter",
        "show_speed_comparison", "show_speed_diff_track", "show_gear_visualizer",
        "show_stint_strategy", "show_tyre_degradation",
        "show_sector_times", "show_telemetry_overlay",
    },
    "Testing": {
        "show_driver_consistency",
        "show_overall_laptimes", "show_all_laptimes", "show_lap_scatter",
        "show_speed_comparison", "show_speed_diff_track", "show_gear_visualizer",
        "show_stint_strategy", "show_tyre_degradation",
        "show_sector_times", "show_telemetry_overlay",
    },
}

# Compare tab = only comparison-friendly graphs
COMPARE_FUNCS = [
    "show_speed_comparison",
    "show_speed_diff_track",
    "show_telemetry_overlay",
    "show_sector_times",
]

# -----------------------------
# Sidebar: Control Center
# -----------------------------
st.sidebar.header("Control Center")

years = list(range(2018, 2027))
year = st.sidebar.selectbox("Year", years, index=len(years) - 1)

if st.sidebar.button("Load Event List"):
    schedule = fastf1.get_event_schedule(year)
    schedule = schedule[["RoundNumber", "EventName", "EventDate", "EventFormat"]].copy()

    def _date_str(d):
        try:
            return pd.to_datetime(d).date().isoformat()
        except Exception:
            return str(d)

    schedule["EventDateStr"] = schedule["EventDate"].apply(_date_str)
    schedule["DisplayName"] = (
        schedule["EventName"].astype(str)
        + " — "
        + schedule["EventDateStr"].astype(str)
        + " (" + schedule["EventFormat"].astype(str) + ")"
    )

    schedule["RoundSort"] = pd.to_numeric(schedule["RoundNumber"], errors="coerce")
    schedule = schedule.sort_values(["EventDate", "RoundSort"], na_position="last").reset_index(drop=True)
    st.session_state["races"] = schedule

if "races" not in st.session_state:
    st.info("Load the event list from the sidebar to start.")
    st.stop()

schedule = st.session_state["races"]
gp_label = st.sidebar.selectbox("Grand Prix / Event", schedule["DisplayName"].tolist())
selected_event = schedule.loc[schedule["DisplayName"] == gp_label].iloc[0]

is_testing = detect_testing(selected_event)

if is_testing:
    testing_session_label = st.sidebar.selectbox("Testing Session", ["Session 1", "Session 2", "Session 3"])
    testing_session_number = int(testing_session_label.split()[-1])
    session_type = None
else:
    session_type = st.sidebar.selectbox("Session", ["FP1", "FP2", "FP3", "Q", "R"])

# Compare mode (now creates a Compare tab)
st.sidebar.divider()
st.sidebar.subheader("Compare")

compare_mode = st.sidebar.toggle("Enable Compare Tab (2 drivers)", value=False)

# -----------------------------
# Load session
# -----------------------------
if st.sidebar.button("Load Session Data"):
    try:
        if is_testing:
            testing_events = schedule[schedule["EventName"].astype(str).str.contains("Testing", na=False)].copy()
            testing_events = testing_events.sort_values(["EventDate", "RoundSort"], na_position="last").reset_index(drop=True)

            match = testing_events.index[testing_events["DisplayName"] == gp_label]
            if len(match) == 0:
                match = testing_events.index[testing_events["EventDateStr"] == selected_event["EventDateStr"]]
            test_number = int(match[0]) + 1

            session = fastf1.get_testing_session(year, test_number, testing_session_number)
            session.load()
            st.session_state["current_session"] = session
            st.session_state["session_type"] = "T"
            st.success(f"Loaded {selected_event['EventName']} — Test {test_number}, Session {testing_session_number}")

        else:
            round_number = int(selected_event["RoundNumber"])
            session = fastf1.get_session(year, round_number, session_type)
            session.load()
            st.session_state["current_session"] = session
            st.session_state["session_type"] = session_type
            st.success(f"Loaded {selected_event['EventName']} {session_type}")

    except Exception as e:
        st.exception(e)
        st.stop()

if "current_session" not in st.session_state:
    st.warning("Load a session from the sidebar.")
    st.stop()

session = st.session_state["current_session"]
session_type_loaded = st.session_state.get("session_type", "FP1")
cat = session_category(session_type_loaded, is_testing)
allowed = MODULE_ALLOWLIST.get(cat, set())

# -----------------------------
# Summary header
# -----------------------------
st.subheader(f"{session.event['EventName']} {session.event.year} — {session.name}")

laps = session.laps
quicklaps = laps.pick_quicklaps() if laps is not None else None
fastest = laps.pick_fastest() if laps is not None else None

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Drivers", len(session.drivers) if hasattr(session, "drivers") else 0)
c2.metric("Total laps", len(laps) if laps is not None else 0)
c3.metric("Quick laps", len(quicklaps) if quicklaps is not None else 0)
c4.metric("Fastest lap", fmt_laptime(fastest["LapTime"]) if fastest is not None else "N/A")
c5.metric("Loaded at", datetime.now().strftime("%H:%M:%S"))

# -----------------------------
# Compare driver selection (preload compare module inputs)
# -----------------------------
drivers = sorted(list(set(laps["Driver"]))) if (laps is not None and "Driver" in laps.columns) else sorted(list(session.drivers))

compare_drivers = None
if compare_mode and drivers:
    d1 = st.sidebar.selectbox("Driver 1", drivers, key="cmp_d1")
    d2 = st.sidebar.selectbox("Driver 2", drivers, index=1 if len(drivers) > 1 else 0, key="cmp_d2")
    compare_drivers = (d1, d2)

# Store for modules that read it (telemetry overlay fix you asked earlier already supports this)
st.session_state["compare_drivers"] = compare_drivers

# Preload module selectbox keys where possible (no module edits needed if keys exist)
# speedcomparison.py uses keys: "speed_driver_1", "speed_driver_2"
# speedmap.py uses keys: 'speed_diff_driver_1', 'speed_diff_driver_2'
if compare_drivers:
    st.session_state["speed_driver_1"] = compare_drivers[0]
    st.session_state["speed_driver_2"] = compare_drivers[1]
    st.session_state["speed_diff_driver_1"] = compare_drivers[0]
    st.session_state["speed_diff_driver_2"] = compare_drivers[1]

# -----------------------------
# Load modules + collect show_ funcs
# -----------------------------
modules = load_modules("module")

all_funcs = []
for _, mod in modules.items():
    for attr in dir(mod):
        obj = getattr(mod, attr)
        if callable(obj) and attr.startswith("show_"):
            all_funcs.append(obj)

func_by_name = {f.__name__: f for f in all_funcs}

# -----------------------------
# Tabs
#   - Add Compare tab when compare_mode enabled
# -----------------------------
tab_names = TAB_NAMES_BASE.copy()
if compare_mode:
    tab_names.insert(3, "Compare")  # put Compare between Telemetry and Strategy

tabs = st.tabs(tab_names)

# -----------------------------
# Render: each tab gets functions that belong there AND are allowed
# -----------------------------
def render_function(func):
    fname = func.__name__
    title = nice_title(fname)

    with st.expander(title, expanded=False):
        if fname in EXPLAINERS:
            st.caption(EXPLAINERS[fname])

        try:
            func(session)
        except Exception as e:
            st.error(f"Module crashed: {fname}")
            st.exception(e)

def funcs_for_tab(tname: str):
    out = []
    for fname, group in FUNC_GROUP.items():
        if group != tname:
            continue
        if fname not in allowed:
            continue
        if fname in func_by_name:
            out.append(func_by_name[fname])
    return sorted(out, key=lambda f: nice_title(f.__name__))

for tname, tab in zip(tab_names, tabs):
    with tab:
        if tname == "Compare":
            if not compare_drivers:
                st.warning("Pick Driver 1 and Driver 2 in the sidebar to populate Compare.")
            else:
                st.info(f"Compare: **{compare_drivers[0]} vs {compare_drivers[1]}** (preloaded into comparison tools).")

            # Render compare tools in a fixed order (only those that exist + allowed)
            for fname in COMPARE_FUNCS:
                if fname in allowed and fname in func_by_name:
                    render_function(func_by_name[fname])

            continue

        # Normal tabs
        funcs_here = funcs_for_tab(tname)

        # Race tab should be empty for non-race sessions (by design)
        if not funcs_here:
            st.caption("No modules here for this session type.")
            continue

        # Make Overview + Lap Times open by default (more readable)
        expand_default = (tname in {"Overview", "Lap Times"})
        for func in funcs_here:
            fname = func.__name__
            title = nice_title(fname)
            with st.expander(title, expanded=expand_default):
                if fname in EXPLAINERS:
                    st.caption(EXPLAINERS[fname])
                try:
                    func(session)
                except Exception as e:
                    st.error(f"Module crashed: {fname}")
                    st.exception(e)
