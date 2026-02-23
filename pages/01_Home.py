import plotly.graph_objects as go

def plot_telemetry_row(df, y_col, title, y_suffix=""):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["Distance"], y=df[y_col], mode="lines", name=y_col))
    fig.update_layout(
        height=220,
        margin=dict(l=10, r=10, t=40, b=10),
        title=title,
        xaxis_title="Distance (m)",
        yaxis_title=f"{y_col}{y_suffix}"
    )
    return fig

def plot_multi_driver_speed(drivers_data: dict, title="Speed"):
    fig = go.Figure()
    for drv, df in drivers_data.items():
        fig.add_trace(go.Scatter(x=df["Distance"], y=df["Speed"], mode="lines", name=drv))
    fig.update_layout(
        height=260,
        margin=dict(l=10, r=10, t=40, b=10),
        title=title,
        xaxis_title="Distance (m)",
        yaxis_title="kph"
    )
    return fig

def plot_delta(distance, delta, title="Delta vs Reference"):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=distance, y=delta, mode="lines", name="Delta (s)"))
    fig.update_layout(
        height=260,
        margin=dict(l=10, r=10, t=40, b=10),
        title=title,
        xaxis_title="Distance (m)",
        yaxis_title="Seconds"
    )
    return fig

def plot_longrun_laptimes(df, title="Lap times"):
    fig = go.Figure()
    for drv in df["Driver"].unique():
        sub = df[df["Driver"] == drv]
        fig.add_trace(go.Scatter(
            x=sub["LapNumber"], y=sub["LapTime_s"], mode="lines+markers", name=drv
        ))
    fig.update_layout(
        height=350,
        margin=dict(l=10, r=10, t=40, b=10),
        title=title,
        xaxis_title="Lap #",
        yaxis_title="Lap time (s)"
    )
    return fig