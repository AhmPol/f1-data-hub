import os
import importlib.util
import pandas as pd
import inspect

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

def run_module(func, session, key_prefix: str):
    sig = inspect.signature(func)
    if "key_prefix" in sig.parameters:
        return func(session, key_prefix=key_prefix)
    return func(session)

