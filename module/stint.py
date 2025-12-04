import pandas as pd
import fastf1
import plotly.graph_objects as go
from fastf1.plotting import get_compound_mapping

fastf1.Cache.enable_cache('fastf1_cache')

class StintStrategyDriversPlotly:
    def __init__(self, session, title=None):
        self.session = session
        self.title = title or f"{self.session.event['EventName']} {self.session.event.year} Strategies"

    def plot(self):
        laps = self.session.laps.reset_index()
        drivers = sorted(laps['Driver'].unique())

        # Compute stints
        stints = laps.groupby(['Driver', 'Stint', 'Compound']).agg(
            StintLength=('LapNumber', 'count'),
            StartLap=('LapNumber', 'min')
        ).reset_index()
        stints['EndLap'] = stints['StartLap'] + stints['StintLength'] - 1

        # Map compound to colors
        compound_colors = get_compound_mapping(session=self.session)
        stints['Color'] = stints['Compound'].map(compound_colors)

        # Build interactive timeline
        fig = go.Figure()
        for driver in drivers:
            driver_stints = stints[stints['Driver'] == driver]
            for _, row in driver_stints.iterrows():
                fig.add_trace(go.Bar(
                    y=[driver],
                    x=[row['StintLength']],
                    base=row['StartLap'],
                    orientation='h',
                    marker_color=row['Color'],
                    name=row['Compound'],
                    hovertemplate=(
                        f"Driver: {driver}<br>"
                        f"Stint: {row['Stint']}<br>"
                        f"Compound: {row['Compound']}<br>"
                        f"Laps: {row['StartLap']} - {row['EndLap']}<extra></extra>"
                    ),
                    showlegend=False
                ))

        fig.update_layout(
            title=self.title,
            xaxis_title="Lap Number",
            yaxis_title="Driver",
            barmode='stack',
            plot_bgcolor='rgb(30,30,30)',
            paper_bgcolor='rgb(30,30,30)',
            font=dict(color='white'),
            height=max(400, 40*len(drivers))
        )
        return fig


def show_stint_strategy(session):
    import streamlit as st
    plotter = StintStrategyDriversPlotly(session)
    fig = plotter.plot()
    st.plotly_chart(fig, use_container_width=True)
