import fastf1
from fastf1 import plotting
import pandas as pd
import plotly.express as px
import streamlit as st

fastf1.Cache.enable_cache("fastf1_cache")
plotting.setup_mpl()


class TelemetryOverlayPlotly:
    """
    Plots telemetry overlays for selected drivers' fastest laps using Plotly.
    Supports multiple telemetry channels: Speed, Throttle, Brake, Gear, RPM, etc.
    """
    TELEMETRY_CHANNELS = ["Speed", "Throttle", "Brake", "Gear", "RPM"]

    def __init__(self, session, telemetry_channel="Speed", drivers=None):
        if telemetry_channel not in self.TELEMETRY_CHANNELS:
            raise ValueError(f"Invalid telemetry channel. Choose from {self.TELEMETRY_CHANNELS}")
        self.session = session
        self.telemetry_channel = telemetry_channel
        self.driver_colors = plotting.get_driver_color_mapping(session=self.session)
        self.drivers = drivers  # list of driver codes (e.g., ["VER","HAM"])

    def get_fastest_laps_telemetry(self):
        telemetry_list = []

        # If not provided, default to all drivers
        drivers = self.drivers or list(self.session.drivers)

        for drv in drivers:
            # pick_fastest can return None
            lap = self.session.laps.pick_drivers(drv).pick_fastest()
            if lap is None:
                continue

            # Car data + distance
            lap_tel = lap.get_car_data().add_distance()
            if self.telemetry_channel not in lap_tel.columns:
                continue

            df = pd.DataFrame({
                "Driver": drv,
                "Distance": lap_tel["Distance"],
                self.telemetry_channel: lap_tel[self.telemetry_channel],
            })
            telemetry_list.append(df)

        if not telemetry_list:
            return pd.DataFrame(columns=["Driver", "Distance", self.telemetry_channel])

        return pd.concat(telemetry_list, ignore_index=True)

    def plot(self):
        telemetry_df = self.get_fastest_laps_telemetry()

        if telemetry_df.empty:
            st.warning(f"No telemetry data available for channel {self.telemetry_channel} with the selected drivers.")
            return None

        fig = px.line(
            telemetry_df,
            x="Distance",
            y=self.telemetry_channel,
            color="Driver",
            color_discrete_map=self.driver_colors,
            hover_data=["Driver", "Distance", self.telemetry_channel],
            labels={"Distance": "Distance (m)", self.telemetry_channel: self.telemetry_channel},
            title=f"{self.session.event['EventName']} {self.session.event.year} — {self.telemetry_channel} Overlay",
        )

        fig.update_layout(
            plot_bgcolor="rgb(30,30,30)",
            paper_bgcolor="rgb(30,30,30)",
            font=dict(color="white"),
            legend_title_text="Driver",
            height=600,
        )

        return fig


def show_telemetry_overlay(session):
    """
    Streamlit-friendly function to display telemetry overlay.
    Adds driver selection + channel selection.
    Uses compare mode drivers if available in st.session_state["compare_drivers"].
    """
    all_drivers = sorted(list(set(session.laps["Driver"]))) if "Driver" in session.laps.columns else sorted(list(session.drivers))

    # If your dashboard stored compare drivers, use them as default
    default_drivers = None
    if "compare_drivers" in st.session_state and st.session_state["compare_drivers"]:
        default_drivers = list(st.session_state["compare_drivers"])
    else:
        default_drivers = all_drivers[:6]  # sensible default

    telemetry_channel = st.selectbox(
        "Select Telemetry Channel",
        TelemetryOverlayPlotly.TELEMETRY_CHANNELS,
        index=0,
        key="telemetry_channel_select",
    )

    selected_drivers = st.multiselect(
        "Select Drivers (fastest lap overlay)",
        options=all_drivers,
        default=default_drivers,
        key="telemetry_driver_multiselect",
    )

    if not selected_drivers:
        st.warning("Select at least one driver.")
        return

    plotter = TelemetryOverlayPlotly(session, telemetry_channel=telemetry_channel, drivers=selected_drivers)
    fig = plotter.plot()
    if fig:
        st.plotly_chart(fig, use_container_width=True)
