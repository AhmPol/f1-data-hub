import pandas as pd
import plotly.graph_objects as go
import fastf1
from fastf1.plotting import get_driver_color

fastf1.Cache.enable_cache('fastf1_cache')

class RaceResultsDriversPlotly:
    """
    Interactive Plotly visualization of driver positions over a session.
    Works for any session type (Race, Sprint, FP, Q).
    """
    def __init__(self, session):
        self.session = session

    def plot(self):
        fig = go.Figure()

        for drv in self.session.drivers:
            drv_laps = self.session.laps.pick_driver(drv).reset_index()
            if drv_laps.empty:
                continue

            driver_abbr = drv_laps['Driver'].iloc[0]
            fig.add_trace(go.Scatter(
                x=drv_laps['LapNumber'],
                y=drv_laps['Position'],
                mode='lines+markers',
                name=driver_abbr,
                line=dict(color=get_driver_color(driver_abbr, session=self.session)),
                marker=dict(size=6),
                hovertemplate="Driver: %{text}<br>Lap: %{x}<br>Position: %{y}<extra></extra>",
                text=[driver_abbr]*len(drv_laps)
            ))

        fig.update_layout(
            title=f"{self.session.event['EventName']} {self.session.event.year} - Driver Positions",
            xaxis_title="Lap Number",
            yaxis_title="Position",
            yaxis=dict(autorange="reversed", dtick=1),  # top positions at top
            plot_bgcolor='rgb(30,30,30)',
            paper_bgcolor='rgb(30,30,30)',
            font=dict(color='white'),
            legend_title="Driver",
            hovermode='closest',
            width=1000,
            height=600
        )
        return fig

def show_race_results(session):
    import streamlit as st
    plotter = RaceResultsDriversPlotly(session)
    fig = plotter.plot()
    st.plotly_chart(fig, use_container_width=True)
