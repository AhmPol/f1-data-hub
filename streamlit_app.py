import streamlit as st
import fastf1
import os
import importlib.util
import inspect
from datetime import datetime

fastf1.Cache.enable_cache('fastf1_cache')

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


EXPLAINERS = {
    "show_driver_consistency": "Lower = more consistent. Std dev of quick-lap times (noise filtered).",
    "show_overall_laptimes": "Lap time vs lap number for selected drivers. Faster laps appear higher (reversed axis).",
    "show_all_laptimes": "Distribution of lap times by driver (violin + box). Sorted by median pace.",
    "show_point_finishers": "Lap times of P1–P10 finishers across laps, split by tyre compound.",
    "show_lap_scatter": "Single-driver lap times colored by tyre compound (helps spot stints + pace drop).",
    "show_sector_times": "Sector 1/2/3 distributions (violin). Great for where pace comes from.",
    "show_qualifying_results": "Each driver’s fastest lap gap to pole (horizontal bars).",
    "show_team_avg": "Team average fastest-lap gap to pole (useful for car performance baseline).",
    "show_race_results": "Position by lap (race story / overtakes / incidents).",
    "show_stint_strategy": "Stint timeline by compound (strategy overview).",
    "show_tyre_degradation": "Lap time evolution within stints (pace drop / tyre life).",
    "show_telemetry_overlay": "Fastest lap overlays across drivers for chosen channel (Speed/Throttle/Brake/Gear/RPM).",
    "show_speed_comparison": "2-driver fastest lap speed vs distance, with corner markers.",
    "show_speed_diff_track": "2-driver speed delta painted on track map (where time is gained/lost).",
    "show_gear_visualizer": "Fastest lap track map colored by gear (driving style / gearing).",
}

# Map function -> logical group/tab
FUNC_GROUP = {
    # Overview
    "show_driver_consistency": "Overview",

    # Lap Times
    "show_overall_laptimes": "Lap Times",
    "show_all_laptimes": "Lap Times",
    "show_point_finishers": "Lap Times",
    "show_lap_scatter": "Lap Times",

    # Quali
    "show_qualifying_results": "Qualifying",
    "show_team_avg": "Qualifying",

    # Telemetry
    "show_telemetry_overlay": "Telemetry",
    "show_speed_comparison": "Telemetry",
    "show_speed_diff_track": "Telemetry",
    "show_gear_visualizer": "Telemetry",
    "show_sector_times": "Telemetry",

    # Strategy
    "show_stint_strategy": "Strategy",
    "show_tyre_degradation": "Strategy",

    # Race
    "show_race_results": "Race",
}

# What to show per session category (removes filler automatically)
MODULE_ALLOWLIST = {
    "Race": {
        "show_driver_consistency",
        "show_overall_laptimes", "show_all_laptimes", "show_point_finishers", "show_lap_scatter",
        "show_sector_times",
        "show_telemetry_overlay", "show_speed_comparison", "show_speed_diff_track", "show_gear_visualizer",
        "show_stint_strategy", "show_tyre_degradation",
        "show_race_results",
    },
    "Qualifying": {
        "show_driver_consistency",
        "show_qualifying_results", "show_team_avg",
        "show_sector_times",
        "show_telemetry_overlay", "show_speed_comparison", "show_speed_diff_track", "show_gear_visualizer",
        "show_overall_laptimes", "show_all_laptimes",
    },
    "Practice": {
        "show_driver_consistency",
        "show_overall_laptimes", "show_all_laptimes", "show_lap_scatter",
        "show_sector_times",
        "show_telemetry_overlay", "show_speed_comparison", "show_speed_diff_track", "show_gear_visualizer",
    },
    "Testing": {
        "show_driver_consistency",
        "show_overall_laptimes", "show_all_laptimes", "show_lap_scatter",
        "show_sector_times",
        "show_telemetry_overlay", "show_speed_comparison", "show_speed_diff_track", "show_gear_visualizer",
    },
}

def detect_testing(selected_event) -> bool:
    event_name = str(selected_event.get("EventName", ""))
    event_format = str(selected_event.get("EventFormat", ""))
    return ("Testing" in event_name) or ("Testing" in event_format)

def session_category(session_type: str, is_testing: bool) -> str:
    if is_testing:
        return "Testing"
    if session_type == "Q":
        return "Qualifying"
    if session_type == "R":
        return "Race"
    return "Practice"


# -----------------------------
# Sidebar: Control Center
# -----------------------------
st.sidebar.header("Control Center")

years = list(range(2025, 2027))
year = st.sidebar.selectbox("Year", years, index=len(years)-1)

if st.sidebar.button("Load Event List"):
    schedule = fastf1.get_event_schedule(year)
    # keep what you had
    schedule = schedule[['RoundNumber', 'EventName', 'EventDate', 'EventFormat']].sort_values('RoundNumber')
    st.session_state['races'] = schedule

if 'races' not in st.session_state:
    st.info("Load the event list from the sidebar to start.")
    st.stop()

gp = st.sidebar.selectbox("Grand Prix / Event", st.session_state['races']['EventName'])

selected_event = st.session_state['races'].loc[
    st.session_state['races']['EventName'] == gp
].iloc[0]

is_testing = detect_testing(selected_event)

# Session selector changes depending on testing vs weekend
if is_testing:
    testing_session_label = st.sidebar.selectbox("Testing Session", ["Session 1", "Session 2", "Session 3"])
    testing_session_number = int(testing_session_label.split()[-1])
    session_type = None
else:
    session_type = st.sidebar.selectbox("Session", ['FP1', 'FP2', 'FP3', 'Q', 'R'])

