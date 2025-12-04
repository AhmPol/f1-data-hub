import pandas as pd
import plotly.graph_objects as go
import fastf1
import streamlit as st

fastf1.Cache.enable_cache('fastf1_cache')

class LapTimeScatterDriversPlotly:
    """
    Interactive Plotly scatter of lap times for selected drivers.
    Lap times are colored by tire compound.
    """
    def __init__(self, session, drivers=None):
        self.session = session
        # Use provided drivers or default to fastest driver
        self.drivers = drivers or [self.session.laps.pick_fastest()['Driver']]
        # Get compound color mapping
        self.compound_colors = fastf1.plotting.get_compound_mapping(session=self.session)

    def plot(self, driver):
        laps = self.session.laps.pick_driver(driver).pick_quicklaps().reset_index()
        if laps.empty:
            st.warning(f"No laps found for {driver}")
            return go.Figure()

        laps['LapTime(s)'] = laps['LapTime'].dt.total_seconds()

        fig = go.Figure()
        for compound, group in laps.groupby('Compound'):
            color = self.compound_colors.get(compound, '#888888')
            fig.add_trace(go.Scatter(
                x=group['LapNumber'],
                y=group['LapTime(s)'],
                mode='markers+lines',
                marker=dict(color=color, size=8),
                line=dict(width=2),
                name=f"{driver} ({compound})",
                hovertemplate="Driver: %{text}<br>Lap: %{x}<br>Lap Time: %{y:.3f}s<extra></extra>",
                text=[driver]*len(group)
            ))

        fig.update_layout(
            title=f"{driver} Lap Times - {self.session.event['EventName']} {self.session.event.year}",
            xaxis_title="Lap Number",
            yaxis_title="Lap Time (s)",
            yaxis=dict(autorange='reversed'),  # faster laps on top
            plot_bgcolor='rgb(30,30,30)',
            paper_bgcolor='rgb(30,30,30)',
            font=dict(color='white'),
            width=1000,
            height=600,
            legend_title="Driver (Compound)"
        )
        return fig


def show_lap_scatter(session):
    drivers = sorted(list(set(session.laps['Driver'])))
    selected_driver = st.selectbox(
        "Select Driver",
        drivers,
        index=0,
        key="lap_scatter_driver_select"  # unique key to prevent duplicates
    )
    plotter = LapTimeScatterDriversPlotly(session, drivers)
    fig = plotter.plot(selected_driver)
    st.plotly_chart(fig, use_container_width=True)
