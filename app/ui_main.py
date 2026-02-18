import streamlit as st
import fastf1
from datetime import datetime
from .utils import session_category, fmt_laptime, nice_title, load_modules, run_module
from .config import TAB_NAMES_BASE, EXPLAINERS, FUNC_GROUP, MODULE_ALLOWLIST, COMPARE_FUNCS

def load_session(year, schedule, gp_label, selected_event, is_testing, session_type, testing_session_number):
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

    return st.session_state["current_session"]

def render_dashboard(session, is_testing, compare_mode):
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

    session_type_loaded = st.session_state.get("session_type", "FP1")
    cat = session_category(session_type_loaded, is_testing)
    allowed = MODULE_ALLOWLIST.get(cat, set())

    drivers = sorted(list(set(laps["Driver"]))) if (laps is not None and "Driver" in laps.columns) else sorted(list(session.drivers))

    compare_drivers = None
    if compare_mode and drivers:
        d1 = st.sidebar.selectbox("Driver 1", drivers, key="cmp_d1")
        d2 = st.sidebar.selectbox("Driver 2", drivers, index=1 if len(drivers) > 1 else 0, key="cmp_d2")
        compare_drivers = (d1, d2)

    st.session_state["compare_drivers"] = compare_drivers

    if compare_drivers:
        for prefix in ("telemetry_", "compare_"):
            st.session_state[f"{prefix}speed_driver_1"] = compare_drivers[0]
            st.session_state[f"{prefix}speed_driver_2"] = compare_drivers[1]
            st.session_state[f"{prefix}speed_diff_driver_1"] = compare_drivers[0]
            st.session_state[f"{prefix}speed_diff_driver_2"] = compare_drivers[1]
            st.session_state[f"{prefix}sector_driver_multiselect"] = list(compare_drivers)

    modules = load_modules("module")
    all_funcs = []
    for _, mod in modules.items():
        for attr in dir(mod):
            obj = getattr(mod, attr)
            if callable(obj) and attr.startswith("show_"):
                all_funcs.append(obj)
    func_by_name = {f.__name__: f for f in all_funcs}

    tab_names = TAB_NAMES_BASE.copy()
    if compare_mode:
        tab_names.insert(3, "Compare")
    tabs = st.tabs(tab_names)

    def render_function(func, key_prefix: str, expanded: bool):
        fname = func.__name__
        title = nice_title(fname)
        with st.expander(title, expanded=expanded):
            if fname in EXPLAINERS:
                st.caption(EXPLAINERS[fname])
            run_module(func, session, key_prefix=key_prefix)

    def funcs_for_tab(tab_name: str):
        out = []
        for fname, group in FUNC_GROUP.items():
            if group != tab_name:
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
                    st.info(f"Compare: **{compare_drivers[0]} vs {compare_drivers[1]}** (inputs preloaded).")
                for fname in COMPARE_FUNCS:
                    if fname in allowed and fname in func_by_name:
                        render_function(func_by_name[fname], key_prefix="compare_", expanded=True)
                continue

            funcs_here = funcs_for_tab(tname)
            if not funcs_here:
                st.caption("No modules here for this session type.")
                continue

            expanded_default = tname in {"Overview", "Lap Times"}
            key_prefix = {
                "Overview": "overview_",
                "Lap Times": "laps_",
                "Telemetry": "telemetry_",
                "Strategy": "strategy_",
                "Race": "race_",
                "Advanced": "adv_",
            }.get(tname, "tab_")

            for func in funcs_here:
                render_function(func, key_prefix=key_prefix, expanded=expanded_default)

