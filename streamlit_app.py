import streamlit as st
import fastf1
import os
import importlib.util

fastf1.Cache.enable_cache('fastf1_cache')

st.title("F1 Data Interface")

years = list(range(2018, 2026))
year = st.selectbox("Select Year", years)

if st.button("Load Grand Prix List"):
    schedule = fastf1.get_event_schedule(year)
    schedule = schedule[['RoundNumber','EventName','EventDate','EventFormat']].sort_values('RoundNumber')
    st.session_state['races'] = schedule

if 'races' in st.session_state:
    gp = st.selectbox("Select Grand Prix", st.session_state['races']['EventName'])
    session_type = st.selectbox("Select Session", ['FP1','FP2','FP3','Q','R'])
    if st.button("Load Session"):
        round_number = st.session_state['races'].loc[st.session_state['races']['EventName']==gp,'RoundNumber'].iloc[0]
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
