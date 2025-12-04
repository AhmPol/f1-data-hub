import pandas as pd
import fastf1
import plotly.express as px
from fastf1.plotting import get_driver_color_mapping, get_compound_mapping

fastf1.Cache.enable_cache('fastf1_cache')

class LapTimeDistributionAllDriversPlotly:
    def __init__(self, session):
        self.session = session
        self.driver_colors = get_driver_color_mapping(session=self.session)
        self.compound_colors = get_compound_mapping(session=self.session)

    def plot(self):
        # Get all laps for all drivers
        laps_all = self.session.laps.pick_quicklaps().reset_index()
        if laps_all.empty:
            raise ValueError("No laps for drivers in this session.")
        laps_all["LapTime(s)"] = laps_all["LapTime"].dt.total_seconds()

        # Compute median lap time per driver
        median_times = laps_all.groupby('Driver')["LapTime(s)"].median().sort_values()
        sorted_drivers = list(median_times.index)

        fig = px.violin(
            laps_all,
            x="Driver",
            y="LapTime(s)",
            color="Driver",
            box=True,
            points="all",
            hover_data=["LapNumber", "Compound"],
            category_orders={"Driver": sorted_drivers},  # order by median lap time
            color_discrete_map=self.driver_colors
        )

        fig.update_traces(marker=dict(size=6, opacity=0.8), line=dict(width=1))
        fig.update_layout(
            title=f"All Drivers - {self.session.event['EventName']} {self.session.event.year} Lap Times",
            xaxis_title="Driver",
            yaxis_title="Lap Time (s)",
            plot_bgcolor='rgb(30,30,30)',
            paper_bgcolor='rgb(30,30,30)',
            font=dict(color='white'),
            width=1000,
            height=600
        )
        return fig

def show_all_laptimes(session):
    import streamlit as st
    plotter = LapTimeDistributionAllDriversPlotly(session)
    fig = plotter.plot()
    st.plotly_chart(fig, use_container_width=True)
