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
    if session_type == "Q":
        return "Qualifying"
    if session_type == "R":
        return "Race"
    return "Practice"

def fmt_laptime(td) -> str:
    """Format timedelta like M:SS.mmm instead of '0 days 00:...'."""
    if td is None or pd.isna(td):
        return "N/A"
    total = td.total_seconds()
    m = int(total // 60)
    s = total - 60 * m
    return f"{m}:{s:06.3f}"

EXPLAINERS = {
    "show_driver_consistency": "Lower = more consistent. Std dev of quick-lap times.",
    "show_overall_laptimes": "Lap time vs lap number for selected drivers (faster = higher).",
    "show_all_laptimes": "Lap time distribution by driver (violin + box), sorted by median pace.",
    "show_lap_scatter": "Single-driver lap times colored by tyre compound (great for stints).",
    "show_qualifying_results": "Fastest lap gap to pole per driver.",
    "show_team_avg": "Team average gap to pole (fastest-lap baseline).",
    "show_race_results": "Positions over laps (race story).",
    "show_stint_strategy": "Stint timeline by compound (strategy overview).",
    "show_tyre_degradation": "Lap time evolution per stint (tyre life / drop-off).",
    "show_speed_comparison": "2-driver fastest lap: speed vs distance with corner markers.",
    "show_speed_diff_track": "2-driver speed delta painted on track map (where time is gained/lost).",
    "show_gear_visualizer": "Fastest lap track map colored by gear.",
    # These are now Advanced-only:
    "show_sector_times": "Sector distributions (advanced/nerdy, can be visually busy).",
    "show_telemetry_overlay": "Overlay telemetry for fastest laps (can be noisy / data-dependent).",
}

# Grouping: keep it “data nerd” but readable
FUNC_GROUP = {
    # Overview
    "show_driver_consistency": "Overview",

    # Lap Times (core clarity)
    "show_overall_laptimes": "Lap Times",
    "show_all_laptimes": "Lap Times",
    "show_lap_scatter": "Lap Times",

    # Quali
    "show_qualifying_results": "Qualifying",
    "show_team_avg": "Qualifying",

    # Telemetry (only the high-signal ones)
    "show_speed_comparison": "Telemetry",
    "show_speed_diff_track": "Telemetry",
    "show_gear_visualizer": "Telemetry",

    # Strategy
    "show_stint_strategy": "Strategy",
    "show_tyre_degradation": "Strategy",

    # Race
    "show_race_results": "Race",

    # Advanced (optional/noisy)
    "show_sector_times": "Advanced",
    "show_telemetry_overlay": "Advanced",
    "show_point_finishers": "Advanced",
}

# Allowlist per session type (clean + correct)
MODULE_ALLOWLIST = {
    "Race": {
        "show_driver_consistency",
        "show_overall_laptimes", "show_all_laptimes", "show_lap_scatter",
        "show_speed_comparison", "show_speed_diff_track", "show_gear_visualizer",
        "show_stint_strategy", "show_tyre_degradation",
        "show_race_results",
        # advanced available too if user wants it:
        "show_sector_times", "show_telemetry_overlay", "show_point_finishers",
    },
    "Qualifying": {
        "show_driver_consistency",
        "show_qualifying_results", "show_team_avg",
        "show_overall_laptimes", "show_all_laptimes",
        "show_speed_comparison", "show_speed_diff_track", "show_gear_visualizer",
        "show_sector_times", "show_telemetry_overlay",
    },
    "Practice": {
        "show_driver_consistency",
        "show_overall_laptimes", "show_all_laptimes", "show_lap_scatter",
        "show_speed_comparison", "show_speed_diff_track", "show_gear_visualizer",
        "show_sector_times", "show_telemetry_overlay",
    },
    "Testing": {
        "show_driver_consistency",
        "show_overall_laptimes", "show_all_laptimes", "show_lap_scatter",
        "show_speed_comparison", "show_speed_diff_track", "show_gear_visualizer",
        "show_sector_times", "show_telemetry_overlay",
    },
}

# -----------------------------
# Sidebar: Control Center
# -----------------------------
st.sidebar.header("Control Center")

years = list(range(2018, 2027))
year = st.sidebar.selectbox("Year", years, index=len(years) - 1)

if st.sidebar.button("Load Event List"):
    schedule = fastf1.get_event_schedule(year)
    # Keep the useful columns, but DO NOT sort only by RoundNumber (testing may share/blank round)
    schedule = schedule[['RoundNumber', 'EventName', 'EventDate', 'EventFormat']].copy()

    # Create a unique display label (fixes 2 testing events with same name)
    # Example: "Pre-Season Testing — 2026-02-12 (Testing)"
    # EventDate sometimes includes time; we only want the date part.
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

    # Stable sort: by EventDate then RoundNumber (RoundNumber can be NaN)
    schedule["RoundSort"] = pd.to_numeric(schedule["RoundNumber"], errors="coerce")
    schedule = schedule.sort_values(["EventDate", "RoundSort"], na_position="last").reset_index(drop=True)

    st.session_state["races"] = schedule

if "races" not in st.session_state:
    st.info("Load the event list from the sidebar to start.")
    st.stop()

schedule = st.session_state["races"]

# Select event using DisplayName to avoid duplicate-name issues
gp_label = st.sidebar.selectbox("Grand Prix / Event", schedule["DisplayName"].tolist())
selected_event = schedule.loc[schedule["DisplayName"] == gp_label].iloc[0]
selected_event_idx = int(schedule.index[schedule["DisplayName"] == gp_label][0])

is_testing = detect_testing(selected_event)

# Session selector changes depending on testing vs weekend
if is_testing:
    testing_session_label = st.sidebar.selectbox("Testing Session", ["Session 1", "Session 2", "Session 3"])
    testing_session_number = int(testing_session_label.split()[-1])
    session_type = None
else:
    session_type = st.sidebar.selectbox("Session", ["FP1", "FP2", "FP3", "Q", "R"])

# Nerd filters (but NOT overly severe)
st.sidebar.divider()
st.sidebar.subheader("Nerd Filters")

compare_mode = st.sidebar.toggle("Compare Mode (2 drivers)", value=False)
show_explainers = st.sidebar.toggle("Show quick explanations", value=True)

# Keep filters light: only hide Advanced unless user opts-in
show_advanced = st.sidebar.toggle("Show Advanced tab", value=False)

# Search modules (optional)
module_search = st.sidebar.text_input("Search modules (optional)", value="").strip().lower()

# -----------------------------
# Load session
# -----------------------------
if st.sidebar.button("Load Session Data"):
    try:
        if is_testing:
            # Build ordered list of testing events (unique by DisplayName and date)
            testing_events = schedule[schedule["EventName"].astype(str).str.contains("Testing", na=False)].copy()
            testing_events = testing_events.sort_values(["EventDate", "RoundSort"], na_position="last").reset_index(drop=True)

            # Find the selected testing event by matching DisplayName (unique)
            # This fixes “two pre-season tests with same name”.
            match = testing_events.index[testing_events["DisplayName"] == gp_label]
            if len(match) == 0:
                # fallback: match by date string
                match = testing_events.index[testing_events["EventDateStr"] == selected_event["EventDateStr"]]
            test_number = int(match[0]) + 1

            session = fastf1.get_testing_session(year, test_number, testing_session_number)
            session.load()
            st.session_state["current_session"] = session
            st.session_state["session_kind"] = "Testing"
            st.session_state["session_type"] = "T"
            st.success(f"Loaded {selected_event['EventName']} — Test {test_number}, Session {testing_session_number}")

        else:
            # For race weekends, use round number normally
            round_number = int(selected_event["RoundNumber"])
            session = fastf1.get_session(year, round_number, session_type)
            session.load()
            st.session_state["current_session"] = session
            st.session_state["session_kind"] = session_category(session_type, False)
            st.session_state["session_type"] = session_type
            st.success(f"Loaded {selected_event['EventName']} {session_type}")

    except Exception as e:
        st.exception(e)
        st.stop()

if "current_session" not in st.session_state:
    st.warning("Load a session from the sidebar.")
    st.stop()

session = st.session_state["current_session"]

# -----------------------------
# Session header summary (clear!)
# -----------------------------
st.subheader(f"{session.event['EventName']} {session.event.year} — {session.name}")

laps = session.laps
quicklaps = laps.pick_quicklaps() if laps is not None else []
fastest = laps.pick_fastest() if laps is not None else None

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Drivers", len(session.drivers) if hasattr(session, "drivers") else 0)
c2.metric("Total laps", len(laps) if laps is not None else 0)
c3.metric("Quick laps", len(quicklaps) if quicklaps is not None else 0)
c4.metric("Fastest lap", fmt_laptime(fastest["LapTime"]) if fastest is not None else "N/A")
c5.metric("Loaded at", datetime.now().strftime("%H:%M:%S"))

# -----------------------------
# Compare mode setup (does NOT hide everything)
# -----------------------------
drivers = sorted(list(set(laps["Driver"]))) if (laps is not None and "Driver" in laps.columns) else []
compare_drivers = None
if compare_mode and drivers:
    d1 = st.sidebar.selectbox("Driver 1", drivers, key="cmp_d1")
    d2 = st.sidebar.selectbox("Driver 2", drivers, index=1 if len(drivers) > 1 else 0, key="cmp_d2")
    compare_drivers = (d1, d2)
st.session_state["compare_drivers"] = compare_drivers

# -----------------------------
# Load and filter modules
# -----------------------------
modules = load_modules("module")

# Flatten all show_ functions
all_funcs = []
for _, mod in modules.items():
    for attr in dir(mod):
        obj = getattr(mod, attr)
        if callable(obj) and attr.startswith("show_"):
            all_funcs.append(obj)

cat = session_category(st.session_state.get("session_type", "FP1"), is_testing)
allowed = MODULE_ALLOWLIST.get(cat, set())

def should_show(func_name: str) -> bool:
    if func_name not in allowed:
        return False

    # Search overrides everything
    if module_search:
        return (module_search in func_name.lower()) or (module_search in nice_title(func_name).lower())

    # Hide advanced stuff unless toggled
    if not show_advanced and FUNC_GROUP.get(func_name, "Advanced") == "Advanced":
        return False

    return True

tab_names = ["Overview", "Lap Times", "Qualifying", "Telemetry", "Strategy", "Race"]
if show_advanced:
    tab_names.append("Advanced")
tabs = st.tabs(tab_names)

# Group funcs by tab
tab_funcs = {t: [] for t in tab_names}
for func in all_funcs:
    fname = func.__name__
    if not should_show(fname):
        continue
    group = FUNC_GROUP.get(fname, "Advanced")
    if group not in tab_funcs:
        # if Advanced hidden, skip; if shown, it exists
        continue
    tab_funcs[group].append(func)

# Sort inside tabs
for t in tab_funcs:
    tab_funcs[t] = sorted(tab_funcs[t], key=lambda f: nice_title(f.__name__))

# -----------------------------
# Render tabs
# -----------------------------
for tname, tab in zip(tab_names, tabs):
    with tab:
        funcs_here = tab_funcs.get(tname, [])
        if not funcs_here:
            st.caption("No modules here (based on your filters).")
            continue

        # If compare mode, add a small pinned hint in Telemetry tab
        if tname == "Telemetry" and compare_mode and compare_drivers:
            st.info(f"Compare Mode: **{compare_drivers[0]} vs {compare_drivers[1]}** — use Speed Comparison + Speed Diff Track for the cleanest story.")

        for func in funcs_here:
            fname = func.__name__
            title = nice_title(fname)

            # Cleaner defaults: open Overview + Lap Times, others collapsed
            expanded_default = tname in {"Overview", "Lap Times"}

            with st.expander(title, expanded=expanded_default):
                if show_explainers and fname in EXPLAINERS:
                    st.caption(EXPLAINERS[fname])

                # Run the module safely
                try:
                    func(session)
                except Exception as e:
                    st.error(f"Module crashed: {fname}")
                    st.exception(e)
