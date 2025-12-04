import pandas as pd
import plotly.graph_objects as go
import fastf1
import streamlit as st
from fastf1.plotting import get_driver_color_mapping

fastf1.Cache.enable_cache('fastf1_cache')

class OverallLapTimesPlotly:
    """
    Interactive Plotly version of OverallLapTimes.
    Shows all selected drivers' lap times in one interactive plot.
    """
    def __init__(self, session, drivers=None):
        self.session = session
        self.drivers = drivers or sorted(list(set(session.laps['Driver'])))
        self.driver_colors = get_driver_color_mapping(session=session)

    def plot(self, selected_drivers):
        fig = go.Figure()
        for driver in selected_drivers:
            laps = self.session.laps.pick_driver(driver).pick_quicklaps().reset_index()
            if laps.empty:
                continue
            laps['LapTime(s)'] = laps['LapTime'].dt.total_seconds()
            fig.add_trace(go.Scatter(
                x=laps['LapNumber'],
                y=laps['LapTime(s)'],
                mode='lines+markers',
                name=driver,
                line=dict(color=self.driver_colors.get(driver, '#888888'), width=2),
                marker=dict(size=6),
                hovertemplate="Driver: %{text}<br>Lap: %{x}<br>Lap Time: %{y:.3f}s<extra></extra>",
                text=[driver]*len(laps)
            ))

        fig.update_layout(
            title=f"Overall Lap Times - {self.session.event['EventName']} {self.session.event.year}",
            xaxis_title="Lap Number",
            yaxis_title="Lap Time (s)",
            yaxis=dict(autorange='reversed'),  # faster laps on top
            plot_bgcolor='rgb(30,30,30)',
            paper_bgcolor='rgb(30,30,30)',
            font=dict(color='white'),
            width=1000,
            height=600,
            legend_title="Driver"
        )
        return fig


def show_overall_laptimes(session):
    all_drivers = sorted(list(set(session.laps['Driver'])))
    selected_drivers = st.multiselect(
        "Select Drivers",
        all_drivers,
        default=all_drivers[:5],  # default to first 5 drivers
        key="overall_laptimes_select"
    )
    if selected_drivers:
        plotter = OverallLapTimesPlotly(session, drivers=all_drivers)
        fig = plotter.plot(selected_drivers)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Please select at least one driver.")
