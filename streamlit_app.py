import streamlit as st
import fastf1
import os
import importlib.util

fastf1.Cache.enable_cache('fastf1_cache')

st.title("F1 Data Interface")

years = list(range(2018, 2027))
year = st.selectbox("Select Year", years)

if st.button("Load Grand Prix List"):
    schedule = fastf1.get_event_schedule(year)
    schedule = schedule[['RoundNumber','EventName','EventDate','EventFormat']].sort_values('RoundNumber')
    st.session_state['races'] = schedule

if 'races' in st.session_state:
    gp = st.selectbox("Select Grand Prix", st.session_state['races']['EventName'])

    # Grab the selected event row
    selected_event = st.session_state['races'].loc[
        st.session_state['races']['EventName'] == gp
    ].iloc[0]

    event_name = str(selected_event.get("EventName", ""))
    event_format = str(selected_event.get("EventFormat", ""))

    # Detect testing events
    is_testing = ("Testing" in event_name) or ("Testing" in event_format)

    if is_testing:
        testing_session_label = st.selectbox(
            "Select Testing Session",
            ["Session 1", "Session 2", "Session 3"]
        )
        testing_session_number = int(testing_session_label.split()[-1])
    else:
        session_type = st.selectbox("Select Session", ['FP1', 'FP2', 'FP3', 'Q', 'R'])

    if st.button("Load Session"):
        if is_testing:
            # Find which testing event number this is (1st test, 2nd test, etc.)
            testing_events = st.session_state['races'][
                st.session_state['races']['EventName'].astype(str).str.contains("Testing", na=False)
            ].sort_values("EventDate").reset_index(drop=True)

            test_number = int(testing_events[testing_events["EventName"] == gp].index[0]) + 1

            session = fastf1.get_testing_session(year, test_number, testing_session_number)
            session.load()
            st.session_state['current_session'] = session
            st.success(f"Loaded {gp} - Session {testing_session_number}")

        else:
            round_number = int(selected_event["RoundNumber"])
            session = fastf1.get_session(year, round_number, session_type)
            session.load()
            st.session_state['current_session'] = session
            st.success(f"Loaded {gp} {session_type}")

# Load modules dynamically
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

if 'current_session' in st.session_state:
    modules = load_modules("module")
    for name, mod in modules.items():
        show_funcs = [getattr(mod, attr) for attr in dir(mod)
                      if callable(getattr(mod, attr)) and attr.startswith("show_")]
        for func in show_funcs:
            with st.expander(f"{func.__name__.replace('show_','').replace('_',' ').title()}"):
                func(st.session_state['current_session'])
