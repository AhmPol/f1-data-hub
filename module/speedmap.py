import numpy as np
import plotly.graph_objects as go
import fastf1

fastf1.Cache.enable_cache("fastf1_cache")


class SpeedDiffTrackMapPlotly:
    """
    Cloud-safe Plotly version of speed comparison on track between two drivers.
    Uses only 2 traces (line + colored points) to avoid resource limit crashes.
    """
    def __init__(self, session, driver_1, driver_2, n_points: int = 500):
        self.session = session
        self.driver_1 = driver_1
        self.driver_2 = driver_2
        self.n_points = int(n_points)

    def plot(self):
        lap1 = self.session.laps.pick_drivers(self.driver_1).pick_fastest()
        lap2 = self.session.laps.pick_drivers(self.driver_2).pick_fastest()

        if lap1 is None or lap2 is None:
            raise ValueError("Fastest lap not available for one of the selected drivers.")

        tel1 = lap1.get_telemetry().add_distance()
        tel2 = lap2.get_telemetry().add_distance()

        # Ensure required columns exist
        for tel in (tel1, tel2):
            if "Speed" not in tel.columns or "Distance" not in tel.columns:
                raise ValueError("Telemetry missing Speed/Distance columns for one of the drivers.")

        # Ensure 'X' and 'Y' exist (track coordinates)
        if ("X" not in tel1.columns) or ("Y" not in tel1.columns):
            tel1["X"] = tel1["Distance"]
            tel1["Y"] = tel1["Speed"]
            tel2["X"] = tel2["Distance"]
            tel2["Y"] = tel2["Speed"]

        max_dist = float(min(tel1["Distance"].max(), tel2["Distance"].max()))
        if not np.isfinite(max_dist) or max_dist <= 0:
            raise ValueError("Invalid distance data for selected drivers.")

        # Interpolate to common distance points (lower = faster + safer)
        n = max(200, min(self.n_points, 1200))
        common_distance = np.linspace(0, max_dist, n)

        tel1_speed = np.interp(common_distance, tel1["Distance"], tel1["Speed"])
        tel2_speed = np.interp(common_distance, tel2["Distance"], tel2["Speed"])
        speed_diff = tel1_speed - tel2_speed  # km/h

        # Track coordinates interpolation (use driver 1 geometry)
        x = np.interp(common_distance, tel1["Distance"], tel1["X"])
        y = np.interp(common_distance, tel1["Distance"], tel1["Y"])

        # Clean arrays to avoid NaNs breaking plotly
        speed_diff = np.nan_to_num(speed_diff, nan=0.0, posinf=0.0, neginf=0.0)
        x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
        y = np.nan_to_num(y, nan=0.0, posinf=0.0, neginf=0.0)

        fig = go.Figure()

        # Base track line (single trace)
        fig.add_trace(go.Scattergl(
            x=x, y=y,
            mode="lines",
            line=dict(color="lightgray", width=8),
            hoverinfo="skip",
            showlegend=False
        ))

        # Colored points along the line (single trace)
        fig.add_trace(go.Scattergl(
            x=x, y=y,
            mode="markers",
            marker=dict(
                size=5,
                color=speed_diff,
                colorscale="RdBu",
                reversescale=True,
                showscale=True,
                colorbar=dict(title="Speed Δ (km/h)"),
            ),
            customdata=np.stack([common_distance, speed_diff], axis=1),
            hovertemplate="Distance: %{customdata[0]:.0f} m<br>Speed Δ: %{customdata[1]:.2f} km/h<extra></extra>",
            showlegend=False
        ))

        # Lap time annotations (neutral color for dark theme)
        fig.add_annotation(
            x=float(x[-1]),
            y=float(y[-1]),
            text=f"{self.driver_1}: {lap1['LapTime'].total_seconds():.3f}s",
            showarrow=False,
            xanchor="right",
            font=dict(color="white")
        )
        fig.add_annotation(
            x=float(x[-1]),
            y=float(y[-1]) * 0.98,
            text=f"{self.driver_2}: {lap2['LapTime'].total_seconds():.3f}s",
            showarrow=False,
            xanchor="right",
            font=dict(color="white")
        )

        fig.update_layout(
            title=f"{self.session.event['EventName']} {self.session.event.year} — {self.driver_1} vs {self.driver_2} Speed Δ on Track",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False, scaleanchor="x", scaleratio=1),
            plot_bgcolor="rgb(30,30,30)",
            paper_bgcolor="rgb(30,30,30)",
            font=dict(color="white"),
            height=600,
            showlegend=False,
            margin=dict(l=10, r=10, t=60, b=10)
        )

        return fig


def show_speed_diff_track(session, key_prefix: str = ""):
    import streamlit as st

    drivers = sorted(list(set(session.laps["Driver"])))

    driver_1 = st.selectbox(
        "Select First Driver",
        drivers,
        key=f"{key_prefix}speed_diff_driver_1"
    )
    driver_2 = st.selectbox(
        "Select Second Driver",
        drivers,
        key=f"{key_prefix}speed_diff_driver_2"
    )

    # small control for nerds (safe)
    n_points = st.slider(
        "Resolution (points)",
        min_value=200,
        max_value=900,
        value=500,
        step=50,
        key=f"{key_prefix}speed_diff_points"
    )

    plotter = SpeedDiffTrackMapPlotly(session, driver_1, driver_2, n_points=n_points)
    fig = plotter.plot()
    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}speed_diff_track_chart")