# Nerd filters
st.sidebar.divider()
st.sidebar.subheader("Nerd Filters")

compare_mode = st.sidebar.toggle("Compare Mode (2 drivers)", value=False)
focus_only = st.sidebar.toggle("Focus view (hide noisy modules)", value=True)
show_explainers = st.sidebar.toggle("Show quick explanations", value=True)

# module search
module_search = st.sidebar.text_input("Search modules", value="").strip().lower()

# -----------------------------
# Load session
# -----------------------------
if st.sidebar.button("Load Session Data"):
    try:
        if is_testing:
            testing_events = st.session_state['races'][
                st.session_state['races']['EventName'].astype(str).str.contains("Testing", na=False)
            ].sort_values("EventDate").reset_index(drop=True)
            test_number = int(testing_events[testing_events["EventName"] == gp].index[0]) + 1

            session = fastf1.get_testing_session(year, test_number, testing_session_number)
            session.load()
            st.session_state['current_session'] = session
            st.session_state['session_kind'] = "Testing"
            st.session_state['session_type'] = "T"
            st.success(f"Loaded {gp} — Session {testing_session_number}")

        else:
            round_number = int(selected_event["RoundNumber"])
            session = fastf1.get_session(year, round_number, session_type)
            session.load()
            st.session_state['current_session'] = session
            st.session_state['session_kind'] = session_category(session_type, False)
            st.session_state['session_type'] = session_type
            st.success(f"Loaded {gp} {session_type}")
    except Exception as e:
        st.exception(e)
        st.stop()

if 'current_session' not in st.session_state:
    st.warning("Load a session from the sidebar.")
    st.stop()

session = st.session_state['current_session']

# -----------------------------
# Session header summary (clarity!)
# -----------------------------
st.subheader(f"{session.event['EventName']} {session.event.year} — {session.name}")

laps = session.laps
quicklaps = laps.pick_quicklaps()
fastest = laps.pick_fastest()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Drivers", len(session.drivers))
c2.metric("Total laps", len(laps))
c3.metric("Quick laps", len(quicklaps))
c4.metric("Fastest lap", str(fastest['LapTime']) if fastest is not None else "N/A")

# -----------------------------
# Compare mode setup
# -----------------------------
drivers = sorted(list(set(laps['Driver']))) if 'Driver' in laps.columns else []

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

# Flatten out all show_ functions found
all_funcs = []
for _, mod in modules.items():
    for attr in dir(mod):
        obj = getattr(mod, attr)
        if callable(obj) and attr.startswith("show_"):
            all_funcs.append(obj)

# session category drives allowlist
cat = session_category(st.session_state.get("session_type", "FP1"), is_testing)
allowed = MODULE_ALLOWLIST.get(cat, set())

# If compare mode, only show the most comparison-friendly tools by default
COMPARE_CORE = {
    "show_speed_comparison",
    "show_speed_diff_track",
    "show_sector_times",
    "show_telemetry_overlay",
}

# Optionally “focus only” removes some noisy plots unless searched explicitly
NOISY_BY_DEFAULT = {
    "show_all_laptimes",  # can be heavy visually
    "show_point_finishers",
}

def should_show(func_name: str) -> bool:
    if func_name not in allowed:
        return False

    if module_search:
        # search overrides everything else
        return module_search in func_name.lower() or module_search in nice_title(func_name).lower()

    if compare_mode:
        return func_name in COMPARE_CORE

    if focus_only and func_name in NOISY_BY_DEFAULT:
        return False

    return True

# Group functions by tab
tab_names = ["Overview", "Lap Times", "Qualifying", "Telemetry", "Strategy", "Race", "Advanced"]
tabs = st.tabs(tab_names)

# Build a dict: tab -> list[func]
tab_funcs = {t: [] for t in tab_names}
for func in all_funcs:
    fname = func.__name__
    if not should_show(fname):
        continue
    group = FUNC_GROUP.get(fname, "Advanced")
    tab_funcs.setdefault(group, []).append(func)

# Keep consistent ordering inside tabs
def sort_key(f):
    return nice_title(f.__name__)
for t in tab_funcs:
    tab_funcs[t] = sorted(tab_funcs[t], key=sort_key)

# -----------------------------
# Render tabs
# -----------------------------
for tname, tab in zip(tab_names, tabs):
    with tab:
        funcs_here = tab_funcs.get(tname, [])
        if not funcs_here:
            st.caption("No modules here (based on your current filters).")
            continue

        for func in funcs_here:
            fname = func.__name__
            title = nice_title(fname)

            # compact module header style
            with st.expander(title, expanded=(tname in ["Overview", "Telemetry"] and (not compare_mode))):
                if show_explainers and fname in EXPLAINERS:
                    st.caption(EXPLAINERS[fname])

                # If compare mode is on, give user a reminder for 2-driver modules
                if compare_mode and fname in {"show_speed_comparison", "show_speed_diff_track"}:
                    if compare_drivers:
                        st.info(f"Compare Mode: {compare_drivers[0]} vs {compare_drivers[1]} (use the dropdowns inside the module if needed).")

                # Run the module
                try:
                    func(session)
                except Exception as e:
                    st.error(f"Module crashed: {fname}")
                    st.exception(e)

# Bonus: show what’s hidden (true nerd feature)
with st.sidebar.expander("What’s hidden right now?"):
    hidden = []
    for func in all_funcs:
        if func.__name__ in allowed and not should_show(func.__name__):
            hidden.append(nice_title(func.__name__))
    if hidden:
        st.write(hidden)
    else:
        st.write("Nothing hidden.")
